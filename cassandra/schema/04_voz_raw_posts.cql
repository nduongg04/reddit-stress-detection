-- ============================================================================
-- Table: voz_raw_posts
-- Description: Stores raw VOZ.vn posts for stress detection training data
-- Sprint: 1 - Data Collection Infrastructure
-- Requirement: R3.2 (Post Requirements)
-- ============================================================================

USE reddit_rt;

-- VOZ posts table - no TTL since this is training data (R21: labeled datasets = 2 years)
CREATE TABLE IF NOT EXISTS voz_raw_posts (
    -- Partition key: unique post identifier (natural deduplication)
    post_id text,

    -- Content fields (R3.2.1)
    text text,

    -- Temporal data
    timestamp timestamp,  -- Original VOZ post creation time
    crawled_at timestamp,

    -- Metadata
    source text,          -- 'voz.vn/f/tam-su.17'
    url text,

    PRIMARY KEY (post_id)
) WITH compaction = {
    'class': 'SizeTieredCompactionStrategy'
  }
  AND compression = {
    'class': 'LZ4Compressor'
  }
  AND comment = 'Raw VOZ.vn posts for stress detection training - no TTL for training data';

-- Secondary index for querying by source (useful for filtering by forum)
CREATE INDEX IF NOT EXISTS voz_source_idx ON voz_raw_posts (source);

-- Design rationale:
-- 1. Partition by post_id: Natural deduplication - same post_id overwrites
--    - No need for ALLOW FILTERING or secondary index for duplicate checks
--    - Even distribution across cluster nodes
-- 2. No TTL: Training data should be permanent (R21: 2 years for labeled)
-- 3. SizeTieredCompaction: Better for write-once, read-many pattern
-- 4. Index on source: Allows filtering by forum if needed
