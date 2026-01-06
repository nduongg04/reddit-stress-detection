## Context

VOZ.vn is a Vietnamese forum with a "Tâm sự" (Confessions) section at `voz.vn/f/tam-su.17`. This section contains personal posts suitable for stress detection analysis. The crawler must handle:

- HTML parsing of forum thread listings
- Pagination through multiple pages (newest first per R3.1.4)
- Post content extraction from individual threads
- Rate limiting to avoid IP blocks
- Resume capability for long-running crawls

## Goals / Non-Goals

**Goals:**
- Collect 12,000+ raw posts from VOZ tam-su forum
- Extract required fields: post_id, text, timestamp, source
- Provide resume capability for interrupted crawls
- Log progress with timestamps

**Non-Goals:**
- Stress filtering during collection (per R3.1.4)
- Deduplication (handled in Sprint 2)
- Token length filtering (handled in Sprint 2)
- Cassandra storage (use JSONL for raw storage)

## Decisions

### Decision 1: Use requests + BeautifulSoup

**Rationale:** VOZ.vn is server-rendered HTML. No JavaScript execution needed. This is simpler and more reliable than Selenium/Playwright.

**Alternatives considered:**
- Selenium: Overkill, slower, more dependencies
- Scrapy: Good but higher learning curve for simple task

### Decision 2: JSONL output format

**Rationale:**
- Append-only (safe for resume)
- Line-by-line processing
- Easy to convert to CSV/Cassandra later

**Output path:** `data/raw/voz_posts_v1.jsonl`

### Decision 3: Checkpoint-based resume

**Rationale:** Store last processed page number in `data/raw/.voz_checkpoint.json`. On restart, read checkpoint and continue from that page.

### Decision 4: Rate limiting

**Rationale:** 1 request per second minimum delay. Configurable. VOZ.vn does not document rate limits, so conservative approach.

## Data Schema

Each JSONL line:
```json
{
  "post_id": "12345",
  "text": "Post content here...",
  "timestamp": "2024-01-15T10:30:00+07:00",
  "source": "voz.vn/f/tam-su.17",
  "url": "https://voz.vn/t/thread-title.12345/",
  "crawled_at": "2024-01-20T08:00:00Z"
}
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    voz_crawler.py                           │
├─────────────────────────────────────────────────────────────┤
│  1. Load checkpoint (if exists)                             │
│  2. For each page (newest first):                           │
│     a. Fetch thread listing                                 │
│     b. Extract thread URLs                                  │
│     c. For each thread:                                     │
│        - Fetch thread page                                  │
│        - Extract first post content                         │
│        - Write to JSONL (append)                            │
│     d. Update checkpoint                                    │
│  3. Log progress every 100 posts                            │
└─────────────────────────────────────────────────────────────┘
```

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| IP block from VOZ.vn | Conservative rate limiting (1 req/s), random delays |
| HTML structure changes | Modular selectors, easy to update |
| Incomplete posts | Skip posts with empty content, log warnings |
| Duplicate threads | Track seen URLs in checkpoint |

## File Structure

```
scripts/
└── voz_crawler.py          # Main crawler script

data/
└── raw/
    ├── voz_posts_v1.jsonl  # Output file
    └── .voz_checkpoint.json # Resume checkpoint
```

## Open Questions

None - requirements are clear from R3.1.1, R3.1.4, R3.2.1, and R16.1.
