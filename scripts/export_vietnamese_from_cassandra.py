#!/usr/bin/env python3
"""
Export Vietnamese posts from Cassandra to CSV for labeling and training.

Usage:
    python scripts/export_vietnamese_from_cassandra.py

Output:
    ml/dataset/raw/vietnamese_posts.csv
"""

import os
import sys
import csv
from datetime import datetime, timedelta
from collections import defaultdict

# Fix for Python 3.12+ compatibility with cassandra-driver
try:
    from cassandra.cluster import Cluster
    from cassandra.auth import PlainTextAuthProvider
except Exception as e:
    print(f"Error importing cassandra-driver: {e}")
    print("\nInstalling compatible cassandra-driver...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "-U", "cassandra-driver[eventlet]"], check=True)
    from cassandra.cluster import Cluster
    from cassandra.auth import PlainTextAuthProvider

# Cassandra connection settings
CASSANDRA_HOST = os.getenv('CASSANDRA_HOST', 'localhost')
CASSANDRA_PORT = int(os.getenv('CASSANDRA_PORT', '9042'))
CASSANDRA_KEYSPACE = 'reddit_rt'

# Output settings
OUTPUT_DIR = 'ml/dataset/raw'
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'vietnamese_posts.csv')

# Vietnamese keywords for filtering (from vietnamese_keywords.py)
VIETNAMESE_STRESS_KEYWORDS = [
    'stress', 'áp lực', 'căng thẳng', 'lo âu', 'anxiety', 'depression',
    'trầm cảm', 'suy sụp', 'mệt mỏi', 'exhausted', 'burnout', 'kiệt sức',
    'overthinking', 'suy nghĩ quá nhiều', 'insomnia', 'mất ngủ',
    'mental health', 'sức khỏe tinh thần', 'tâm lý', 'psychology',
    'therapy', 'trị liệu', 'counseling', 'tư vấn', 'pressure', 'deadlines'
]

VIETNAMESE_NON_STRESS_KEYWORDS = [
    'happy', 'vui vẻ', 'hạnh phúc', 'relaxed', 'thư giãn', 'calm', 'bình tĩnh',
    'peaceful', 'yên bình', 'motivated', 'động lực', 'excited', 'phấn khích',
    'grateful', 'biết ơn', 'optimistic', 'lạc quan', 'confident', 'tự tin',
    'proud', 'tự hào', 'accomplished', 'thành công', 'balanced', 'cân bằng',
    'healthy', 'khỏe mạnh', 'energetic', 'tràn đầy năng lượng'
]

def connect_to_cassandra():
    """Connect to Cassandra cluster."""
    print(f"Connecting to Cassandra at {CASSANDRA_HOST}:{CASSANDRA_PORT}...")

    # Use eventlet event loop for Python 3.12+ compatibility
    try:
        from cassandra.io.eventletreactor import EventletConnection
        cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT, connection_class=EventletConnection)
    except ImportError:
        # Fallback to default if eventlet not available
        cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT)

    session = cluster.connect(CASSANDRA_KEYSPACE)
    print(f"Connected to keyspace: {CASSANDRA_KEYSPACE}")
    return cluster, session

def get_date_partitions(days_back=14):
    """Generate date partition strings for the last N days."""
    partitions = []
    today = datetime.now().date()
    for i in range(days_back):
        date = today - timedelta(days=i)
        partitions.append(date.strftime('%Y-%m-%d'))
    return partitions

def export_vietnamese_posts(session):
    """Export Vietnamese posts from Cassandra to CSV."""

    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Get date partitions to query
    partitions = get_date_partitions(days_back=14)
    print(f"Querying {len(partitions)} date partitions: {partitions[0]} to {partitions[-1]}")

    # Prepare query statement
    from cassandra.query import SimpleStatement
    query = SimpleStatement("""
        SELECT post_id, title, body, subreddit, created_utc, permalink,
               search_category, source, kind
        FROM raw_posts_by_day
        WHERE date_partition = %s
    """)

    posts = {}  # Deduplicate by post_id
    total_queried = 0

    for partition in partitions:
        print(f"Querying partition {partition}...", end=' ')
        rows = session.execute(query, (partition,))

        partition_count = 0
        for row in rows:
            total_queried += 1
            post_id = row.post_id

            # Deduplicate
            if post_id in posts:
                continue

            # Filter for Vietnamese posts (check search_category contains Vietnamese keywords)
            search_category = row.search_category or ''

            # Check if any Vietnamese keyword is in search_category
            is_vietnamese = any(
                keyword.lower() in search_category.lower()
                for keyword in VIETNAMESE_STRESS_KEYWORDS + VIETNAMESE_NON_STRESS_KEYWORDS
            )

            if is_vietnamese:
                posts[post_id] = {
                    'post_id': post_id,
                    'title': row.title or '',
                    'body': row.body or '',
                    'subreddit': row.subreddit or '',
                    'created_utc': row.created_utc,
                    'permalink': row.permalink or '',
                    'search_category': search_category,
                    'source': row.source or '',
                    'kind': row.kind or ''
                }
                partition_count += 1

        print(f"Found {partition_count} Vietnamese posts")

    print(f"\nTotal rows queried: {total_queried}")
    print(f"Unique Vietnamese posts found: {len(posts)}")

    # Write to CSV
    if not posts:
        print("No Vietnamese posts found! Check if collection script ran successfully.")
        return

    print(f"\nWriting to {OUTPUT_FILE}...")

    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['post_id', 'title', 'body', 'subreddit', 'created_utc',
                     'permalink', 'search_category', 'source', 'kind']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for post in posts.values():
            writer.writerow(post)

    print(f"✓ Exported {len(posts)} Vietnamese posts to {OUTPUT_FILE}")

    # Print statistics
    print("\n=== Export Statistics ===")
    print(f"Total unique posts: {len(posts)}")

    # Count by subreddit
    subreddit_counts = defaultdict(int)
    for post in posts.values():
        subreddit_counts[post['subreddit']] += 1

    print("\nTop subreddits:")
    for subreddit, count in sorted(subreddit_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {subreddit}: {count}")

    # Count by search category (stress vs non-stress keywords)
    stress_count = 0
    non_stress_count = 0
    for post in posts.values():
        category = post['search_category'].lower()
        if any(kw.lower() in category for kw in VIETNAMESE_STRESS_KEYWORDS):
            stress_count += 1
        if any(kw.lower() in category for kw in VIETNAMESE_NON_STRESS_KEYWORDS):
            non_stress_count += 1

    print(f"\nBy search category:")
    print(f"  Stress-related keywords: {stress_count}")
    print(f"  Non-stress keywords: {non_stress_count}")
    print(f"  Overlap (both): {stress_count + non_stress_count - len(posts)}")

    return len(posts)

def main():
    """Main execution function."""
    print("=" * 60)
    print("Vietnamese Posts Export from Cassandra")
    print("=" * 60)
    print()

    cluster = None
    try:
        # Connect to Cassandra
        cluster, session = connect_to_cassandra()

        # Export posts
        count = export_vietnamese_posts(session)

        if count and count > 0:
            print("\n" + "=" * 60)
            print("✓ Export completed successfully!")
            print("=" * 60)
            print(f"\nNext steps:")
            print(f"  1. Review the exported data: cat {OUTPUT_FILE}")
            print(f"  2. Run Ollama labeling: python ml/dataset/label_vietnamese_with_ollama.py")
            return 0
        else:
            print("\n" + "=" * 60)
            print("⚠ No Vietnamese posts found!")
            print("=" * 60)
            print("\nTroubleshooting:")
            print("  1. Check if collection script ran: ./collect_vietnamese_data.sh")
            print("  2. Verify Cassandra has data: docker exec -it reddit-cassandra cqlsh")
            print("  3. Check search_category field contains Vietnamese keywords")
            return 1

    except Exception as e:
        print(f"\n✗ Error during export: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        if cluster:
            cluster.shutdown()
            print("\nCassandra connection closed.")

if __name__ == '__main__':
    sys.exit(main())
