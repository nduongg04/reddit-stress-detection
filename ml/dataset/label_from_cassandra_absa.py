#!/usr/bin/env python3
"""
Label Vietnamese posts from Cassandra with ABSA sentiment (-1, 0, 1)

Flow:
1. Fetch raw Vietnamese posts from Cassandra
2. For each post, detect aspects
3. For each detected aspect, get sentiment (-1, 0, 1)
4. Save to CSV with aspect labels and sentiments

Output: vozforums_absa_from_cassandra.csv
"""

import os
import sys
import json
import subprocess
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import time

# Cassandra connection
try:
    from cassandra.cluster import Cluster
    from cassandra.io.eventletreactor import EventletConnection
except Exception as e:
    print(f"Installing cassandra-driver...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-U", "cassandra-driver[eventlet]"], check=True)
    from cassandra.cluster import Cluster
    from cassandra.io.eventletreactor import EventletConnection

# Thread-safe progress
progress_lock = Lock()
progress_count = 0


def log(message):
    """Thread-safe logging"""
    with progress_lock:
        print(message, flush=True)


def load_aspects(file='ml/lda/absa_mental_health_aspects.json'):
    """Load ABSA aspects"""
    with open(file, 'r', encoding='utf-8') as f:
        return json.load(f)['aspects']


def fetch_vietnamese_posts(limit=500):
    """Fetch raw Vietnamese posts from Cassandra"""
    log("Connecting to Cassandra...")

    try:
        cluster = Cluster(['localhost'], port=9042, connection_class=EventletConnection)
    except:
        cluster = Cluster(['localhost'], port=9042)

    session = cluster.connect('reddit_rt')
    log("Connected to Cassandra (keyspace: reddit_rt)")

    # Query recent posts (last 14 days)
    from datetime import datetime, timedelta
    from cassandra.query import SimpleStatement

    today = datetime.now().date()
    posts = []

    for i in range(14):
        date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
        query = SimpleStatement("""
            SELECT post_id, title, body, subreddit, created_utc
            FROM raw_posts_by_day
            WHERE date_partition = %s
        """)

        rows = session.execute(query, (date,))
        for row in rows:
            # Combine title + body
            text = f"{row.title or ''}\n{row.body or ''}".strip()
            if text and len(text) > 20:  # Skip empty posts
                posts.append({
                    'post_id': row.post_id,
                    'text': text,
                    'subreddit': row.subreddit or 'unknown',
                    'created_utc': row.created_utc
                })

            if len(posts) >= limit:
                break

        if len(posts) >= limit:
            break

    cluster.shutdown()
    log(f"Fetched {len(posts)} posts from Cassandra")
    return posts


def create_aspect_prompt(text: str, aspect: str) -> str:
    """Prompt for aspect detection"""
    return f"""Does this text mention "{aspect}"? Reply ONLY 0 (no) or 1 (yes).

Text: {text[:300]}

Reply: """


def create_sentiment_prompt(text: str, aspect: str) -> str:
    """Prompt for sentiment"""
    return f"""Sentiment of "{aspect}" in this text? Reply ONLY -1 (negative), 0 (neutral), or 1 (positive).

Text: {text[:300]}

Reply: """


def call_ollama(prompt: str) -> int:
    """Call Ollama with timeout"""
    try:
        result = subprocess.run(
            ['ollama', 'run', 'llama3.1:8b'],
            input=prompt.encode('utf-8'),
            capture_output=True,
            timeout=30
        )

        output = result.stdout.decode('utf-8').strip()

        # Extract number from first line
        first_line = output.split('\n')[0].strip()
        if '-1' in first_line[:5]:
            return -1
        elif '1' in first_line[:5]:
            return 1
        else:
            return 0

    except Exception as e:
        log(f"  Ollama error: {e}")
        return 0


def label_post(post: dict, aspects: list, idx: int, total: int) -> dict:
    """Label a single post with aspects and sentiments"""
    global progress_count

    text = post['text']
    result = {
        'post_id': post['post_id'],
        'text': text,
        'subreddit': post['subreddit'],
        'created_utc': post['created_utc']
    }

    # Detect aspects
    for i, aspect in enumerate(aspects):
        aspect_name = aspect['aspect_name']

        # 1. Detect aspect
        aspect_prompt = create_aspect_prompt(text, aspect_name)
        label = call_ollama(aspect_prompt)

        result[f'label_{i}_{aspect_name}'] = label

        # 2. Get sentiment if aspect detected
        if label == 1:
            sentiment_prompt = create_sentiment_prompt(text, aspect_name)
            sentiment = call_ollama(sentiment_prompt)
            result[f'sentiment_{i}_{aspect_name}'] = sentiment
        else:
            result[f'sentiment_{i}_{aspect_name}'] = 0

    # Progress
    with progress_lock:
        progress_count += 1
        log(f"✓ [{progress_count}/{total}] Post {post['post_id'][:8]}... labeled")

    return result


def main():
    global progress_count

    log("="*70)
    log("ABSA LABELING FROM CASSANDRA")
    log("="*70)

    # Load aspects
    log("\n1. Loading aspects...")
    aspects = load_aspects()
    log(f"   Loaded {len(aspects)} aspects")

    # Fetch posts from Cassandra
    log("\n2. Fetching posts from Cassandra...")
    posts = fetch_vietnamese_posts(limit=500)

    if not posts:
        log("✗ No posts found in Cassandra!")
        return

    # Configuration
    max_workers = 2  # Conservative for Ollama
    log(f"\n3. Configuration:")
    log(f"   Posts to label: {len(posts)}")
    log(f"   Workers: {max_workers}")
    log(f"   Aspects per post: {len(aspects)}")
    log(f"   Estimated time: ~{len(posts) * len(aspects) * 30 / max_workers / 60:.0f} minutes")

    # Label in parallel
    log(f"\n4. Labeling posts...")
    start_time = time.time()
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(label_post, post, aspects, i, len(posts)): i
            for i, post in enumerate(posts)
        }

        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                idx = futures[future]
                log(f"✗ Error at post {idx}: {e}")

    # Save to CSV
    log(f"\n5. Saving results...")
    df = pd.DataFrame(results)

    # Sort columns
    base_cols = ['post_id', 'text', 'subreddit', 'created_utc']
    aspect_cols = [col for col in df.columns if col not in base_cols]
    df = df[base_cols + sorted(aspect_cols)]

    output_file = 'ml/dataset/labeled/vozforums_absa_from_cassandra.csv'
    os.makedirs('ml/dataset/labeled', exist_ok=True)
    df.to_csv(output_file, index=False)

    elapsed = time.time() - start_time

    log(f"\n{'='*70}")
    log("LABELING COMPLETE")
    log("="*70)
    log(f"✓ Labeled: {len(df)} posts")
    log(f"✓ Time: {elapsed/60:.1f} minutes")
    log(f"✓ Output: {output_file}")

    # Show statistics
    log(f"\nASPECT STATISTICS:")
    for i, aspect in enumerate(aspects):
        label_col = f'label_{i}_{aspect["aspect_name"]}'
        sentiment_col = f'sentiment_{i}_{aspect["aspect_name"]}'

        if label_col in df.columns:
            detected = df[label_col].sum()
            if detected > 0:
                sentiments = df[df[label_col] == 1][sentiment_col].value_counts().to_dict()
                log(f"\n{aspect['aspect_name']}: {int(detected)} posts")
                log(f"  Negative: {sentiments.get(-1, 0)}")
                log(f"  Neutral: {sentiments.get(0, 0)}")
                log(f"  Positive: {sentiments.get(1, 0)}")


if __name__ == "__main__":
    main()
