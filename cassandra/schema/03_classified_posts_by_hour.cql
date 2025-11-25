-- ============================================================================
-- Table: classified_posts_by_hour
-- Description: Stores ABSA ML-classified posts partitioned by subreddit and hour
--              Multi-label aspect-based sentiment analysis for Vietnamese mental health
-- ============================================================================

USE reddit_rt;

-- ABSA classified posts table partitioned by subreddit and hour
-- Partition key: (subreddit, hour_partition) - enables per-subreddit + time queries
-- Clustering keys: created_utc DESC, post_id (chronological ordering)
-- TTL: 90 days (longer retention for analytical data)
CREATE TABLE IF NOT EXISTS classified_posts_by_hour (
    -- Composite partition key: subreddit + hour
    subreddit text,
    hour_partition text,    -- Format: YYYY-MM-DD-HH

    -- Clustering keys: order by post creation time (newest first), then by post_id
    created_utc timestamp,
    post_id text,

    -- Post metadata
    kind text,

    -- Content fields
    title text,
    body text,

    -- Author information (hashed for privacy)
    author_hash text,
    permalink text,

    -- ABSA ML classification results
    aspect_sentiments map<text, int>,  -- Aspect → Sentiment mapping (aspect_name → -1/0/1)
    model_version text,                -- Model version for tracking

    -- Processing metadata
    processed_ts timestamp,  -- When ML inference completed

    PRIMARY KEY ((subreddit, hour_partition), created_utc, post_id)
) WITH CLUSTERING ORDER BY (created_utc DESC, post_id ASC)
  AND default_time_to_live = 7776000  -- 90 days in seconds
  AND compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_size': '1',
    'compaction_window_unit': 'HOURS'
  }
  AND compression = {
    'class': 'LZ4Compressor'
  }
  AND comment = 'ABSA multi-label classified posts partitioned by subreddit and hour with 90-day TTL';

-- Design rationale:
-- 1. Composite partition key (subreddit, hour_partition):
--    - Enables efficient per-subreddit queries
--    - Balances load across multiple partitions
--    - Hourly granularity matches aggregation needs
--    - Prevents hot partitions from popular subreddits
--
-- 2. Clustering by created_utc DESC: Posts ordered by creation time
--    - created_utc = original Reddit post time (not processing time)
--    - Most recent posts appear first
--    - Efficient for dashboard queries
--
-- 3. TTL = 90 days: Extended retention for analytics
--    - Longer than raw data (14 days)
--    - Supports historical trend analysis
--    - Balances storage cost vs analytical value
--
-- 4. TimeWindowCompactionStrategy (1 hour windows):
--    - Matches partition granularity
--    - Optimized for time-series queries
--    - Efficient TTL-based expiration
--
-- 5. ABSA classification fields:
--    - aspect_sentiments: Map of aspect_name → sentiment (-1=negative, 0=neutral, 1=positive)
--      Example: {'công_việc': -1, 'tình_yêu': -1, 'sức_khỏe': 0}
--    - model_version: Tracks PhoBERT ABSA model version
--
-- Query patterns supported:
-- - Get all posts with negative aspects in subreddit X during hour Y
-- - Get latest N posts for subreddit X
-- - Filter by specific aspect presence (e.g., WHERE aspect_sentiments CONTAINS KEY 'công_việc')
