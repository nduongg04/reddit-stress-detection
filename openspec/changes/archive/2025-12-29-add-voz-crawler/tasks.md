## 1. Setup

- [x] 1.1 Create `data/raw/` directory structure
- [x] 1.2 Add `requests` and `beautifulsoup4` to requirements (if not present)

## 2. Core Crawler Implementation

- [x] 2.1 Create `scripts/voz_crawler.py` with main entry point
- [x] 2.2 Implement forum page fetcher for `voz.vn/f/tam-su.17`
- [x] 2.3 Implement thread listing parser (extract thread URLs, newest first)
- [x] 2.4 Implement single thread fetcher (extract first post content)
- [x] 2.5 Implement field extraction: `post_id`, `text`, `timestamp`, `source`, `url`

## 3. Storage

- [x] 3.1 Implement JSONL writer (append mode)
- [x] 3.2 Add `crawled_at` timestamp to each record

## 4. Resume Capability

- [x] 4.1 Implement checkpoint loading from `.voz_checkpoint.json`
- [x] 4.2 Implement checkpoint saving (page number, seen URLs)
- [x] 4.3 Add duplicate URL detection using checkpoint

## 5. Rate Limiting & Robustness

- [x] 5.1 Add configurable delay between requests (default 1s)
- [x] 5.2 Add random jitter to delays (0.5-1.5s range)
- [x] 5.3 Handle HTTP errors with retry logic (max 3 retries)
- [x] 5.4 Skip empty/missing content posts with warning log

## 6. Progress Logging

- [x] 6.1 Log progress every 100 posts (timestamp, count, page)
- [x] 6.2 Log completion summary (total posts, elapsed time)
- [x] 6.3 Log warnings for skipped posts

## 7. Validation

- [x] 7.1 Manual test: Run crawler for 100 posts
- [x] 7.2 Verify JSONL output format is valid
- [x] 7.3 Verify resume works after interruption
- [x] 7.4 Verify duplicate URLs are skipped

## 8. Documentation

- [x] 8.1 Add usage instructions to README.md (brief)

## Acceptance Criteria

- [x] Crawler runs without errors for 2+ hours
- [x] ≥12,000 posts collected from VOZ tam-su forum
- [x] Each post has: `post_id`, `text`, `timestamp`, `source`
- [x] Duplicate URLs are skipped during crawl
- [x] Crawler can resume from last checkpoint

## Deliverables

- `scripts/voz_crawler.py`
- `data/raw/voz_posts_v1.jsonl`
- Crawl log with timestamps

## Implementation Notes

- Forum URL redirects from `tam-su.17` to `chuyen-tro-linh-tinh™.17` (same forum, renamed)
- Removed `Accept-Encoding` header to avoid compression issues with VOZ.vn
- XenForo 2 uses `.structItem--thread` for thread listings
- First post content extracted via `.message-body .bbWrapper` selector
