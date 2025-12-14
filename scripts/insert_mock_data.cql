-- Insert mock Vietnamese mental health posts for testing retrain pipeline
-- These posts have LOW confidence scores to trigger retrain

-- Post 1: Stress về công việc
INSERT INTO reddit_rt.classified_posts_by_hour (
    subreddit, hour_partition, created_utc, post_id, 
    author_hash, body, kind, model_version, 
    aspect_sentiments, confidence_scores, processed_ts
) VALUES (
    'vozforums', '2025-12-10-09', '2025-12-10 09:00:00', 'mock_post_1',
    'mock_user_1', 'Hôm nay mình stress quá, công việc nhiều deadline quá mệt mỏi', 
    'submission', 'mock_v1',
    {'công_việc': -1, 'căng_thẳng_tài_chính': 0, 'thiếu_năng_lượng': -1},
    {'công_việc': 0.45, 'căng_thẳng_tài_chính': 0.30, 'thiếu_năng_lượng': 0.42},
    toTimestamp(now())
);

-- Post 2: Trầm cảm
INSERT INTO reddit_rt.classified_posts_by_hour (
    subreddit, hour_partition, created_utc, post_id, 
    author_hash, body, kind, model_version, 
    aspect_sentiments, confidence_scores, processed_ts
) VALUES (
    'vozforums', '2025-12-10-09', '2025-12-10 08:50:00', 'mock_post_2',
    'mock_user_2', 'Mình cảm thấy trầm cảm, không muốn làm gì cả, chỉ muốn nằm một chỗ', 
    'submission', 'mock_v1',
    {'trầm_cảm': -1, 'thiếu_năng_lượng': -1, 'tự_suy_ngẫm': -1},
    {'trầm_cảm': 0.38, 'thiếu_năng_lượng': 0.41, 'tự_suy_ngẫm': 0.35},
    toTimestamp(now())
);

-- Post 3: Vấn đề giấc ngủ
INSERT INTO reddit_rt.classified_posts_by_hour (
    subreddit, hour_partition, created_utc, post_id, 
    author_hash, body, kind, model_version, 
    aspect_sentiments, confidence_scores, processed_ts
) VALUES (
    'vozforums', '2025-12-10-09', '2025-12-10 08:40:00', 'mock_post_3',
    'mock_user_3', 'Giấc ngủ mình rất tệ, mỗi đêm chỉ ngủ được 3-4 tiếng, uống thuốc cũng không giúp được', 
    'submission', 'mock_v1',
    {'giấc_ngủ_thuốc': -1, 'trầm_cảm': -1},
    {'giấc_ngủ_thuốc': 0.40, 'trầm_cảm': 0.33},
    toTimestamp(now())
);

-- Post 4: Vấn đề gia đình
INSERT INTO reddit_rt.classified_posts_by_hour (
    subreddit, hour_partition, created_utc, post_id, 
    author_hash, body, kind, model_version, 
    aspect_sentiments, confidence_scores, processed_ts
) VALUES (
    'vozforums', '2025-12-10-09', '2025-12-10 08:30:00', 'mock_post_4',
    'mock_user_4', 'Gia đình mình không hiểu mình, cảm thấy cô đơn trong chính nhà của mình', 
    'submission', 'mock_v1',
    {'gia_đình': -1, 'giao_tiếp': -1, 'trầm_cảm': -1},
    {'gia_đình': 0.44, 'giao_tiếp': 0.37, 'trầm_cảm': 0.39},
    toTimestamp(now())
);

-- Post 5: Tình yêu tan vỡ
INSERT INTO reddit_rt.classified_posts_by_hour (
    subreddit, hour_partition, created_utc, post_id, 
    author_hash, body, kind, model_version, 
    aspect_sentiments, confidence_scores, processed_ts
) VALUES (
    'vozforums', '2025-12-10-09', '2025-12-10 08:20:00', 'mock_post_5',
    'mock_user_5', 'Tình yêu của mình tan vỡ, cảm thấy cuộc sống không còn ý nghĩa', 
    'submission', 'mock_v1',
    {'tình_yêu': -1, 'trầm_cảm': -1, 'tự_suy_ngẫm': -1},
    {'tình_yêu': 0.36, 'trầm_cảm': 0.43, 'tự_suy_ngẫm': 0.40},
    toTimestamp(now())
);

-- Post 6: Tìm kiếm giúp đỡ
INSERT INTO reddit_rt.classified_posts_by_hour (
    subreddit, hour_partition, created_utc, post_id, 
    author_hash, body, kind, model_version, 
    aspect_sentiments, confidence_scores, processed_ts
) VALUES (
    'vozforums', '2025-12-10-09', '2025-12-10 08:10:00', 'mock_post_6',
    'mock_user_6', 'Mình muốn tìm người để nói chuyện, cần ai đó giúp đỡ về tâm lý', 
    'submission', 'mock_v1',
    {'tìm_kiếm_giúp_đỡ': 1, 'giao_tiếp': 0},
    {'tìm_kiếm_giúp_đỡ': 0.47, 'giao_tiếp': 0.32},
    toTimestamp(now())
);

-- Post 7: Tích cực (high confidence - sẽ không được chọn để retrain)
INSERT INTO reddit_rt.classified_posts_by_hour (
    subreddit, hour_partition, created_utc, post_id, 
    author_hash, body, kind, model_version, 
    aspect_sentiments, confidence_scores, processed_ts
) VALUES (
    'vozforums', '2025-12-10-09', '2025-12-10 08:00:00', 'mock_post_7',
    'mock_user_7', 'Công việc ổn định, cuộc sống cũng tạm được, không có gì phàn nàn', 
    'submission', 'mock_v1',
    {'công_việc': 1, 'căng_thẳng_tài_chính': 0},
    {'công_việc': 0.88, 'căng_thẳng_tài_chính': 0.75},
    toTimestamp(now())
);

-- Post 8: Học cách quản lý stress (high confidence)
INSERT INTO reddit_rt.classified_posts_by_hour (
    subreddit, hour_partition, created_utc, post_id, 
    author_hash, body, kind, model_version, 
    aspect_sentiments, confidence_scores, processed_ts
) VALUES (
    'vozforums', '2025-12-10-09', '2025-12-10 07:50:00', 'mock_post_8',
    'mock_user_8', 'Hôm nay mình học được cách quản lý stress, cảm thấy tốt hơn nhiều', 
    'submission', 'mock_v1',
    {'tự_suy_ngẫm': 1, 'tìm_kiếm_giúp_đỡ': 1},
    {'tự_suy_ngẫm': 0.82, 'tìm_kiếm_giúp_đỡ': 0.79},
    toTimestamp(now())
);

-- Post 9: Căng thẳng tài chính
INSERT INTO reddit_rt.classified_posts_by_hour (
    subreddit, hour_partition, created_utc, post_id, 
    author_hash, body, kind, model_version, 
    aspect_sentiments, confidence_scores, processed_ts
) VALUES (
    'vozforums', '2025-12-10-09', '2025-12-10 07:40:00', 'mock_post_9',
    'mock_user_9', 'Tiền bạc khó khăn quá, không biết làm sao để chi trả các khoản nợ', 
    'submission', 'mock_v1',
    {'căng_thẳng_tài_chính': -1, 'công_việc': -1},
    {'căng_thẳng_tài_chính': 0.39, 'công_việc': 0.34},
    toTimestamp(now())
);

-- Post 10: Mất ngủ, kiệt sức
INSERT INTO reddit_rt.classified_posts_by_hour (
    subreddit, hour_partition, created_utc, post_id, 
    author_hash, body, kind, model_version, 
    aspect_sentiments, confidence_scores, processed_ts
) VALUES (
    'vozforums', '2025-12-10-09', '2025-12-10 07:30:00', 'mock_post_10',
    'mock_user_10', 'Mình mất ngủ liên tục, cảm thấy kiệt sức, không có năng lượng làm gì', 
    'submission', 'mock_v1',
    {'giấc_ngủ_thuốc': -1, 'thiếu_năng_lượng': -1},
    {'giấc_ngủ_thuốc': 0.41, 'thiếu_năng_lượng': 0.44},
    toTimestamp(now())
);
