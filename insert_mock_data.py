#!/usr/bin/env python3
"""Insert mock Vietnamese posts into Cassandra for retrain testing"""

from cassandra.cluster import Cluster
from datetime import datetime, timedelta
import time

# Mock Vietnamese posts for testing
MOCK_POSTS = [
    {
        "text": "Tôi cảm thấy rất lo lắng về công việc, áp lực quá lớn khiến tôi mất ngủ",
        "min_confidence": 0.35
    },
    {
        "text": "Cuộc sống thật tuyệt vời, hôm nay tôi được thăng chức",
        "min_confidence": 0.40
    },
    {
        "text": "Mối quan hệ gia đình của tôi đang gặp nhiều vấn đề",
        "min_confidence": 0.32
    },
    {
        "text": "Tôi đang cảm thấy rất cô đơn và buồn bã",
        "min_confidence": 0.38
    },
    {
        "text": "Công việc khiến tôi căng thẳng nhưng tôi vẫn cố gắng",
        "min_confidence": 0.36
    },
    {
        "text": "Sức khỏe của tôi đang có vấn đề, cần đi khám",
        "min_confidence": 0.41
    },
    {
        "text": "Tình hình tài chính gia đình đang khó khăn",
        "min_confidence": 0.33
    },
    {
        "text": "Tôi cảm thấy rất hạnh phúc với cuộc sống hiện tại",
        "min_confidence": 0.45
    },
    {
        "text": "Lo lắng về tương lai và sự nghiệp",
        "min_confidence": 0.37
    },
    {
        "text": "Áp lực xã hội khiến tôi stress",
        "min_confidence": 0.39
    }
]

def insert_mock_data():
    print("Connecting to Cassandra...")
    cluster = Cluster(['cassandra'])
    session = cluster.connect('reddit_rt')
    
    # Calculate current hour partition (format: YYYY-MM-DD-HH)
    now = datetime.now()
    hour_partition = now.strftime('%Y-%m-%d-%H')
    
    print(f"Current hour partition: {hour_partition}")
    print(f"Inserting {len(MOCK_POSTS)} mock posts...")
    
    insert_query = """
    INSERT INTO classified_posts_by_hour (
        subreddit, hour_partition, created_utc, post_id,
        title, body, author_hash, permalink, kind,
        aspect_sentiments, confidence_scores,
        model_version, processed_ts
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    prepared = session.prepare(insert_query)
    
    # Mock aspect sentiments and confidence scores
    aspects = ['work_stress', 'sleep_quality', 'family', 'loneliness', 'health', 
               'finance', 'social_pressure', 'life_satisfaction', 'anxiety', 'career']
    
    for idx, post in enumerate(MOCK_POSTS):
        post_id = f"mock_vozforums_{now.strftime('%Y%m%d%H%M%S')}_{idx}"
        created_utc = now - timedelta(minutes=idx*5)
        
        # Random sentiments: -1 (negative), 0 (neutral), 1 (positive)
        aspect_sentiments = {asp: (idx % 3) - 1 for asp in aspects}
        confidence_scores = {asp: post["min_confidence"] + (idx * 0.01) for asp in aspects}
        
        session.execute(prepared, (
            'vozforums',
            hour_partition,
            created_utc,
            post_id,
            f"Vietnamese Post {idx+1}",
            post["text"],
            f"user_{idx}_hash",
            f"/post/{post_id}",
            'submission',
            aspect_sentiments,
            confidence_scores,
            'phobert_v1',
            now
        ))
        print(f"  ✓ Inserted post {idx+1}/{len(MOCK_POSTS)}")
    
    # Verify
    count = session.execute(
        f"SELECT COUNT(*) FROM classified_posts_by_hour WHERE subreddit='vozforums' AND hour_partition='{hour_partition}'"
    ).one()[0]
    
    print(f"\n✓ Successfully inserted {count} posts")
    print(f"✓ Hour partition: {hour_partition}")
    print(f"✓ Ready for retrain pipeline!")
    
    cluster.shutdown()

if __name__ == "__main__":
    # Wait for Cassandra to be ready
    print("Waiting for Cassandra...")
    time.sleep(5)
    
    try:
        insert_mock_data()
    except Exception as e:
        print(f"Error: {e}")
        exit(1)
