#!/usr/bin/env python3
"""
Batch VOZ Classification Script

Reads posts from Kafka, classifies with LLM, writes to Cassandra.
For testing/demo when Spark streaming is not available.

Usage:
    python scripts/batch_classify_voz.py [--limit 10]
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from confluent_kafka import Consumer, KafkaError
from cassandra.cluster import Cluster

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration
KAFKA_SERVERS = "localhost:29092"
KAFKA_TOPIC = "voz.posts.raw.v1"
CASSANDRA_HOST = "localhost"
OLLAMA_URL = "http://localhost:11434"
LLM_MODEL = "llama3.1:8b"


def create_kafka_consumer():
    """Create Kafka consumer"""
    config = {
        "bootstrap.servers": KAFKA_SERVERS,
        "group.id": "voz-batch-classifier",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": True,
    }
    consumer = Consumer(config)
    consumer.subscribe([KAFKA_TOPIC])
    return consumer


def connect_cassandra():
    """Connect to Cassandra"""
    cluster = Cluster([CASSANDRA_HOST], port=9042)
    session = cluster.connect("reddit_rt")
    return cluster, session


def classify_with_llm(text: str) -> dict:
    """Classify text using LLM"""
    import requests

    prompt = """Phân tích bài đăng tiếng Việt và trả về JSON:
- aspects: mảng số [0-9] cho các khía cạnh stress (0=Công việc, 1=Tài chính, 2=Học tập, 3=Gia đình, 4=Sức khỏe, 5=Tình cảm, 6=Hiện sinh, 7=Xã hội, 8=Sự kiện, 9=Hình ảnh bản thân)
- gender: "nam"/"nữ"/"unknown"
- age_group: "teen"/"young_adult"/"adult"/"middle_aged"/"senior"/"unknown"
- occupation: "student"/"office_worker"/"it_engineer"/"healthcare"/"teacher"/"blue_collar"/"freelance"/"unemployed"/"unknown"
- relationship: "single"/"dating"/"married"/"divorced"/"unknown"
- reasoning: giải thích ngắn

Bài đăng:
""" + text[:1000]

    default = {
        "aspects": [],
        "gender": "unknown",
        "age_group": "unknown",
        "occupation": "unknown",
        "relationship": "unknown",
        "reasoning": "LLM failed"
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
        logger.warning(f"LLM error: {e}")

    default["processing_time_ms"] = int((time.time() - start) * 1000)
    return default


def write_to_cassandra(session, post: dict, classification: dict):
    """Write classified post to Cassandra"""
    hour_bucket = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
    classified_at = datetime.now(timezone.utc)

    aspects = classification.get("aspects", [])
    if isinstance(aspects, list):
        aspects = [a for a in aspects if isinstance(a, int) and 0 <= a <= 9]
    else:
        aspects = []

    aspect_probs = [1.0 if i in aspects else 0.0 for i in range(10)]

    query = """
    INSERT INTO voz_classified_posts (
        hour_bucket, classified_at, post_id, text, url, source,
        aspects, aspect_probs, confidence, stress_label, reasoning,
        gender, age_group, occupation, relationship,
        model_version, processing_time_ms
    ) VALUES (
        %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s
    )
    """

    session.execute(query, (
        hour_bucket,
        classified_at,
        post["post_id"],
        post["text"],
        post.get("url"),
        post.get("source"),
        aspects,
        aspect_probs,
        len(aspects) / 10.0 if aspects else 0.0,
        len(aspects) > 0,
        classification.get("reasoning", "")[:500],
        classification.get("gender", "unknown"),
        classification.get("age_group", "unknown"),
        classification.get("occupation", "unknown"),
        classification.get("relationship", "unknown"),
        f"{LLM_MODEL}_batch",
        classification.get("processing_time_ms", 0),
    ))


def main():
    parser = argparse.ArgumentParser(description="Batch VOZ Classification")
    parser.add_argument("--limit", type=int, default=10, help="Max posts to process")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Batch VOZ Classification")
    logger.info("=" * 60)
    logger.info(f"Kafka: {KAFKA_SERVERS} / {KAFKA_TOPIC}")
    logger.info(f"Cassandra: {CASSANDRA_HOST}")
    logger.info(f"LLM: {OLLAMA_URL} / {LLM_MODEL}")
    logger.info(f"Limit: {args.limit} posts")
    logger.info("=" * 60)

    # Connect
    consumer = create_kafka_consumer()
    cluster, session = connect_cassandra()

    processed = 0
    stress_count = 0

    try:
        while processed < args.limit:
            msg = consumer.poll(timeout=5.0)

            if msg is None:
                logger.info("No more messages")
                break

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    logger.info("End of partition")
                    break
                logger.error(f"Kafka error: {msg.error()}")
                continue

            # Parse message
            try:
                post = json.loads(msg.value().decode("utf-8"))
            except Exception as e:
                logger.warning(f"Parse error: {e}")
                continue

            logger.info(f"[{processed + 1}/{args.limit}] Processing: {post['post_id']}")

            # Classify
            classification = classify_with_llm(post["text"])

            # Write to Cassandra
            write_to_cassandra(session, post, classification)

            processed += 1
            if classification.get("aspects"):
                stress_count += 1

            aspects_str = ",".join(str(a) for a in classification.get("aspects", [])) or "none"
            logger.info(f"  → Aspects: [{aspects_str}], Gender: {classification.get('gender')}, Time: {classification.get('processing_time_ms')}ms")

    except KeyboardInterrupt:
        logger.info("Interrupted")
    finally:
        consumer.close()
        cluster.shutdown()

    logger.info("=" * 60)
    logger.info("Summary")
    logger.info("=" * 60)
    logger.info(f"Processed: {processed}")
    logger.info(f"Stress: {stress_count} ({stress_count/processed*100:.1f}%)" if processed else "N/A")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
