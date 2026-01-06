#!/usr/bin/env python3
"""
Data Cleaning Pipeline for VOZ.vn Posts

Sprint 2: Clean and deduplicate raw posts before LLM labeling.
- Token length filtering (20-300 tokens using underthesea)
- Semantic deduplication (MiniLM embeddings, cosine similarity ≥0.90)

Usage:
    python scripts/data_cleaning.py [--from-cassandra] [--output OUTPUT]
"""

import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
from pyvi import ViTokenizer
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
MIN_TOKENS = 20
MAX_TOKENS = 300
SIMILARITY_THRESHOLD = 0.90
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384

# Cassandra settings
CASSANDRA_HOST = "localhost"
CASSANDRA_PORT = 9042
CASSANDRA_KEYSPACE = "reddit_rt"
CASSANDRA_TABLE = "voz_raw_posts"


def count_tokens(text: str) -> int:
    """Count tokens using pyvi Vietnamese tokenizer."""
    tokenized = ViTokenizer.tokenize(text)
    tokens = tokenized.split()
    return len(tokens)


def load_posts_from_cassandra() -> List[Dict[str, Any]]:
    """Load posts from Cassandra table."""
    from cassandra.cluster import Cluster

    logger.info(f"Connecting to Cassandra at {CASSANDRA_HOST}:{CASSANDRA_PORT}...")
    cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT)
    session = cluster.connect(CASSANDRA_KEYSPACE)

    query = f"SELECT post_id, text, timestamp, source, url FROM {CASSANDRA_TABLE}"
    logger.info(f"Executing query: {query}")

    rows = session.execute(query)
    posts = []
    for row in rows:
        posts.append({
            "post_id": row.post_id,
            "text": row.text,
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
            "source": row.source,
            "url": row.url
        })

    cluster.shutdown()
    logger.info(f"Loaded {len(posts)} posts from Cassandra")
    return posts


def load_posts_from_jsonl(input_path: str) -> List[Dict[str, Any]]:
    """Load posts from JSONL file."""
    posts = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                posts.append(json.loads(line))
    logger.info(f"Loaded {len(posts)} posts from {input_path}")
    return posts


def filter_by_token_length(posts: List[Dict[str, Any]]) -> tuple:
    """Filter posts by token count (20-300 tokens)."""
    filtered = []
    removed_count = 0

    for i, post in enumerate(posts):
        text = post.get("text", "")
        token_count = count_tokens(text)

        if MIN_TOKENS <= token_count <= MAX_TOKENS:
            post["token_count"] = token_count
            filtered.append(post)
        else:
            removed_count += 1

        if (i + 1) % 1000 == 0:
            logger.info(f"Token filter progress: {i + 1}/{len(posts)} posts processed")

    logger.info(f"Token filter: kept {len(filtered)}, removed {removed_count}")
    return filtered, removed_count


def generate_embeddings(posts: List[Dict[str, Any]], model: SentenceTransformer) -> np.ndarray:
    """Generate embeddings for all posts."""
    texts = [post.get("text", "") for post in posts]
    logger.info(f"Generating embeddings for {len(texts)} posts...")

    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True  # Normalize for cosine similarity
    )

    logger.info(f"Generated embeddings with shape {embeddings.shape}")
    return embeddings


def deduplicate_posts(
    posts: List[Dict[str, Any]],
    embeddings: np.ndarray,
    threshold: float = SIMILARITY_THRESHOLD
) -> tuple:
    """Remove semantic duplicates using sklearn cosine similarity."""
    n_posts = len(posts)
    logger.info(f"Deduplicating {n_posts} posts with threshold {threshold}...")

    # Track which posts to keep (start with all)
    keep_mask = np.ones(n_posts, dtype=bool)

    # Parse timestamps for comparison
    def parse_timestamp(post):
        ts = post.get("timestamp")
        if ts is None:
            return datetime.max
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts)
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except:
            return datetime.max

    timestamps = [parse_timestamp(p) for p in posts]

    # Compute cosine similarity in batches to avoid memory issues
    batch_size = 500
    logger.info(f"Computing similarity in batches of {batch_size}...")

    for i in range(0, n_posts, batch_size):
        batch_end = min(i + batch_size, n_posts)
        if i % 1000 == 0:
            logger.info(f"Dedup progress: {i}/{n_posts} posts processed")

        # Compute similarity between this batch and all posts
        batch_embeddings = embeddings[i:batch_end]
        similarities = cosine_similarity(batch_embeddings, embeddings)

        for batch_idx, global_i in enumerate(range(i, batch_end)):
            if not keep_mask[global_i]:
                continue

            # Only check posts after this one to avoid double processing
            for j in range(global_i + 1, n_posts):
                if not keep_mask[j]:
                    continue

                sim = similarities[batch_idx, j]
                if sim >= threshold:
                    # Keep the one with earlier timestamp
                    if timestamps[global_i] <= timestamps[j]:
                        keep_mask[j] = False
                    else:
                        keep_mask[global_i] = False
                        break

    # Filter posts
    deduplicated = [p for p, keep in zip(posts, keep_mask) if keep]
    removed_count = n_posts - len(deduplicated)

    logger.info(f"Deduplication: kept {len(deduplicated)}, removed {removed_count}")
    return deduplicated, removed_count


def save_posts(posts: List[Dict[str, Any]], output_path: str):
    """Save posts to JSONL file."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for post in posts:
            # Remove temporary token_count field if present
            post_copy = {k: v for k, v in post.items() if k != "token_count"}
            f.write(json.dumps(post_copy, ensure_ascii=False) + "\n")

    logger.info(f"Saved {len(posts)} posts to {output_path}")


def save_statistics(stats: Dict[str, Any], output_path: str):
    """Save cleaning statistics to JSON file."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved statistics to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Clean and deduplicate VOZ posts")
    parser.add_argument(
        "--from-cassandra",
        action="store_true",
        default=True,
        help="Load data from Cassandra (default: True)"
    )
    parser.add_argument(
        "--input",
        default="data/raw/voz_posts_v1.jsonl",
        help="Input JSONL file path (used if --from-cassandra is False)"
    )
    parser.add_argument(
        "--output",
        default="data/cleaned/voz_posts_cleaned_v1.jsonl",
        help="Output JSONL file path"
    )
    parser.add_argument(
        "--stats",
        default="reports/cleaning_stats_v1.json",
        help="Statistics output file path"
    )
    args = parser.parse_args()

    # Load posts
    if args.from_cassandra:
        logger.info("Loading posts from Cassandra...")
        posts = load_posts_from_cassandra()
        input_source = f"cassandra://{CASSANDRA_HOST}:{CASSANDRA_PORT}/{CASSANDRA_KEYSPACE}.{CASSANDRA_TABLE}"
    else:
        if not os.path.exists(args.input):
            logger.error(f"Input file not found: {args.input}")
            return 1
        posts = load_posts_from_jsonl(args.input)
        input_source = args.input

    original_count = len(posts)

    # Step 1: Token length filtering
    logger.info("Step 1: Token length filtering (20-300 tokens)...")
    posts, removed_by_length = filter_by_token_length(posts)

    # Step 2: Generate embeddings
    logger.info(f"Step 2: Loading embedding model {EMBEDDING_MODEL}...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    embeddings = generate_embeddings(posts, model)

    # Step 3: Semantic deduplication
    logger.info("Step 3: Semantic deduplication (cosine similarity ≥0.90)...")
    posts, removed_by_duplicate = deduplicate_posts(posts, embeddings)

    # Step 4: Save cleaned posts
    logger.info("Step 4: Saving cleaned posts...")
    save_posts(posts, args.output)

    # Step 5: Generate statistics
    final_count = len(posts)
    removal_rate = 1 - (final_count / original_count) if original_count > 0 else 0

    stats = {
        "original_count": original_count,
        "removed_by_length": removed_by_length,
        "removed_by_duplicate": removed_by_duplicate,
        "final_count": final_count,
        "removal_rate": round(removal_rate, 4),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "input_source": input_source,
        "output_file": args.output,
        "config": {
            "min_tokens": MIN_TOKENS,
            "max_tokens": MAX_TOKENS,
            "similarity_threshold": SIMILARITY_THRESHOLD,
            "embedding_model": EMBEDDING_MODEL
        }
    }
    save_statistics(stats, args.stats)

    # Summary
    logger.info("=" * 50)
    logger.info("Data Cleaning Complete!")
    logger.info(f"  Original posts: {original_count}")
    logger.info(f"  Removed by length: {removed_by_length}")
    logger.info(f"  Removed by duplicate: {removed_by_duplicate}")
    logger.info(f"  Final posts: {final_count}")
    logger.info(f"  Removal rate: {removal_rate:.1%}")
    logger.info("=" * 50)

    return 0


if __name__ == "__main__":
    exit(main())
