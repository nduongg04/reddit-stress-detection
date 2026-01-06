-- ============================================================================
-- Table: voz_classified_posts
-- Description: Stores classified VOZ posts with stress aspects and demographics
-- Sprint: 8 - Deployment + Real-Time Demographics & Dashboard
-- ============================================================================

USE reddit_rt;

-- Main classified posts table with demographics
-- Partitioned by hour for efficient time-range queries
CREATE TABLE IF NOT EXISTS voz_classified_posts (
    -- Partition key: hour bucket for time-series queries
    hour_bucket text,

    -- Clustering keys: sorted by classification time (newest first)
    classified_at timestamp,
    post_id text,

    -- Original post content
    text text,
    url text,
    source text,
    original_timestamp timestamp,

    -- Stress classification (LLM output)
    aspects list<int>,              -- List of aspect IDs [0-9]
    aspect_probs list<float>,       -- Probabilities for each of 10 aspects
    confidence float,               -- Overall confidence score
    stress_label boolean,           -- True if any stress aspect detected
    reasoning text,                 -- LLM reasoning for classification

    -- Demographics (LLM extracted)
    gender text,                    -- 'nam', 'nữ', 'unknown'
    age_group text,                 -- 'teen', 'young_adult', 'adult', 'middle_aged', 'senior', 'unknown'
    occupation text,                -- 'student', 'office_worker', 'it_engineer', etc.
    relationship text,              -- 'single', 'dating', 'married', 'divorced', 'unknown'

    -- Metadata
    model_version text,             -- e.g., 'llama3.1:8b'
    processing_time_ms int,         -- Time taken for LLM inference

    PRIMARY KEY ((hour_bucket), classified_at, post_id)
) WITH CLUSTERING ORDER BY (classified_at DESC, post_id ASC)
  AND compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_unit': 'HOURS',
    'compaction_window_size': 1
  }
  AND compression = {
    'class': 'LZ4Compressor'
  }
  AND default_time_to_live = 604800  -- 7 days retention for demo
  AND comment = 'VOZ posts classified with stress aspects and demographics';

-- Index for filtering by stress label
CREATE INDEX IF NOT EXISTS voz_stress_idx ON voz_classified_posts (stress_label);

-- Index for filtering by gender
CREATE INDEX IF NOT EXISTS voz_gender_idx ON voz_classified_posts (gender);

-- Index for filtering by occupation
CREATE INDEX IF NOT EXISTS voz_occupation_idx ON voz_classified_posts (occupation);

-- ============================================================================
-- Aggregation tables for dashboard charts
-- ============================================================================

-- Hourly aspect counts (for time-series chart)
CREATE TABLE IF NOT EXISTS voz_aspect_hourly (
    hour_bucket text,
    aspect_id int,
    count counter,
    PRIMARY KEY ((hour_bucket), aspect_id)
);

-- Demographic distribution (for pie charts)
CREATE TABLE IF NOT EXISTS voz_demographics_daily (
    day_bucket text,
    demographic_type text,  -- 'gender', 'age_group', 'occupation', 'relationship'
    value text,             -- e.g., 'nam', 'student', etc.
    count counter,
    PRIMARY KEY ((day_bucket, demographic_type), value)
);

-- Aspect co-occurrence matrix (for heatmap)
CREATE TABLE IF NOT EXISTS voz_aspect_cooccurrence (
    day_bucket text,
    aspect_a int,
    aspect_b int,
    count counter,
    PRIMARY KEY ((day_bucket), aspect_a, aspect_b)
);

-- Design notes:
-- 1. hour_bucket format: 'YYYY-MM-DD-HH' (e.g., '2024-12-30-14')
-- 2. day_bucket format: 'YYYY-MM-DD' (e.g., '2024-12-30')
-- 3. TimeWindowCompaction optimized for time-series data
-- 4. Counter tables for efficient aggregation without read-before-write
-- 5. 7-day TTL keeps data fresh for demo without manual cleanup
