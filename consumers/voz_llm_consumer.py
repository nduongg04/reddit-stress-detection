#!/usr/bin/env python3
"""
VOZ LLM Consumer - Real-time Kafka consumer with LLM classification

Consumes posts from Kafka, classifies with llama3.1:8b, writes to Cassandra.
Runs locally to access Ollama on localhost.

Flow: Kafka (voz.posts.raw.v1) → LLM (llama3.1:8b) → Cassandra (voz_classified_posts)

Usage:
    python consumers/voz_llm_consumer.py
"""

import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from confluent_kafka import Consumer, KafkaError
from cassandra.cluster import Cluster

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration
KAFKA_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "voz.posts.raw.v1")
KAFKA_GROUP = os.getenv("KAFKA_GROUP", "voz-llm-consumer")
CASSANDRA_HOST = os.getenv("CASSANDRA_HOST", "localhost")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")

# Graceful shutdown
running = True

def signal_handler(sig, frame):
    global running
    logger.info("Shutdown signal received...")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


class VOZLLMConsumer:
    """Real-time Kafka consumer with LLM classification"""

    def __init__(self):
        self.consumer = self._create_consumer()
        self.cluster, self.session = self._connect_cassandra()
        self.processed = 0
        self.stress_count = 0
        self.start_time = time.time()

        # LLM prompt
        self.prompt_template = """Phân tích bài đăng tiếng Việt và trả về JSON:
- aspects: mảng số [0-9] cho các khía cạnh stress (0=Công việc, 1=Tài chính, 2=Học tập, 3=Gia đình, 4=Sức khỏe, 5=Tình cảm, 6=Hiện sinh, 7=Xã hội, 8=Sự kiện, 9=Hình ảnh bản thân)
- gender: "nam"/"nữ"/"unknown"
- age_group: "teen"/"young_adult"/"adult"/"middle_aged"/"senior"/"unknown"
- occupation: "student"/"office_worker"/"it_engineer"/"healthcare"/"teacher"/"blue_collar"/"freelance"/"unemployed"/"unknown"
- relationship: "single"/"dating"/"married"/"divorced"/"unknown"
- reasoning: giải thích ngắn

Bài đăng:
"""

    def _create_consumer(self):
        """Create Kafka consumer"""
        config = {
            "bootstrap.servers": KAFKA_SERVERS,
            "group.id": KAFKA_GROUP,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
            "session.timeout.ms": 30000,
        }
        consumer = Consumer(config)
        consumer.subscribe([KAFKA_TOPIC])
        logger.info(f"Subscribed to Kafka topic: {KAFKA_TOPIC}")
        return consumer

    def _connect_cassandra(self):
        """Connect to Cassandra"""
        cluster = Cluster([CASSANDRA_HOST], port=9042)
        session = cluster.connect("reddit_rt")
        logger.info(f"Connected to Cassandra: {CASSANDRA_HOST}")
        return cluster, session

    def classify_with_llm(self, text: str) -> dict:
        """Classify text using LLM"""
        prompt = self.prompt_template + text[:1000]

        default = {
            "aspects": [],
            "gender": "unknown",
            "age_group": "unknown",
            "occupation": "unknown",
            "relationship": "unknown",
            "reasoning": "LLM failed",
            "processing_time_ms": 0
        }

        start = time.time()
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": LLM_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 500}
                },
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                text_resp = data.get("response", "")
                start_idx = text_resp.find("{")
                end_idx = text_resp.rfind("}") + 1
                if start_idx >= 0 and end_idx > start_idx:
                    result = json.loads(text_resp[start_idx:end_idx])
                    result["processing_time_ms"] = int((time.time() - start) * 1000)
                    return result

        except Exception as e:
            logger.debug(f"LLM error: {e}")

        default["processing_time_ms"] = int((time.time() - start) * 1000)
        return default

    def write_to_cassandra(self, post: dict, classification: dict):
        """Write classified post to Cassandra"""
        hour_bucket = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
        classified_at = datetime.now(timezone.utc)

        aspects = classification.get("aspects", [])
        if isinstance(aspects, list):
            aspects = [a for a in aspects if isinstance(a, int) and 0 <= a <= 9]
        else:
            aspects = []

        # Ensure demographic fields are strings (LLM sometimes returns lists)
        def ensure_string(val, default="unknown"):
            if isinstance(val, list):
                return val[0] if val else default
            return str(val) if val else default

        gender = ensure_string(classification.get("gender"), "unknown")
        age_group = ensure_string(classification.get("age_group"), "unknown")
        occupation = ensure_string(classification.get("occupation"), "unknown")
        relationship = ensure_string(classification.get("relationship"), "unknown")

        aspect_probs = [1.0 if i in aspects else 0.0 for i in range(10)]

        # Parse original timestamp
        original_ts = None
        if post.get("timestamp"):
            try:
                original_ts = datetime.fromisoformat(post["timestamp"].replace("Z", "+00:00"))
            except:
                pass

        query = """
        INSERT INTO voz_classified_posts (
            hour_bucket, classified_at, post_id, text, url, source, original_timestamp,
            aspects, aspect_probs, confidence, stress_label, reasoning,
            gender, age_group, occupation, relationship,
            model_version, processing_time_ms
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s
        )
        """

        self.session.execute(query, (
            hour_bucket,
            classified_at,
            post["post_id"],
            post["text"],
            post.get("url"),
            post.get("source"),
            original_ts,
            aspects,
            aspect_probs,
            len(aspects) / 10.0 if aspects else 0.0,
            len(aspects) > 0,
            classification.get("reasoning", "")[:500] if classification.get("reasoning") else "",
            gender,
            age_group,
            occupation,
            relationship,
            f"{LLM_MODEL}_realtime",
            classification.get("processing_time_ms", 0),
        ))

    def process_message(self, msg):
        """Process a single Kafka message"""
        try:
            post = json.loads(msg.value().decode("utf-8"))
        except Exception as e:
            logger.warning(f"Parse error: {e}")
            return

        # Classify with LLM
        classification = self.classify_with_llm(post["text"])

        # Write to Cassandra
        self.write_to_cassandra(post, classification)

        self.processed += 1
        if classification.get("aspects"):
            self.stress_count += 1

        # Log progress
        aspects_str = ",".join(str(a) for a in classification.get("aspects", [])) or "none"
        elapsed = time.time() - self.start_time
        rate = self.processed / elapsed * 60 if elapsed > 0 else 0

        logger.info(
            f"[{self.processed}] {post['post_id'][:20]} | "
            f"Aspects: [{aspects_str}] | "
            f"Gender: {classification.get('gender', 'unknown')} | "
            f"Time: {classification.get('processing_time_ms')}ms | "
            f"Rate: {rate:.1f}/min"
        )

    def run(self):
        """Main consumer loop"""
        global running

        logger.info("=" * 70)
        logger.info("VOZ LLM Consumer - Real-time Stress Detection")
        logger.info("=" * 70)
        logger.info(f"Kafka: {KAFKA_SERVERS} / {KAFKA_TOPIC}")
        logger.info(f"Cassandra: {CASSANDRA_HOST}")
        logger.info(f"LLM: {OLLAMA_URL} / {LLM_MODEL}")
        logger.info("=" * 70)
        logger.info("Waiting for messages... (Ctrl+C to stop)")
        logger.info("")

        try:
            while running:
                msg = self.consumer.poll(timeout=1.0)

                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.error(f"Kafka error: {msg.error()}")
                    continue

                self.process_message(msg)

        finally:
            self.shutdown()

    def shutdown(self):
        """Clean shutdown"""
        logger.info("")
        logger.info("=" * 70)
        logger.info("Shutting down...")
        logger.info("=" * 70)

        self.consumer.close()
        self.cluster.shutdown()

        elapsed = time.time() - self.start_time
        logger.info(f"Processed: {self.processed} posts")
        logger.info(f"Stress: {self.stress_count} ({self.stress_count/self.processed*100:.1f}%)" if self.processed else "N/A")
        logger.info(f"Time: {elapsed/60:.1f} minutes")
        logger.info("=" * 70)


def main():
    consumer = VOZLLMConsumer()
    consumer.run()


if __name__ == "__main__":
    main()
