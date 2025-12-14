"""
Insert mock Vietnamese mental health posts into Cassandra
For testing retrain pipeline without needing Spark
"""

from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from datetime import datetime, timedelta
import uuid

# Mock Vietnamese mental health posts
MOCK_POSTS = [
    {
        "body": "Hôm nay mình stress quá, công việc nhiều deadline quá mệt mỏi",
        "aspects": {"công_việc": -1, "căng_thẳng_tài_chính": 0, "thiếu_năng_lượng": -1},
        "confidence": {"công_việc": 0.45, "căng_thẳng_tài_chính": 0.3, "thiếu_năng_lượng": 0.42}
    },
    {
        "body": "Mình cảm thấy trầm cảm, không muốn làm gì cả, chỉ muốn nằm một chỗ",
        "aspects": {"trầm_cảm": -1, "thiếu_năng_lượng": -1, "tự_suy_ngẫm": -1},
        "confidence": {"trầm_cảm": 0.38, "thiếu_năng_lượng": 0.41, "tự_suy_ngẫm": 0.35}
    },
    {
        "body": "Giấc ngủ mình rất tệ, mỗi đêm chỉ ngủ được 3-4 tiếng, uống thuốc cũng không giúp được",
        "aspects": {"giấc_ngủ_thuốc": -1, "trầm_cảm": -1},
        "confidence": {"giấc_ngủ_thuốc": 0.40, "trầm_cảm": 0.33}
    },
    {
        "body": "Gia đình mình không hiểu mình, cảm thấy cô đơn trong chính nhà của mình",
        "aspects": {"gia_đình": -1, "giao_tiếp": -1, "trầm_cảm": -1},
        "confidence": {"gia_đình": 0.44, "giao_tiếp": 0.37, "trầm_cảm": 0.39}
    },
    {
        "body": "Tình yêu của mình tan vỡ, cảm thấy cuộc sống không còn ý nghĩa",
        "aspects": {"tình_yêu": -1, "trầm_cảm": -1, "tự_suy_ngẫm": -1},
        "confidence": {"tình_yêu": 0.36, "trầm_cảm": 0.43, "tự_suy_ngẫm": 0.40}
    },
    {
        "body": "Mình muốn tìm người để nói chuyện, cần ai đó giúp đỡ về tâm lý",
        "aspects": {"tìm_kiếm_giúp_đỡ": 1, "giao_tiếp": 0},
        "confidence": {"tìm_kiếm_giúp_đỡ": 0.47, "giao_tiếp": 0.32}
    },
    {
        "body": "Công việc ổn định, cuộc sống cũng tạm được, không có gì phàn nàn",
        "aspects": {"công_việc": 1, "căng_thẳng_tài_chính": 0},
        "confidence": {"công_việc": 0.88, "căng_thẳng_tài_chính": 0.75}
    },
    {
        "body": "Hôm nay mình học được cách quản lý stress, cảm thấy tốt hơn nhiều",
        "aspects": {"tự_suy_ngẫm": 1, "tìm_kiếm_giúp_đỡ": 1},
        "confidence": {"tự_suy_ngẫm": 0.82, "tìm_kiếm_giúp_đỡ": 0.79}
    },
    {
        "body": "Tiền bạc khó khăn quá, không biết làm sao để chi trả các khoản nợ",
        "aspects": {"căng_thẳng_tài_chính": -1, "công_việc": -1},
        "confidence": {"căng_thẳng_tài_chính": 0.39, "công_việc": 0.34}
    },
    {
        "body": "Mình mất ngủ liên tục, cảm thấy kiệt sức, không có năng lượng làm gì",
        "aspects": {"giấc_ngủ_thuốc": -1, "thiếu_năng_lượng": -1},
        "confidence": {"giấc_ngủ_thuốc": 0.41, "thiếu_năng_lượng": 0.44}
    }
]

def insert_mock_data():
    """Insert mock posts into Cassandra"""
    
    # Connect to Cassandra
    print("Connecting to Cassandra...")
    cluster = Cluster(['localhost'], port=9042)
    session = cluster.connect('reddit_rt')
    
    # Prepare insert statement
    insert_stmt = session.prepare("""
        INSERT INTO classified_posts_by_hour (
            subreddit, hour_partition, created_utc, post_id,
            author_hash, body, kind, model_version,
            aspect_sentiments, confidence_scores,
            processed_ts
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """)
    
    # Get current time
    now = datetime.utcnow()
    hour_partition = now.strftime('%Y-%m-%d-%H')
    
    print(f"\nInserting {len(MOCK_POSTS)} mock posts...")
    
    for i, post in enumerate(MOCK_POSTS, 1):
        post_id = f"mock_post_{uuid.uuid4().hex[:8]}"
        created_time = now - timedelta(minutes=i*10)
        
        session.execute(insert_stmt, (
            'vozforums',
            hour_partition,
            created_time,
            post_id,
            f'mock_user_{i}',
            post['body'],
            'submission',
            'mock_v1',
            post['aspects'],
            post['confidence'],
            now
        ))
        
        print(f"  ✓ Inserted post {i}: {post['body'][:50]}...")
    
    # Verify
    count = session.execute(
        "SELECT COUNT(*) FROM classified_posts_by_hour WHERE subreddit = 'vozforums' ALLOW FILTERING"
    ).one()[0]
    
    print(f"\n✓ Successfully inserted {count} posts into Cassandra")
    print(f"  Hour partition: {hour_partition}")
    print(f"  Subreddit: vozforums")
    
    cluster.shutdown()

if __name__ == '__main__':
    insert_mock_data()
