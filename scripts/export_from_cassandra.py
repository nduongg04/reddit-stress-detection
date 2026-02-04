#!/usr/bin/env python3
"""Export VOZ posts from Cassandra to JSONL."""

import json
import argparse
from datetime import datetime
from cassandra.cluster import Cluster
from cassandra.query import SimpleStatement

def export_posts(output_path: str, host: str = "localhost", port: int = 9042):
    """Export all posts from voz_raw_posts to JSONL."""
    cluster = Cluster([host], port=port)
    session = cluster.connect("reddit_rt")

    query = SimpleStatement("SELECT post_id, text, url, timestamp, crawled_at, source FROM voz_raw_posts")
    rows = session.execute(query)

    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for row in rows:
            record = {
                "post_id": row.post_id,
                "text": row.text,
                "url": row.url,
                "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                "crawled_at": row.crawled_at.isoformat() if row.crawled_at else None,
                "source": row.source
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
            if count % 1000 == 0:
                print(f"Exported {count} posts...")

    cluster.shutdown()
    print(f"Total exported: {count} posts to {output_path}")
    return count

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export VOZ posts from Cassandra")
    parser.add_argument("--output", "-o", default="data/raw/voz_exported.jsonl", help="Output JSONL file")
    parser.add_argument("--host", default="localhost", help="Cassandra host")
    parser.add_argument("--port", type=int, default=9042, help="Cassandra port")
    args = parser.parse_args()

    export_posts(args.output, args.host, args.port)
