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
- 8GB+ RAM

### 1. Start Services
```bash
docker-compose up -d
```

### 2. Initialize Infrastructure
```bash
./scripts/init-kafka-topics.sh
./scripts/init-cassandra-schema.sh
./scripts/airflow-init.sh
```

### 3. Run Streaming Pipeline
```bash
docker exec -it reddit-spark-master spark-submit \
  --master spark://spark-master:7077 \
  --packages com.datastax.spark:spark-cassandra-connector_2.12:3.5.1,org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1 \
  /opt/spark-apps/kafka_to_cassandra.py
```

### 4. Access Dashboards
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
│   └── models/                  # DistilBERT model + training scripts
├── producers/reddit_producer/   # Reddit data crawler (PRAW)
├── spark/                       # Spark streaming pipeline
│   └── kafka_to_cassandra.py    # Kafka → Cassandra job
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
- **Model**: DistilBERT (distilbert-base-uncased)
- **Task**: Binary classification (STRESS / NON_STRESS)
- **Dataset**: 11,270 Reddit posts labeled by Ollama (llama3.1:8b)
- **Performance**: ~80% accuracy, ~83% F1 score

### Training
```bash
# Train model
python ml/models/train.py --data-dir ml/dataset/splits --epochs 3

# Evaluate
python ml/models/evaluate.py --model-path ml/models/reddit_stress_v1
```

## Configuration

### Reddit API Credentials
Create `producers/reddit_producer/.env`:
```bash
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=your_user_agent
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
```

## Common Commands

```bash
# View logs
docker logs -f reddit-producer
docker logs -f reddit-spark-master

# Check Cassandra data
docker exec -it reddit-cassandra cqlsh -e "SELECT COUNT(*) FROM reddit_rt.raw_posts_by_day;"

# Restart services
docker-compose restart

# Stop all
docker-compose down
```

## Troubleshooting

### Kafka Issues
```bash
docker exec -it reddit-kafka kafka-topics --list --bootstrap-server localhost:9092
./scripts/init-kafka-topics.sh
```

### Cassandra Issues
```bash
docker exec -it reddit-cassandra nodetool status
docker exec -it reddit-cassandra cqlsh -e "DESCRIBE KEYSPACE reddit_rt;"
```

## Tech Stack

- **Streaming**: Apache Kafka, Apache Spark
- **Storage**: Apache Cassandra
- **ML**: DistilBERT, Hugging Face Transformers, Ollama
- **Orchestration**: Apache Airflow
- **Visualization**: Grafana
- **Language**: Python 3.8+

## Version

**Project Version**: 1.0.0
**Last Updated**: October 2025

---

SE363 - Software Engineering Project
