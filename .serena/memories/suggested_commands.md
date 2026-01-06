# Suggested Commands

## Setup & Installation

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Running the Pipeline

```bash
# Start complete pipeline (recommended - auto-configures everything)
./run.sh

# Start only Docker services
docker-compose up -d

# Stop all services
docker-compose down
```

## Model Training

```bash
# Train Vietnamese PhoBERT ABSA model
./train_vietnamese_stress.sh

# Test trained model
./test_vietnamese_model.sh

# Collect stress data from r/vozforums
./collect_vozforums_stress.sh

# Export Vietnamese posts from Cassandra
python scripts/export_vietnamese_from_cassandra.py

# Prepare dataset with train/val/test splits
python scripts/prepare_vozforums_dataset.py

# Train ABSA model manually
python ml/models/train_absa_phobert.py
```

## Testing & Validation

```bash
# Test model on custom inputs
python ml/models/test_model.py --model-path ml/models/vietnamese_absa_sentiment_phobert_v1

# Test model on dataset
python ml/models/test_model.py --dataset path/to/test.csv

# Check GPU availability
python ml/models/check_gpu.py
```

## Monitoring & Debugging

```bash
# View producer logs
tail -f logs/reddit_producer.log

# View Spark logs
docker logs -f reddit-spark-master

# Check Kafka messages
docker exec reddit-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic reddit.posts.raw.v1 --max-messages 5

# Access Cassandra shell
docker exec -it reddit-cassandra cqlsh

# Query classified posts
docker exec reddit-cassandra cqlsh -e \
  "SELECT * FROM reddit_rt.classified_posts_by_hour LIMIT 10;"
```

## Docker Commands

```bash
# Rebuild Spark image
docker-compose build spark-master spark-worker

# View running containers
docker ps

# View all logs
docker-compose logs -f

# Restart specific service
docker-compose restart kafka
```

## Dashboard URLs

- **Streamlit ABSA**: http://localhost:8501
- **Grafana**: http://localhost:3000 (admin/admin)
- **Kafka UI**: http://localhost:8080
- **Spark UI**: http://localhost:8081
- **Airflow**: http://localhost:8082 (airflow/airflow)

## Git Commands (Darwin/macOS)

```bash
git status
git add .
git commit -m "message"
git push origin main
git log --oneline -10
```
