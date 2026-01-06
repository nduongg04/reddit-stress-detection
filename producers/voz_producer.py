#!/usr/bin/env python3
"""
VOZ Kafka Producer

Reads VOZ posts from Cassandra and publishes to Kafka topic for real-time processing.
This enables the Spark streaming pipeline to process VOZ posts with LLM inference.

Usage:
    python producers/voz_producer.py [--batch-size 10] [--delay 5]
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

from confluent_kafka import Producer

# Cassandra imports
try:
    from cassandra.cluster import Cluster
except ImportError:
    print("Installing cassandra-driver...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "cassandra-driver"], check=True)
    from cassandra.cluster import Cluster

# Configuration
KAFKA_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "voz.posts.raw.v1")
CASSANDRA_HOST = os.getenv("CASSANDRA_HOST", "localhost")
CASSANDRA_PORT = int(os.getenv("CASSANDRA_PORT", "9042"))
CASSANDRA_KEYSPACE = "reddit_rt"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def create_kafka_producer() -> Producer:
    """Create Kafka producer with optimized settings"""
    config = {
        "bootstrap.servers": KAFKA_SERVERS,
        "client.id": "voz-producer",
        "acks": "all",
        "retries": 3,
        "retry.backoff.ms": 1000,
        "batch.size": 16384,
        "linger.ms": 100,
        "compression.type": "snappy",
    }
    return Producer(config)


def connect_to_cassandra():
    """Connect to Cassandra cluster"""
    logger.info(f"Connecting to Cassandra at {CASSANDRA_HOST}:{CASSANDRA_PORT}...")
    cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT)
    session = cluster.connect(CASSANDRA_KEYSPACE)
    logger.info(f"Connected to keyspace: {CASSANDRA_KEYSPACE}")
    return cluster, session


def fetch_unprocessed_posts(session, batch_size: int = 100):
    """
    Fetch posts from voz_raw_posts that haven't been classified yet.

    Uses a simple approach: compare with voz_classified_posts by post_id.
    """
    # Get all raw post IDs
    raw_query = "SELECT post_id, text, url, source, timestamp FROM voz_raw_posts LIMIT 10000"
    raw_posts = list(session.execute(raw_query))

    if not raw_posts:
        return []

    # Get already classified post IDs (simple approach for demo)
    # In production, use a materialized view or separate tracking table
    try:
        classified_query = "SELECT post_id FROM voz_classified_posts LIMIT 50000 ALLOW FILTERING"
        classified_ids = {row.post_id for row in session.execute(classified_query)}
    except Exception:
        # Table might not exist yet
        classified_ids = set()

    # Filter unprocessed
    unprocessed = [p for p in raw_posts if p.post_id not in classified_ids]

    logger.info(f"Raw posts: {len(raw_posts)}, Classified: {len(classified_ids)}, Unprocessed: {len(unprocessed)}")

    return unprocessed[:batch_size]


def delivery_callback(err, msg):
    """Kafka delivery callback"""
    if err:
        logger.error(f"Message delivery failed: {err}")
    else:
        logger.debug(f"Message delivered to {msg.topic()} [{msg.partition()}]")


def run_producer(batch_size: int = 10, delay: float = 5.0, continuous: bool = True):
    """Run the VOZ Kafka producer"""
    logger.info("=" * 60)
    logger.info("VOZ Kafka Producer")
    logger.info("=" * 60)
    logger.info(f"Kafka: {KAFKA_SERVERS}")
    logger.info(f"Topic: {KAFKA_TOPIC}")
    logger.info(f"Cassandra: {CASSANDRA_HOST}:{CASSANDRA_PORT}")
    logger.info(f"Batch size: {batch_size}")
    logger.info(f"Delay: {delay}s")
    logger.info("=" * 60)

    # Connect to services
    cluster, session = connect_to_cassandra()
    producer = create_kafka_producer()

    total_published = 0

    try:
        while True:
            posts = fetch_unprocessed_posts(session, batch_size)

            if not posts:
                if continuous:
                    logger.info("No new posts, waiting...")
                    time.sleep(delay * 2)
                    continue
                else:
                    logger.info("No more posts to process")
                    break

            for post in posts:
                # Convert to JSON message
                message = {
                    "post_id": post.post_id,
                    "text": post.text,
                    "url": post.url,
                    "source": post.source,
                    "timestamp": post.timestamp.isoformat() if post.timestamp else None,
                    "crawled_at": datetime.now(timezone.utc).isoformat(),
                }

                # Publish to Kafka
                producer.produce(
                    KAFKA_TOPIC,
                    key=post.post_id.encode("utf-8"),
                    value=json.dumps(message, ensure_ascii=False).encode("utf-8"),
                    callback=delivery_callback,
                )

                total_published += 1

            # Flush and log
            producer.flush()
            logger.info(f"Published {len(posts)} posts (total: {total_published})")

            if not continuous:
                break

            time.sleep(delay)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        producer.flush()
        cluster.shutdown()
        logger.info(f"Total published: {total_published}")
        logger.info("Producer stopped")


def main():
    parser = argparse.ArgumentParser(description="VOZ Kafka Producer")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size per cycle")
    parser.add_argument("--delay", type=float, default=5.0, help="Delay between batches (seconds)")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    run_producer(
        batch_size=args.batch_size,
        delay=args.delay,
        continuous=not args.once,
    )


if __name__ == "__main__":
    main()
