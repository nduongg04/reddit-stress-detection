# Reddit Stress Detection System

Real-time ML pipeline detecting stress in Reddit posts using Vietnamese PhoBERT.

## Architecture

```
Reddit → Kafka → Spark + Vietnamese PhoBERT → Cassandra → Grafana
```

## Quick Start

**New to this project?** → See [QUICKSTART.md](QUICKSTART.md) for detailed step-by-step guide.

**Collecting Vietnamese data?** → See [VIETNAMESE_DATA_COLLECTION.md](VIETNAMESE_DATA_COLLECTION.md) for Vietnamese post collection.

### Prerequisites
- Docker & Docker Compose
- Python 3.8+ with virtual environment
- Reddit API credentials (free)
- 8GB+ RAM
- **Vietnamese PhoBERT model** (train it first: `./train_vietnamese_stress.sh`)

### Run Complete Pipeline

```bash
# One command to start everything!
./run.sh
```

**Auto-configured features:**
- ✅ Activates virtual environment
- ✅ Validates Vietnamese PhoBERT model
- ✅ Starts Docker services (Kafka, Cassandra, Spark, Grafana)
- ✅ Initializes schemas and topics
- ✅ Configures Kafka connection (localhost:29092 for local producer)
- ✅ Starts Reddit Producer
- ✅ Starts Spark ML Pipeline
- ✅ Real-time monitoring

### Access Dashboards
- **Streamlit ABSA Dashboard**: http://localhost:8501 (real-time Vietnamese mental health analytics)
- **Grafana**: http://localhost:3000 (admin/admin)
- **Kafka UI**: http://localhost:8080
- **Spark UI**: http://localhost:8081
- **Airflow**: http://localhost:8082 (airflow/airflow)

## Configuration

### Reddit API Credentials
Create `producers/reddit_producer/.env`:
```bash
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=your_user_agent
```

### Performance Configuration
Edit `producers/reddit_producer/config/config.yaml`:
```yaml
reddit:
  posts_per_minute: 100  # Maximized for Reddit's 100 QPM limit

rate_limiting:
  requests_per_minute: 100  # Reddit's max QPM (10-min avg)
  burst_limit: 50  # Allow bursts up to 50 req/min
  window_minutes: 10  # Reddit's averaging window
```

**Rate Limit Optimizations:**
- **100 QPM sustained rate** (Reddit's max, averaged over 10 minutes)
- **50 burst limit** for initial request bursts
- **Adaptive throttling** based on Reddit API headers
- **10-minute averaging window** matching Reddit's enforcement
- Real-time monitoring of `X-Ratelimit-*` headers

**Processing Optimizations:**
- 8 parallel worker threads for concurrent processing
- 500 posts/batch for Vietnamese collection (5x increase)
- Parallel language detection using ThreadPoolExecutor
- Minimal sleep delays (0.5s between searches)
- Smart batch filtering before processing
- Rate limiter handles all throttling automatically

## ML Model

**Vietnamese PhoBERT Model:**
- Multi-label classification (10 mental health characteristics)
- Vietnamese-only stress detection
- PhoBERT-base-v2 (135M parameters)
- Trained on clean r/vozforums data
- LDA-derived mental health topics

**New Training Pipeline (r/vozforums):**
```bash
# 1. Collect 1k stress posts from r/vozforums
./collect_vozforums_stress.sh

# 2. Export collected posts
python scripts/export_vietnamese_from_cassandra.py

# 3. Extract 10 mental health topics with LDA
python ml/lda/extract_topics.py

# 4. Prepare balanced dataset (200 stress + 200 non-stress)
python scripts/prepare_vozforums_dataset.py

# 5. Train multi-label PhoBERT model
# (Training script supports multi-label via topic JSON)
```

**Old Binary Classification:**
```bash
# Binary STRESS/NON_STRESS (kept for reference)
./train_vietnamese_stress.sh
./test_vietnamese_model.sh
```

## Monitoring & Verification

### Check Pipeline Health

```bash
# 1. Producer is crawling posts
tail -f logs/reddit_producer.log | grep "Published"

# 2. Kafka has messages
docker exec reddit-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic reddit.posts.raw.v1 \
  --max-messages 5

# 3. Spark is processing
docker logs -f reddit-spark-master | grep "Batch"

# 4. Data in Cassandra
docker exec -it reddit-cassandra cqlsh
```

### View Data in Cassandra

```sql
-- Inside cqlsh
USE reddit_rt;

-- View recent classified posts
SELECT subreddit, title, stress_score, stress_label, created_utc
FROM classified_posts_by_hour
LIMIT 10;

-- Count total posts
SELECT COUNT(*) FROM classified_posts_by_hour;

-- View stress posts only
SELECT * FROM classified_posts_by_hour
WHERE subreddit = 'anxiety'
  AND hour_partition = '2024-11-20-15'
  AND stress_label = true
LIMIT 20;

-- Check aggregated metrics
SELECT * FROM agg_subreddit_hour LIMIT 10;
SELECT * FROM agg_global_hour LIMIT 10;
```

### Real-Time Monitoring

```bash
# Watch post count grow
watch 'docker exec reddit-cassandra cqlsh -e \
  "SELECT COUNT(*) FROM reddit_rt.classified_posts_by_hour;"'

# Monitor producer rate
tail -f logs/reddit_producer.log | grep "Rate:"

# Track Spark processing
docker logs -f reddit-spark-master 2>&1 | grep "classified"
```

## Performance Metrics

**Expected Throughput:**
- **100 requests/minute** sustained (Reddit API max)
- **500 posts per search batch** (5x original)
- **~5,000 posts in 8-12 minutes** (Vietnamese collection)
- **~8x faster processing** with parallel workers

**Rate Limit Monitoring:**
```bash
# Watch producer logs for rate limit stats
tail -f logs/reddit_producer.log | grep "Rate:"

# Example output:
# Rate: 98.5/100 QPM (98.5% utilized)
# Reddit API: 750 used, 250 remaining, resets in 480s
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **Producer DNS lookup failed** | Run `./run.sh` (auto-fixes Kafka config) |
| **Model not found** | Run `./train_vietnamese_stress.sh` |
| **Kafka not connecting** | `docker-compose restart kafka` |
| **Out of memory** | Increase Docker memory to 4GB+ |
| **Rate limit errors** | Producer auto-throttles; wait for reset window |
| **Ollama not found** | Install: `brew install ollama` (Mac) or see https://ollama.com |

### Kafka Connection Issue

If producer shows `DNS lookup failed for kafka:9092`:

```bash
# Auto-fix (recommended)
./run.sh

# Manual fix
# Edit producers/reddit_producer/config/config.yaml
# Change: - kafka:9092
# To:     - localhost:29092
```

**Why:** Producer runs locally (needs `localhost:29092`), Spark runs in Docker (uses `kafka:9092`).

## Tech Stack

- **Streaming**: Apache Kafka, Apache Spark
- **Storage**: Apache Cassandra
- **ML**: PhoBERT-base-v2 (Hugging Face Transformers)
- **Orchestration**: Apache Airflow
- **Visualization**: Grafana
- **Language**: Python 3.8+
- **Labeling**: Ollama (llama3.1:8b)

## Key Files

| File | Description |
|------|-------------|
| `run.sh` | Start entire pipeline |
| `train_vietnamese_stress.sh` | Train Vietnamese PhoBERT model |
| `test_vietnamese_model.sh` | Test model accuracy |
| `spark/kafka_to_cassandra_with_ml.py` | Real-time ML pipeline |
| `spark/model_inference.py` | Vietnamese model wrapper |
| `ml/models/vietnamese_augmentation.py` | Vietnamese text augmentation |
| `scripts/export_vietnamese_from_cassandra.py` | Export Vietnamese posts |
| `ml/dataset/label_vietnamese_with_ollama.py` | Automated labeling |
| `producers/reddit_producer/config/config.yaml` | Rate limiting & settings |

---

**Project Version**: 2.0.0
**Model Version**: Vietnamese PhoBERT v1
**SE363** - Software Engineering Project
