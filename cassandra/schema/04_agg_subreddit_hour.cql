-- ============================================================================
-- Table: agg_subreddit_hour
-- Description: Hourly aggregated metrics per subreddit for dashboard consumption
--              Pre-computed statistics for fast dashboard queries
-- ============================================================================

USE reddit_rt;

-- Subreddit hourly aggregates table
-- Partition key: (subreddit, hour_partition) - one row per subreddit per hour
-- No clustering keys needed - single row per partition
-- TTL: 180 days (6 months retention for trend analysis)
CREATE TABLE IF NOT EXISTS agg_subreddit_hour (
    -- Composite partition key: subreddit + hour
    subreddit text,
    hour_partition text,    -- Format: YYYY-MM-DD-HH

    -- Temporal anchor
    hour_start timestamp,   -- Start of the hour (for time-series plotting)

    -- Aggregate metrics
    total_cnt int,          -- Total posts in this hour
    stress_cnt int,         -- Number of posts classified as stressed
    avg_score float,        -- Average stress score across all posts
    pct_stress float,       -- Percentage of stressed posts (0.0 - 100.0)

    -- Metadata
    last_updated timestamp, -- When this aggregate was last updated

    PRIMARY KEY ((subreddit, hour_partition))
) WITH default_time_to_live = 15552000  -- 180 days in seconds
  AND compaction = {
    'class': 'SizeTieredCompactionStrategy'
  }
  AND compression = {
    'class': 'LZ4Compressor'
  }
  AND comment = 'Hourly aggregated metrics per subreddit with 180-day TTL';

-- Design rationale:
-- 1. Composite partition key (subreddit, hour_partition):
--    - One row per subreddit per hour
--    - No clustering keys needed (single aggregate value)
--    - Efficient point lookups for dashboard
--    - Natural partitioning for time-series queries
--
-- 2. No clustering columns:
--    - Single row per partition (pre-aggregated data)
--    - Simple upsert pattern for updates
--    - Minimal storage overhead
--
-- 3. TTL = 180 days: Long-term trend storage
--    - Longer than classified posts (90 days)
--    - Supports 6-month trend analysis
--    - Aggregates are compact (low storage cost)
--
-- 4. SizeTieredCompactionStrategy:
--    - Better for tables with updates (vs TimeWindowCompactionStrategy)
--    - Aggregates may be updated as data arrives
--    - Less frequent compaction than TWCS
--
-- 5. Aggregate metrics design:
--    - total_cnt: Total posts (denominator for percentages)
--    - stress_cnt: Numerator for stress percentage
--    - avg_score: Mean stress score (for threshold analysis)
--    - pct_stress: Pre-computed percentage (fast dashboard display)
--
-- Query patterns supported:
-- - Get hourly stats for subreddit X at hour Y
-- - Time-series of stress trends for a subreddit
-- - Compare stress levels across hours
--
-- Update pattern:
-- - Upsert on each batch processing window
-- - Idempotent updates (can reprocess same hour)
