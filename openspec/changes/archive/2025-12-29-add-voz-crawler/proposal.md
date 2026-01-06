# Change: Add VOZ.vn Crawler for Data Collection

## Why

The system currently relies on Reddit data (r/vozforums) which violates R3.1.2 (Reddit is explicitly excluded). The refined requirements specify VOZ.vn tam-su forum as the **only allowed data source** (R3.1.1). We need a dedicated crawler to collect 12,000 raw Vietnamese posts from `voz.vn/f/tam-su.17`.

## What Changes

- **NEW**: VOZ.vn crawler script (`scripts/voz_crawler.py`)
- **NEW**: Raw post storage in JSONL format (`data/raw/voz_posts_v1.jsonl`)
- **NEW**: Resume capability with checkpoint persistence
- **NEW**: Progress logging with timestamps
- **REMOVES**: Dependency on Reddit API for data collection phase

## Impact

- Affected specs: `data-collection` (new capability)
- Affected code:
  - `scripts/voz_crawler.py` (new)
  - `data/raw/` directory (new)
  - Future integration with `scripts/export_vietnamese_from_cassandra.py`

## Scope

This is Sprint 1 of the refined pipeline. It establishes the foundation for:
- Sprint 2: Data cleaning (deduplication, token filtering)
- Sprint 3: LLM ensemble labeling

## Success Criteria

- Crawler runs without errors for 2+ hours
- ≥12,000 posts collected from VOZ tam-su forum
- Each post has: `post_id`, `text`, `timestamp`, `source`
- Duplicate URLs are skipped during crawl
- Crawler can resume from last checkpoint
