## ADDED Requirements

### Requirement: VOZ.vn Data Source

The system SHALL ingest data exclusively from VOZ.vn forum `voz.vn/f/tam-su.17` as specified in R3.1.1.

#### Scenario: Crawler targets correct forum
- **WHEN** the crawler is started
- **THEN** it SHALL only fetch posts from `voz.vn/f/tam-su.17`

#### Scenario: No other sources allowed
- **WHEN** data collection is performed
- **THEN** the system SHALL NOT ingest data from Reddit, Tinh Te, VnExpress, or any other source

---

### Requirement: Pagination Strategy

The system SHALL crawl all pages from newest to oldest until 12,000 posts are collected (R3.1.4).

#### Scenario: Newest first ordering
- **WHEN** the crawler fetches the forum listing
- **THEN** it SHALL process threads in newest-first order

#### Scenario: Target post count reached
- **WHEN** 12,000 posts have been collected
- **THEN** the crawler SHALL stop and log completion

---

### Requirement: Post Field Extraction

Each collected post SHALL contain the required fields specified in R3.2.1.

#### Scenario: Required fields present
- **WHEN** a post is extracted from VOZ.vn
- **THEN** it SHALL include: `post_id`, `text`, `timestamp`, `source`

#### Scenario: Missing content handling
- **WHEN** a post has empty or missing text content
- **THEN** the crawler SHALL skip the post and log a warning

---

### Requirement: Raw Storage Format

The system SHALL store raw posts in JSONL format for append-only writes.

#### Scenario: JSONL output
- **WHEN** a post is successfully extracted
- **THEN** it SHALL be appended to `data/raw/voz_posts_v1.jsonl`

#### Scenario: Schema compliance
- **WHEN** writing to JSONL
- **THEN** each line SHALL be valid JSON with fields: `post_id`, `text`, `timestamp`, `source`, `url`, `crawled_at`

---

### Requirement: Resume Capability

The crawler SHALL support resuming from the last checkpoint after interruption (R16.1).

#### Scenario: Checkpoint persistence
- **WHEN** the crawler completes a page
- **THEN** it SHALL update the checkpoint file with the current page number and seen URLs

#### Scenario: Resume from checkpoint
- **WHEN** the crawler is restarted and a checkpoint exists
- **THEN** it SHALL continue from the last saved page number

#### Scenario: Duplicate URL skipping
- **WHEN** a thread URL has already been processed (in checkpoint)
- **THEN** the crawler SHALL skip it without re-fetching

---

### Requirement: Progress Logging

The crawler SHALL log progress with timestamps for monitoring.

#### Scenario: Periodic logging
- **WHEN** every 100 posts are collected
- **THEN** the crawler SHALL log: timestamp, total posts collected, current page number

#### Scenario: Completion logging
- **WHEN** the crawler completes or is interrupted
- **THEN** it SHALL log: total posts collected, elapsed time, final page number
