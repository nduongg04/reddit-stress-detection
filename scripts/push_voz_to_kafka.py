#!/usr/bin/env python3
"""Push existing VOZ posts from Cassandra to Kafka for ML processing."""

import json
import time
from cassandra.cluster import Cluster
from kafka import KafkaProducer

# Configuration
CASSANDRA_HOST = "localhost"
KAFKA_BOOTSTRAP = "localhost:29092"
KAFKA_TOPIC = "voz.posts.raw.v1"
BATCH_SIZE = 100

def main():
    # Connect to Cassandra
    print("Connecting to Cassandra...")
    cluster = Cluster([CASSANDRA_HOST])
    session = cluster.connect("reddit_rt")

    # Connect to Kafka
    print("Connecting to Kafka...")
    producer = KafkaProducer(
        bootstrap_servers=[KAFKA_BOOTSTRAP],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

    # Query all VOZ posts
    print("Fetching VOZ posts from Cassandra...")
    rows = session.execute("SELECT post_id, text, url, source, crawled_at FROM voz_raw_posts")

    count = 0
    for row in rows:
        if not row.text or not row.text.strip():
            continue

        message = {
            "post_id": row.post_id,
            "text": row.text,
            "url": row.url or "",
            "source": row.source or "voz",
            "timestamp": str(row.crawled_at) if row.crawled_at else "",
            "crawled_at": str(row.crawled_at) if row.crawled_at else ""
        }

        producer.send(KAFKA_TOPIC, value=message)
        count += 1

        if count % BATCH_SIZE == 0:
            producer.flush()
            print(f"Sent {count} posts...")

    producer.flush()
    producer.close()
    cluster.shutdown()

    print(f"\n✓ Done! Sent {count} posts to Kafka topic '{KAFKA_TOPIC}'")
    print("The Spark streaming job will process them automatically.")

if __name__ == "__main__":
    main()
