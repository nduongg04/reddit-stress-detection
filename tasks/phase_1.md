# Phase 1: Data Collection

## Goal
Collect 10,000+ Vietnamese stress-related posts from VOZ.vn and stream to Cassandra via Kafka.

## Architecture
```
VOZ.vn → voz_kafka_producer.py → Kafka (voz.posts.raw.v1) → Spark → Cassandra (voz_raw_posts)
```

## Tasks

### 1.1 Infrastructure Setup
- [x] Docker Compose with Zookeeper, Kafka, Cassandra
- [x] Kafka UI for monitoring (port 8080)
- [x] Health checks for all services

### 1.2 Kafka Configuration
- [x] Create topic: `voz.posts.raw.v1`
- [x] Partitions: 3 (for parallel processing)
- [x] Replication: 1 (dev) / 3 (prod)
- [x] Retention: 7 days

### 1.3 Cassandra Schema
- [x] Keyspace: `reddit_rt`
- [x] Table: `voz_raw_posts` (see below)

### 1.4 VOZ Crawler/Producer
- [x] File: `producers/voz_kafka_producer.py`
- [x] Crawl voz.vn/f/tam-su.17 forum
- [x] Filter by stress keywords
- [x] Checkpoint for resume
- [x] Rate limiting (1s delay)

### 1.5 Data Pipeline (Kafka → Cassandra)
- [x] Spark Structured Streaming consumer
- [x] Write raw posts to `voz_raw_posts`
- [x] Deduplication by post_id

## Cassandra Schema

```cql
-- File: cassandra/schema/04_voz_raw_posts.cql
CREATE TABLE IF NOT EXISTS voz_raw_posts (
    post_id text PRIMARY KEY,
    text text,
    timestamp timestamp,
    crawled_at timestamp,
    source text,
    url text
) WITH compaction = {'class': 'SizeTieredCompactionStrategy'}
  AND compression = {'class': 'LZ4Compressor'};
```

## Files Structure

```
producers/
  voz_kafka_producer.py     # [EXISTS] VOZ crawler + Kafka producer
  __init__.py
cassandra/
  schema/
    01_keyspace.cql         # [EXISTS] reddit_rt keyspace
    04_voz_raw_posts.cql    # [EXISTS] Raw posts table
scripts/
  init-cassandra-schema.sh  # [EXISTS] Schema initializer
data/
  raw/
    .voz_kafka_checkpoint.json  # Crawler checkpoint
```

## Kafka Message Schema

```json
{
  "post_id": "12345",
  "text": "Tôi cảm thấy rất stress với công việc...",
  "url": "https://voz.vn/t/thread-title.12345/",
  "source": "voz.vn/f/tam-su.17",
  "timestamp": "2024-01-15T10:30:00Z",
  "crawled_at": "2024-01-15T12:00:00Z"
}
```

## Commands

```bash
# Start infrastructure
docker-compose up -d zookeeper kafka kafka-ui cassandra

# Initialize Cassandra schema
./scripts/init-cassandra-schema.sh

# Create Kafka topic
docker exec reddit-kafka kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --topic voz.posts.raw.v1 \
  --partitions 3 \
  --replication-factor 1

# Run crawler
python producers/voz_kafka_producer.py --target 10000 --delay 1.0

# Monitor Kafka
open http://localhost:8080
```

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| VOZ rate limit (429) | Exponential backoff, max 3 retries |
| Network timeout | 30s timeout, retry with delay |
| Duplicate posts | Cassandra upsert (post_id is PK) |
| Empty/short posts | Skip posts < 50 chars |
| HTML in content | BeautifulSoup text extraction |
| Quotes in posts | Remove .bbCodeBlock--quote elements |
| Kafka broker down | Producer buffer, flush on recovery |
| Cassandra unavailable | Spark retry with checkpoint |
| Crawler interrupted | Checkpoint saves seen URLs + page |
| Invalid timestamp | Use crawled_at as fallback |

## Validation Criteria

- [ ] 10,000+ posts in `voz_raw_posts` table
- [ ] No duplicate post_ids
- [ ] All posts have non-empty text (>50 chars)
- [ ] Kafka topic lag < 100 messages
- [ ] Crawler can resume from checkpoint

## Monitoring

```bash
# Check Cassandra row count
docker exec reddit-cassandra cqlsh -e \
  "SELECT COUNT(*) FROM reddit_rt.voz_raw_posts;"

# Check Kafka topic
docker exec reddit-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic voz.posts.raw.v1 \
  --from-beginning --max-messages 5
```
