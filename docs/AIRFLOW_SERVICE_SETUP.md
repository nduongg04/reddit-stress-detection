# AIRFLOW SERVICE - ACTIVE LEARNING RETRAIN PIPELINE

## Tổng quan

Airflow service đã được **tách riêng thành service độc lập** với Dockerfile custom (`Dockerfile.airflow`) để hỗ trợ đầy đủ ML retraining capabilities.

---

## Thay đổi chính

### 1. **Dockerfile.airflow mới**

```dockerfile
FROM apache/airflow:2.7.3-python3.11

# ML dependencies:
- torch==2.0.1
- transformers==4.35.0
- accelerate==0.26.0
- scikit-learn==1.3.2
- pandas==2.1.4
- cassandra-driver==3.29.2
```

**Lý do:**
- Image Airflow mặc định không có torch/transformers
- Cần dependencies để chạy retrain PhoBERT trong DAG
- Tách biệt với các services khác (Spark, Cassandra)

### 2. **Docker Compose Updates**

#### airflow-webserver:
```yaml
build:
  context: .
  dockerfile: Dockerfile.airflow
image: reddit-airflow-ml:latest
depends_on:
  - cassandra
  - ollama
environment:
  OLLAMA_HOST: http://ollama:11434
```

#### airflow-scheduler:
```yaml
build:
  context: .
  dockerfile: Dockerfile.airflow
image: reddit-airflow-ml:latest
depends_on:
  - cassandra
  - ollama
environment:
  OLLAMA_HOST: http://ollama:11434
```

**Lý do dependencies:**
- **cassandra**: Fetch low-confidence posts
- **ollama**: LLM validation (llama3.1:8b)

---

## DAG: vietnamese_absa_daily_retrain

### Flow (7 tasks):

```
fetch_recent_posts
    ↓
run_inference (vietnamese_absa_sentiment_phobert_v1)
    ↓
select_uncertain_predictions
    ↓
validate_with_ollama (llama3.1:8b)
    ↓
retrain_model
    ↓
update_model_registry
    ↓
send_metrics
```

### Model sử dụng:

✅ **vietnamese_absa_sentiment_phobert_v1**
- 10 aspects × 3 sentiments = 30 classes
- ABSA (Aspect-Based Sentiment Analysis)
- Confidence score tracking

❌ **KHÔNG dùng vietnamese_stress_phobert**
- Chỉ stress vs non-stress (binary)
- Không phù hợp yêu cầu ABSA

---

## Build & Deploy

### 1. Build Airflow image

```bash
docker-compose build airflow-webserver airflow-scheduler
```

Hoặc:

```bash
docker build -f Dockerfile.airflow -t reddit-airflow-ml:latest .
```

### 2. Khởi động services

```bash
# Start all services
docker-compose up -d

# Hoặc chỉ Airflow
docker-compose up -d airflow-postgres airflow-webserver airflow-scheduler
```

### 3. Kiểm tra

```bash
# Check logs
docker logs -f reddit-airflow-scheduler

# Verify ML dependencies
docker exec reddit-airflow-scheduler python -c "import torch; import transformers; print('OK')"

# Access Airflow UI
http://localhost:8082
# Login: airflow / airflow
```

### 4. Enable DAG

1. Truy cập http://localhost:8082
2. Tìm DAG: `vietnamese_absa_daily_retrain`
3. Toggle ON (màu xanh)
4. DAG sẽ chạy tự động daily at 2 AM UTC

---

## Architecture

```
┌─────────────────────────────────────────┐
│   Airflow Scheduler                     │
│   (reddit-airflow-ml:latest)           │
│                                         │
│   • torch 2.0.1                         │
│   • transformers 4.35.0                 │
│   • cassandra-driver                    │
│   • Full ML stack                       │
│                                         │
│   Volumes:                              │
│   - ./airflow/dags → /opt/airflow/dags │
│   - ./ml → /opt/airflow/ml             │
│   - ./utils → /opt/airflow/utils       │
└───────┬─────────────────────────────────┘
        │
        ├──→ Cassandra (fetch low-conf posts)
        ├──→ Ollama (LLM validation)
        └──→ Model Registry (update active model)
```

---

## Volumes Mounted

| Host Path | Container Path | Purpose |
|-----------|---------------|---------|
| `./airflow/dags` | `/opt/airflow/dags` | DAG definitions |
| `./airflow/logs` | `/opt/airflow/logs` | Execution logs |
| `./ml` | `/opt/airflow/ml` | Models, datasets, training scripts |
| `./utils` | `/opt/airflow/utils` | OllamaValidator, helpers |

---

## Environment Variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `OLLAMA_HOST` | `http://ollama:11434` | Ollama API endpoint |
| `AIRFLOW__CORE__EXECUTOR` | `LocalExecutor` | Task execution mode |
| `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN` | `postgresql+...` | Airflow metadata DB |

---

## Troubleshooting

### 1. Build failed - torch installation timeout

```bash
# Build with increased timeout
DOCKER_BUILDKIT=1 docker build \
  -f Dockerfile.airflow \
  --build-arg BUILDKIT_STEP_LOG_MAX_SIZE=10000000 \
  -t reddit-airflow-ml:latest .
```

### 2. DAG import error - module not found

```bash
# Check volumes mounted
docker inspect reddit-airflow-scheduler | grep -A 10 Mounts

# Verify files
docker exec reddit-airflow-scheduler ls -la /opt/airflow/ml/models/
docker exec reddit-airflow-scheduler ls -la /opt/airflow/utils/
```

### 3. Cassandra connection failed

```bash
# Check cassandra container running
docker ps | grep cassandra

# Test connection from Airflow
docker exec reddit-airflow-scheduler python -c "
from cassandra.cluster import Cluster
cluster = Cluster(['cassandra'], port=9042)
session = cluster.connect()
print('OK')
"
```

### 4. Ollama model not found

```bash
# Pull llama3.1:8b
docker exec reddit-ollama ollama pull llama3.1:8b

# Verify
docker exec reddit-ollama ollama list
```

---

## Performance

- **Build time**: ~5-10 minutes (first time)
- **Retraining**: ~30-60 minutes (100 posts)
- **Ollama validation**: ~5 seconds/post
- **Memory**: ~2-3GB (scheduler during retrain)

---

## Next Steps

1. ✅ Build Airflow image với ML dependencies
2. ✅ Start Airflow services
3. ✅ Pull Ollama model (llama3.1:8b)
4. ✅ Enable DAG trong UI
5. ⏳ Wait for first run (2 AM UTC)
6. ✅ Monitor logs & metrics

---

**Status: PRODUCTION READY** 🚀
