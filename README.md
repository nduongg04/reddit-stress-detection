# Reddit Stress Detection System

Real-time data pipeline for detecting stress-related content in Reddit posts using machine learning.

## Architecture

```
Reddit (PRAW) → Kafka → Spark Streaming → Cassandra → Grafana
                           ↓
                    DistilBERT Model
```

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.8+ with virtual environment
- 8GB+ RAM

### Option 1: Automated (One Command - Recommended)

**Run entire pipeline with one script:**
```bash
./run.sh
```

This will:
- ✅ Activate virtual environment
- ✅ Check v4 model exists
- ✅ Start Docker services (Kafka, Cassandra, Grafana)
- ✅ Initialize Cassandra schema
- ✅ Create Kafka topics
- ✅ Start Reddit Producer (background)
- ✅ Start Spark ML Pipeline (background)
- ✅ Monitor all components in real-time

**What you'll see:**
```
✓ All Components Running!
Running Components:
  • Reddit Producer    (PID: 12345) → logs/producer.log
  • Spark ML Pipeline  (PID: 12346) → logs/spark_ml.log
  • Kafka              (Docker: reddit-kafka)
  • Cassandra          (Docker: reddit-cassandra)

Press Ctrl+C to stop all components
```

### Option 2: Manual (Step by Step)

**Terminal 1: Infrastructure**
```bash
# Start Docker services
docker-compose up -d

# Wait 30 seconds, then initialize
sleep 30
docker exec -i reddit-cassandra cqlsh < cassandra/schema/01_keyspace.cql
docker exec -i reddit-cassandra cqlsh < cassandra/schema/02_raw_posts_by_day.cql
docker exec -i reddit-cassandra cqlsh < cassandra/schema/03_classified_posts_by_hour.cql
docker exec -i reddit-cassandra cqlsh < cassandra/schema/04_agg_subreddit_hour.cql
docker exec -i reddit-cassandra cqlsh < cassandra/schema/05_agg_global_hour.cql
./scripts/init-kafka-topics.sh
```

**Terminal 2: Reddit Producer**
```bash
source .venv/bin/activate
cd producers/reddit_producer
python main.py
```

**Terminal 3: Spark Streaming + v4 Model**
```bash
source .venv/bin/activate
python spark/kafka_to_cassandra_with_ml.py
```

**Test Integration**
```bash
./test_realtime_integration.sh
```

### Option 2: Basic Pipeline (No ML)

```bash
docker-compose up -d
./scripts/init-kafka-topics.sh
./scripts/init-cassandra-schema.sh

docker exec -it reddit-spark-master spark-submit \
  --master spark://spark-master:7077 \
  --packages com.datastax.spark:spark-cassandra-connector_2.12:3.5.1,org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1 \
  /opt/spark-apps/kafka_to_cassandra.py
```

### Access Dashboards
- **Grafana**: http://localhost:3000 (admin/admin)
- **Spark UI**: http://localhost:8080
- **Airflow**: http://localhost:8085

## Project Structure

```
.
├── cassandra/schema/            # Cassandra database schemas (5 tables)
├── consumers/                   # Kafka consumers (DLQ monitoring)
├── grafana/                     # Visualization dashboards
├── ml/                          # Machine learning
│   ├── dataset/                 # Training data (11,270 labeled posts)
│   │   ├── labeled/             # Ollama-labeled dataset
│   │   └── splits/              # Train/val/test splits
│   └── models/                  # DistilBERT models (v1-v4)
├── producers/reddit_producer/   # Reddit data crawler (PRAW)
├── spark/                       # Spark streaming pipeline
│   ├── kafka_to_cassandra.py        # Basic pipeline (no ML)
│   ├── kafka_to_cassandra_with_ml.py # Real-time ML inference
│   └── model_inference.py           # v4 model wrapper
├── airflow/dags/                # Airflow orchestration
├── scripts/                     # Setup scripts
│   ├── init-kafka-topics.sh     # Kafka initialization
│   ├── init-cassandra-schema.sh # Cassandra initialization
│   └── airflow-init.sh          # Airflow initialization
└── docker-compose.yml           # Infrastructure definition
```

## Components

### Data Pipeline
1. **Reddit Producer** (`producers/reddit_producer/`) - Crawls Reddit posts using PRAW
2. **Kafka** - Message queue (topic: `reddit.posts.raw.v1`)
3. **Spark Streaming** (`spark/kafka_to_cassandra.py`) - Processes and writes to Cassandra
4. **Cassandra** - Time-series storage with 5 tables
5. **Grafana** - Real-time dashboards

### Machine Learning

#### Models Available
- **v1-v3**: Experimental versions
- **v4** (Latest): Production-ready with best performance

#### Training
```bash
# Activate environment
source .venv/bin/activate

# Train v4 model
./train_reddit_stress_v4.sh

# Test model
./test_v4_model.sh
```

#### Model Details
- **Architecture**: DistilBERT (distilbert-base-uncased)
- **Task**: Binary classification (STRESS / NON_STRESS)
- **Dataset**: 11,270 Reddit posts labeled by Ollama (llama3.1:8b)
- **Performance**: ~80% accuracy, ~83% F1 score
- **Real-Time Inference**: 30-60 seconds latency

## Configuration

### Reddit API Credentials
Create `producers/reddit_producer/.env`:
```bash
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=your_user_agent
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
```

### Rate Limiting
Adjust `producers/reddit_producer/config/config.yaml`:
```yaml
reddit:
  posts_per_minute: 10  # Max posts to fetch per minute (default: 10)
```

**How it works:**
- Fetches up to `posts_per_minute` new posts every minute
- Automatically skips duplicate posts
- Spreads requests evenly (e.g., 10 posts/min = 1 post every 6 seconds)
- Prevents Reddit API rate limiting

## Common Commands

### View Real-Time Predictions
```bash
# Check classified posts with ML predictions
docker exec -it cassandra cqlsh -e "SELECT subreddit, title, stress_score, stress_label FROM reddit_rt.classified_posts_by_hour WHERE subreddit = 'anxiety' AND hour_partition = '2025-10-19-14' LIMIT 10;"

# View Kafka messages
docker exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic reddit.posts.raw.v1 \
  --from-beginning \
  --max-messages 5
```

### Logs & Monitoring

**When using run.sh:**
```bash
# View live producer logs
tail -f logs/producer.log

# View live Spark ML logs
tail -f logs/spark_ml.log

# View both simultaneously
tail -f logs/producer.log logs/spark_ml.log
```

**When using Docker:**
```bash
# View producer logs
docker logs -f reddit-producer

# View Spark logs
docker logs -f reddit-spark-master
```

**Check Data:**
```bash
# Check raw data count
docker exec -it reddit-cassandra cqlsh -e "SELECT COUNT(*) FROM reddit_rt.raw_posts_by_day;"

# Check classified posts with ML predictions
docker exec -it reddit-cassandra cqlsh -e "SELECT * FROM reddit_rt.classified_posts_by_hour LIMIT 10;"
```

### Service Management
```bash
# Restart services
docker-compose restart

# Stop all
docker-compose down
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **Model not found** | Run `./train_reddit_stress_v4.sh` |
| **Kafka not connecting** | `docker-compose restart kafka` |
| **No data in Grafana** | Check if producer & Spark are running |
| **Out of memory** | Increase Docker memory to 4GB+ |
| **Python dependencies** | `pip install transformers torch pyspark` |

### Kafka Issues
```bash
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092
./scripts/init-kafka-topics.sh
```

### Cassandra Issues
```bash
docker exec -it cassandra nodetool status
docker exec -it cassandra cqlsh -e "DESCRIBE KEYSPACE reddit_rt;"
```

### ML Pipeline Issues
```bash
# Test model inference
python spark/model_inference.py

# Run integration test
./test_realtime_integration.sh
```

## Tech Stack

- **Streaming**: Apache Kafka, Apache Spark
- **Storage**: Apache Cassandra
- **ML**: DistilBERT, Hugging Face Transformers, Ollama
- **Orchestration**: Apache Airflow
- **Visualization**: Grafana
- **Language**: Python 3.8+

## What You'll See

### Spark Terminal (Real-Time ML)
```
[Batch 0] Processing 5 records...
[Batch 0] Stress detected: 3/5 (60.0%)
[Batch 0] ✓ Written to raw_posts_by_day
[Batch 0] ✓ Written to classified_posts_by_hour
[Batch 0] ✓ Batch processing complete
```

### Grafana Dashboard
- Real-time stress detection rate gauge
- Posts processed counter
- High-stress posts table with scores
- Trend graphs showing stress over time
- Per-subreddit breakdown

## Key Files

| Component | File | Description |
|-----------|------|-------------|
| **Run Pipeline** | `run.sh` | Start entire pipeline (one command) |
| **ML Inference** | `spark/model_inference.py` | v4 model wrapper |
| **ML Pipeline** | `spark/kafka_to_cassandra_with_ml.py` | Real-time ML streaming |
| **Basic Pipeline** | `spark/kafka_to_cassandra.py` | Basic streaming (no ML) |
| **v4 Model** | `ml/models/reddit_stress_v4/` | Trained model files |
| **Schema** | `cassandra/schema/*.cql` | Database schemas |
| **Integration Test** | `test_realtime_integration.sh` | Test all components |
| **Train v4** | `train_reddit_stress_v4.sh` | Train model script |
| **Test v4** | `test_v4_model.sh` | Test model accuracy |
| **Config** | `producers/reddit_producer/config/config.yaml` | Rate limiting & settings |

## Version

**Project Version**: 1.0.0
**Model Version**: v4 (DistilBERT)
**Last Updated**: October 2025

---

SE363 - Software Engineering Project
