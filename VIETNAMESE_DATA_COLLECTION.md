# Vietnamese Data Collection Guide

Complete guide for collecting Vietnamese Reddit posts and storing them in Cassandra.

## Overview

This pipeline collects Vietnamese posts from Reddit using keyword-based search and stores them in Cassandra for later labeling and model training.

### Data Flow

```
Reddit API (Vietnamese keywords)
    ↓
Producer (keyword search + language detection)
    ↓
Kafka (reddit.posts.raw.v1)
    ↓
Spark Consumer (raw storage, no ML)
    ↓
Cassandra (reddit_rt.raw_posts_by_day)
    ↓
CSV Export for labeling
```

## Prerequisites

1. **Docker & Docker Compose** running
2. **Python 3.8+** with virtual environment
3. **Reddit API credentials** in `producers/reddit_producer/.env`
4. **8GB+ RAM** for Docker

## Step 1: Collect Vietnamese Posts

### Quick Start

```bash
# Run automated collection script
./collect_vietnamese_data.sh
```

**What it does:**
- ✅ Configures Vietnamese keyword collection mode
- ✅ Starts Docker services (Kafka, Cassandra)
- ✅ Initializes Cassandra schema
- ✅ Starts Kafka → Cassandra consumer (raw storage)
- ✅ Starts Reddit Producer (100 QPM, optimized)
- ✅ Monitors collection progress in real-time
- ✅ Auto-stops when target reached (5,000 posts)

### Collection Strategy

**Keywords Used:**

**Stress Keywords (24 keywords):**
- căng thẳng (stress)
- trầm cảm (depression)
- lo âu (anxiety)
- thất bại (failure)
- buồn (sad)
- chán nản (depressed)
- tuyệt vọng (hopeless)
- ...and 17 more

**Non-Stress Keywords (37 keywords):**
- du lịch (travel)
- vui vẻ (happy)
- hạnh phúc (happiness)
- thành công (success)
- ...and 33 more

**Search Process:**
1. Searches Reddit with individual keywords
2. Fetches 500 posts per keyword
3. Parallel language detection (Vietnamese only)
4. 8 parallel workers process posts
5. Stores in Cassandra with category tag

## Step 2: Monitor Collection

### Real-Time Progress

The script shows live progress:
```
Progress: 1234 / 5000 posts (24%) - +50 new
Progress: 1284 / 5000 posts (25%) - +50 new
```

### Manual Monitoring

```bash
# Watch producer logs
tail -f logs/vietnamese_collection.log

# Watch Cassandra count
watch 'docker exec reddit-cassandra cqlsh -e "SELECT COUNT(*) FROM reddit_rt.raw_posts_by_day;"'

# View consumer logs
docker logs -f reddit-spark-master
```

## Step 3: Verify Data in Cassandra

### Check Post Count

```bash
docker exec reddit-cassandra cqlsh
```

Inside cqlsh:
```sql
USE reddit_rt;

-- Count total posts
SELECT COUNT(*) FROM raw_posts_by_day;

-- View sample posts
SELECT post_id, title, subreddit, created_timestamp
FROM raw_posts_by_day
LIMIT 10;

-- Check date distribution
SELECT date_partition, COUNT(*) as post_count
FROM raw_posts_by_day
GROUP BY date_partition;

exit
```

### Expected Results

After successful collection:
- **Total posts**: ~5,000
- **Categories**: Mixed (keyword-tagged)
- **Language**: Vietnamese (filtered)
- **Storage**: reddit_rt.raw_posts_by_day table

## Step 4: Export Data for Labeling

```bash
# Export to CSV
./scripts/export_vietnamese_data.sh
```

**Output:**
- **File**: `data/vietnamese_unlabeled/vietnamese_posts_YYYYMMDD_HHMMSS.csv`
- **Metadata**: `data/vietnamese_unlabeled/metadata.json`

### CSV Format

| Column | Description |
|--------|-------------|
| post_id | Reddit post ID |
| title | Post title (Vietnamese) |
| body | Post body text |
| subreddit | Source subreddit |
| created_timestamp | Post creation time |
| score | Reddit score |
| num_comments | Comment count |
| author_hash | Hashed author ID (privacy) |

### Sample Export

```bash
# View first 10 posts
head -11 data/vietnamese_unlabeled/vietnamese_posts_*.csv | column -t -s','

# Count exported posts
wc -l data/vietnamese_unlabeled/vietnamese_posts_*.csv
```

## Configuration Details

### Cassandra Schema

**Table: raw_posts_by_day**
```sql
CREATE TABLE reddit_rt.raw_posts_by_day (
    date_partition text,        -- Partition key: YYYY-MM-DD
    post_id text,               -- Clustering key
    title text,
    body text,
    author_hash text,
    subreddit text,
    created_timestamp timestamp,
    score int,
    num_comments int,
    url text,
    permalink text,
    type text,
    PRIMARY KEY (date_partition, post_id)
) WITH CLUSTERING ORDER BY (post_id ASC)
  AND default_time_to_live = 1209600;  -- 14 days
```

### Producer Configuration

**Mode**: Vietnamese keyword search
**Rate**: 100 QPM (Reddit's max)
**Batch Size**: 500 posts per search
**Workers**: 8 parallel threads
**Language Filter**: Vietnamese only (using langdetect)

## Performance Metrics

### Expected Throughput

| Metric | Value |
|--------|-------|
| **Collection Rate** | 100 requests/min |
| **Posts per Batch** | 500 (before filtering) |
| **Vietnamese Hit Rate** | ~10-30% (varies by keyword) |
| **Total Time (5,000 posts)** | 8-12 minutes |
| **Storage Size** | ~5-10 MB (uncompressed) |

### Actual Performance

Monitor these metrics during collection:
```bash
# Average rate
tail -f logs/vietnamese_collection.log | grep "Rate:"

# Posts published
grep -c "Published" logs/vietnamese_collection.log

# Cassandra write rate
docker exec reddit-cassandra nodetool tablestats reddit_rt.raw_posts_by_day
```

## Troubleshooting

### Collection Not Starting

```bash
# Check Docker services
docker-compose ps

# Restart if needed
docker-compose restart kafka cassandra

# Check producer logs
tail -50 logs/vietnamese_collection.log
```

### No Vietnamese Posts Found

```bash
# Check language detection
tail -f logs/vietnamese_collection.log | grep "Vietnamese"

# Verify keywords
python producers/reddit_producer/config/vietnamese_keywords.py

# Test search manually
cd producers/reddit_producer
python -c "
import praw
from config.secrets import RedditCredentials
reddit = praw.Reddit(
    client_id=RedditCredentials.CLIENT_ID,
    client_secret=RedditCredentials.CLIENT_SECRET,
    user_agent=RedditCredentials.USER_AGENT
)
posts = list(reddit.subreddit('all').search('\"căng thẳng\"', limit=5))
for p in posts:
    print(f'{p.id}: {p.title}')
"
```

### Cassandra Connection Failed

```bash
# Check Cassandra health
docker exec reddit-cassandra nodetool status

# Verify schema
docker exec reddit-cassandra cqlsh -e "DESCRIBE KEYSPACE reddit_rt;"

# Recreate schema if needed
./scripts/init-cassandra-schema.sh
```

### Rate Limit Errors

The producer auto-throttles, but if you see rate limit errors:

```bash
# Check current rate
tail -f logs/vietnamese_collection.log | grep "Rate:"

# Should show: ~98-100 QPM (within limit)
# If higher: Bug in rate limiter
# If lower: Working correctly, being conservative
```

### Collection Stuck

```bash
# Check if producer is running
ps aux | grep "python main.py"

# Check Spark consumer
docker logs reddit-spark-master | tail -20

# Check Kafka lag
docker exec reddit-kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --all-groups
```

## Manual Collection (Advanced)

If you want to run steps individually:

### 1. Start Docker Services

```bash
docker-compose up -d kafka cassandra spark-master spark-worker
```

### 2. Initialize Schema

```bash
./scripts/init-cassandra-schema.sh
```

### 3. Configure Producer

Edit `producers/reddit_producer/config/config.yaml`:
```yaml
reddit:
  collection_mode: "vietnamese"
  target_posts: 5000
```

### 4. Start Consumer

```bash
# Use the raw consumer (no ML)
docker exec -d reddit-spark-master /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --packages com.datastax.spark:spark-cassandra-connector_2.12:3.5.0,org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
  /opt/spark-apps/kafka_to_cassandra.py
```

### 5. Start Producer

```bash
cd producers/reddit_producer
python main.py
```

## Data Quality Checks

### Verify Language

```bash
# Export sample and check manually
docker exec reddit-cassandra cqlsh -e "
  SELECT title FROM reddit_rt.raw_posts_by_day LIMIT 20;
" | grep -v "^-" | head -20
```

### Check for Duplicates

```sql
-- In cqlsh
USE reddit_rt;

-- Count unique post IDs
SELECT COUNT(DISTINCT post_id) FROM raw_posts_by_day;

-- Should match total count (no duplicates)
SELECT COUNT(*) FROM raw_posts_by_day;
```

### Verify Date Range

```sql
SELECT date_partition, COUNT(*) as count
FROM raw_posts_by_day
GROUP BY date_partition
ORDER BY date_partition DESC;
```

## Next Steps

After collecting 5,000+ Vietnamese posts:

### 1. Export Data
```bash
./scripts/export_vietnamese_data.sh
```

### 2. Label Data
```bash
# Coming next: Ollama labeling script
./scripts/label_with_ollama.sh
```

### 3. Train Model
```bash
# Coming next: Vietnamese model training
./train_vietnamese_model.sh
```

### 4. Deploy Model
```bash
# Update pipeline to use Vietnamese model
# Update spark/model_inference.py
# Restart pipeline with new model
```

## Storage Cleanup

### Clear Old Data

```sql
-- In cqlsh
USE reddit_rt;

-- Delete all posts
TRUNCATE raw_posts_by_day;

-- Verify
SELECT COUNT(*) FROM raw_posts_by_day;
```

### Reset and Recollect

```bash
# Clear Cassandra data
docker exec reddit-cassandra cqlsh -e "TRUNCATE reddit_rt.raw_posts_by_day;"

# Clear Kafka offset (fresh start)
docker exec reddit-kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --delete --group spark-kafka-consumer

# Run collection again
./collect_vietnamese_data.sh
```

## FAQ

**Q: How long does collection take?**
A: 8-12 minutes for 5,000 posts at 100 QPM.

**Q: Can I collect more than 5,000 posts?**
A: Yes! Edit `target_posts` in config or script.

**Q: What if I get rate limited?**
A: Producer auto-throttles to 100 QPM. Should not happen.

**Q: Can I pause and resume?**
A: Yes! The producer tracks processed IDs. Just restart it.

**Q: How do I verify language detection is working?**
A: Check logs: `grep "Vietnamese" logs/vietnamese_collection.log`

**Q: What happens to non-Vietnamese posts?**
A: Filtered out during collection (not stored).

---

**Ready to collect?** Run `./collect_vietnamese_data.sh` and watch the magic! ✨
