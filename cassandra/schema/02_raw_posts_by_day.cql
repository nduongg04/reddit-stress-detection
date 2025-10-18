-- ============================================================================
-- Table: raw_posts_by_day
-- Description: Stores raw Reddit posts partitioned by date for efficient
--              time-series queries. Optimized for write-heavy workload.
-- ============================================================================

USE reddit_rt;

-- Raw posts table partitioned by day
-- Partition key: date_partition (YYYY-MM-DD format)
-- Clustering keys: ingest_ts DESC, post_id (for deduplication and ordering)
-- TTL: 14 days (automatic deletion of old data)
CREATE TABLE IF NOT EXISTS raw_posts_by_day (
    -- Partition key: groups posts by day
    date_partition text,

    -- Clustering keys: order by ingestion time (newest first), then by post_id
    ingest_ts timestamp,
    post_id text,

    -- Post metadata
    kind text,              -- 't1' (comment) or 't3' (post)
    subreddit text,

    -- Content fields
    title text,
    body text,

    -- Temporal data
    created_utc timestamp,  -- Original Reddit creation time

    -- Author information (hashed for privacy)
    author_hash text,

    -- Reference data
    permalink text,
    source text,            -- 'live' or 'backfill'

    PRIMARY KEY (date_partition, ingest_ts, post_id)
) WITH CLUSTERING ORDER BY (ingest_ts DESC, post_id ASC)
  AND default_time_to_live = 1209600  -- 14 days in seconds
  AND compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_size': '1',
    'compaction_window_unit': 'DAYS'
  }
  AND compression = {
    'class': 'LZ4Compressor'
  }
  AND comment = 'Raw Reddit posts partitioned by day with 14-day TTL';

-- Design rationale:
-- 1. Partition by date (YYYY-MM-DD): Natural time-series partitioning
--    - Ensures even data distribution
--    - Limits partition size (one day of data per partition)
--    - Enables efficient time-range queries
--
-- 2. Clustering by ingest_ts DESC: Most recent posts first
--    - Optimizes queries for latest posts
--    - Efficient for real-time monitoring
--
-- 3. TTL = 14 days: Automatic data cleanup
--    - Prevents unbounded growth
--    - Raw data only needed for short-term analysis
--    - Processed data stored separately with longer retention
--
-- 4. TimeWindowCompactionStrategy: Optimized for time-series
--    - Groups data by time windows (1 day)
--    - Efficient for TTL expiration
--    - Minimizes compaction overhead
--
-- 5. LZ4 Compression: Fast compression for high-throughput writes
--    - Lower CPU overhead than other algorithms
--    - Good compression ratio for text data
