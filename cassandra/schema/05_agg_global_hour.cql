-- ============================================================================
-- Table: agg_global_hour
-- Description: Platform-wide hourly aggregated metrics across all subreddits
--              Global stress trends for high-level dashboard views
-- ============================================================================

USE reddit_rt;

-- Global hourly aggregates table
-- Partition key: hour_partition (single global aggregate per hour)
-- No clustering keys needed - single row per hour
-- TTL: 180 days (6 months retention for long-term trend analysis)
CREATE TABLE IF NOT EXISTS agg_global_hour (
    -- Partition key: hour only (global aggregate)
    hour_partition text,    -- Format: YYYY-MM-DD-HH

    -- Temporal anchor
    hour_start timestamp,   -- Start of the hour (for time-series plotting)

    -- Aggregate metrics
    total_cnt int,          -- Total posts across all subreddits in this hour
    stress_cnt int,         -- Number of posts classified as stressed
    avg_score float,        -- Average stress score across all posts
    pct_stress float,       -- Percentage of stressed posts (0.0 - 100.0)

    -- Metadata
    last_updated timestamp, -- When this aggregate was last updated

    PRIMARY KEY (hour_partition)
) WITH default_time_to_live = 15552000  -- 180 days in seconds
  AND compaction = {
    'class': 'SizeTieredCompactionStrategy'
  }
  AND compression = {
    'class': 'LZ4Compressor'
  }
  AND comment = 'Platform-wide hourly aggregated metrics with 180-day TTL';

-- Design rationale:
-- 1. Simple partition key (hour_partition):
--    - One row per hour globally
--    - No subreddit dimension (platform-wide view)
--    - Simple point lookups for dashboard
--    - Small partition size (single row)
--
-- 2. No clustering columns:
--    - Single global aggregate value per hour
--    - Simple upsert pattern for updates
--    - Minimal storage overhead
--
-- 3. TTL = 180 days: Long-term platform trends
--    - Matches agg_subreddit_hour retention
--    - Supports 6-month historical analysis
--    - Very compact data (one row per hour)
--
-- 4. SizeTieredCompactionStrategy:
--    - Better for tables with updates
--    - Global aggregates updated as subreddit data arrives
--    - Less frequent compaction overhead
--
-- 5. Metrics mirror subreddit table:
--    - Consistent schema for easy comparison
--    - total_cnt: Sum of all posts across subreddits
--    - stress_cnt: Sum of stressed posts
--    - avg_score: Weighted average stress score
--    - pct_stress: Global stress percentage
--
-- Query patterns supported:
-- - Get global stats for hour X
-- - Time-series of platform-wide stress trends
-- - Baseline metrics for anomaly detection
--
-- Update pattern:
-- - Upsert after aggregating all subreddits for the hour
-- - Can be computed from agg_subreddit_hour
-- - Idempotent updates (can reprocess same hour)
--
-- Dashboard use cases:
-- - "Global Stress Meter" widget
-- - Platform-wide trend charts
-- - Alert thresholds (e.g., "stress > 30% globally")
