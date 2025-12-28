# PhoBERT Retrain Setup Guide
## Hướng 1: Tách Training Service riêng

## 📋 Tổng quan

### Kiến trúc mới:
```
Airflow Scheduler (4GB RAM)
    ↓ HTTP API
Training Service (12GB RAM) → Train PhoBERT (135M params)
    ↓ Shared Volume
Model Registry ← Airflow reads
```

### Lợi ích:
- ✅ Airflow không bị OOM (chỉ orchestrate)
- ✅ Training Service có resource riêng (12GB RAM, 4 CPUs)
- ✅ Có thể scale training service độc lập
- ✅ Dễ upgrade lên GPU sau này

---

## 🚀 Setup Instructions

### 1. Build Training Service Image

```powershell
# Build Dockerfile
docker-compose build training-service
```

### 2. Start Training Service

```powershell
# Start only training service (test riêng trước)
docker-compose up -d training-service

# Check logs
docker logs reddit-training-service -f

# Expected output:
# * Running on http://0.0.0.0:5000
# * Serving Flask app 'app'
```

### 3. Test API Health

```powershell
# Health check
curl http://localhost:5000/health

# Expected response:
# {"status": "healthy", "service": "training-api"}
```

### 4. Test Training Job (Manual)

```powershell
# Tạo test data file (nếu chưa có)
# Hoặc dùng file có sẵn: ml/dataset/labeled/vozforums_absa_labeled.csv

# Trigger training job
$body = @{
    model_type = "phobert"
    data_file = "/workspace/ml/dataset/labeled/vozforums_absa_labeled.csv"
    config = @{
        num_epochs = 2
        batch_size = 4
        gradient_accumulation_steps = 4
        learning_rate = 0.00002
        mixed_precision = $true
    }
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
    -Uri "http://localhost:5000/api/train" `
    -Body $body `
    -ContentType "application/json"

# Expected response:
# {
#   "job_id": "uuid-here",
#   "state": "queued",
#   "message": "Training job started"
# }
```

### 5. Monitor Job Status

```powershell
# Replace <job-id> with actual job ID from step 4
$jobId = "your-job-id-here"

# Check status
Invoke-RestMethod -Uri "http://localhost:5000/api/jobs/$jobId"

# Expected states:
# - queued: Đang chờ
# - running: Đang train
# - completed: Hoàn thành (model_dir có trong response)
# - failed: Lỗi (error có trong response)

# Check logs
Invoke-RestMethod -Uri "http://localhost:5000/api/jobs/$jobId/logs"
```

### 6. Start Full Stack with Airflow

```powershell
# Start tất cả services (bao gồm training-service)
docker-compose up -d cassandra ollama airflow-postgres airflow-scheduler training-service

# Check all containers
docker ps --filter "name=reddit-" --format "table {{.Names}}\t{{.Status}}"

# Expected:
# reddit-training-service    Up (healthy)
# reddit-airflow-scheduler   Up
# reddit-airflow-postgres    Up (healthy)
# reddit-cassandra           Up (healthy)
# reddit-ollama              Up
```

### 7. Deploy Updated DAG

```powershell
# Copy updated DAG to scheduler
docker cp airflow/dags/vietnamese_absa_retrain.py `
    reddit-airflow-scheduler:/opt/airflow/dags/

# Verify
docker exec reddit-airflow-scheduler ls -lh /opt/airflow/dags/vietnamese_absa_retrain.py
```

### 8. Trigger DAG

```powershell
# Via Airflow CLI
docker exec reddit-airflow-scheduler `
    airflow dags trigger vietnamese_absa_daily_retrain

# Hoặc via Web UI: http://localhost:8082
```

---

## 🔍 Monitoring & Debugging

### Check Training Service Logs

```powershell
# Real-time logs
docker logs reddit-training-service -f

# Last 100 lines
docker logs reddit-training-service --tail 100
```

### Check Airflow Task Logs

```powershell
# Task 5 (retrain_model) logs
docker exec reddit-airflow-scheduler cat /opt/airflow/logs/dag_id=vietnamese_absa_daily_retrain/run_id=manual__*/task_id=retrain_model/attempt=1.log
```

### Check Model Output

```powershell
# List trained models
docker exec reddit-training-service ls -lh /workspace/ml/models/

# Check metadata
docker exec reddit-training-service cat /workspace/ml/models/vietnamese_absa_phobert_retrained_*/metadata.json
```

### API Endpoints Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/api/train` | POST | Start training job |
| `/api/jobs/<job_id>` | GET | Get job status |
| `/api/jobs/<job_id>/logs` | GET | Get training logs |
| `/api/jobs` | GET | List all jobs |

---

## 📊 Resource Configuration

### Training Service (docker-compose.yml)

```yaml
training-service:
  deploy:
    resources:
      limits:
        memory: 12G    # PhoBERT cần ~8-10GB peak
        cpus: '4.0'
      reservations:
        memory: 8G
```

### PhoBERT Training Config (train_phobert_retrain.py)

```python
CONFIG = {
    'batch_size': 8,                    # Small batch
    'gradient_accumulation_steps': 4,   # Effective batch = 32
    'mixed_precision': True,            # FP16 → Save 50% RAM
    'num_epochs': 5,
    'learning_rate': 2e-5,
}
```

**Memory breakdown:**
- PhoBERT model: ~2GB
- Optimizer states: ~2GB
- Gradients: ~2GB
- Activations (batch=8): ~2-3GB
- **Total: ~8-9GB peak**

---

## 🐛 Troubleshooting

### Problem: Training Service không start

```powershell
# Check logs for errors
docker logs reddit-training-service

# Common issues:
# 1. Port 5000 already in use
#    → Change port in docker-compose.yml
# 2. Missing dependencies
#    → Rebuild: docker-compose build training-service
```

### Problem: OOM khi training

```powershell
# Giảm batch size trong DAG
# Edit airflow/dags/vietnamese_absa_retrain.py line ~480:
'batch_size': 4,  # Giảm từ 8
'gradient_accumulation_steps': 8,  # Tăng từ 4 (giữ effective batch = 32)

# Hoặc tăng Docker memory limit
# Edit docker-compose.yml:
memory: 16G  # Tăng từ 12G
```

### Problem: Airflow không connect được Training Service

```powershell
# Check network
docker exec reddit-airflow-scheduler ping training-service

# Check DNS
docker exec reddit-airflow-scheduler nslookup training-service

# Both services phải cùng network: reddit-network
```

### Problem: Training timeout

```powershell
# Tăng timeout trong DAG (line ~530)
max_wait_time = 7200  # 2 hours (tăng từ 1 hour)

# PhoBERT training time estimate:
# - 100 samples, 5 epochs: ~10-15 minutes
# - 1000 samples, 5 epochs: ~1-2 hours
```

---

## 🎯 Expected Workflow

### End-to-End Flow:

1. **Airflow Task 1-4**: Fetch, inference, select, validate (chạy bình thường)

2. **Airflow Task 5** (retrain_model):
   ```
   → Prepare combined dataset
   → Call Training Service API: POST /api/train
   → Receive job_id
   → Poll GET /api/jobs/{job_id} every 30s
   → Wait for state = "completed"
   → Return model_dir
   ```

3. **Training Service**:
   ```
   → Receive API request
   → Start background thread
   → Load PhoBERT + data
   → Train 5 epochs (~1 hour)
   → Save model to /workspace/ml/models/
   → Update job state = "completed"
   ```

4. **Airflow Task 6-7**: Update registry, send metrics (như cũ)

### Success Indicators:

- ✅ Task 5 log: "Training job started: <job_id>"
- ✅ Training Service log: "Training PhoBERT..."
- ✅ Task 5 log: "Training completed successfully!"
- ✅ Model file exists: `/workspace/ml/models/vietnamese_absa_phobert_retrained_*/model.pt`
- ✅ Task 6 success: Registry updated

---

## 📈 Next Steps (Optional)

### 1. Add GPU Support

```yaml
# docker-compose.yml
training-service:
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

### 2. Add Job Queue (Redis)

Replace in-memory `jobs` dict with Redis for persistence.

### 3. Add Monitoring

- Prometheus metrics endpoint
- Grafana dashboard for training jobs
- Email notifications on completion/failure

### 4. Cloud Migration

- Move Training Service to dedicated GPU instance
- Use S3/Azure Blob for model storage
- Keep Airflow on lightweight instance

---

## 📝 Summary

**Files created:**
1. `training_service/app.py` - Flask API server
2. `ml/models/train_phobert_retrain.py` - PhoBERT training script
3. `Dockerfile.training` - Training service image
4. `training_service/requirements.txt` - Python dependencies

**Files modified:**
1. `docker-compose.yml` - Added training-service
2. `airflow/dags/vietnamese_absa_retrain.py` - Task 5 calls API

**Key changes:**
- Airflow scheduler: Không train trực tiếp (tránh OOM)
- Training service: Dedicated 12GB RAM, 4 CPUs
- Communication: HTTP REST API
- Model storage: Shared Docker volume

**Model comparison:**
| Model | Parameters | Training Time | RAM Usage |
|-------|------------|---------------|-----------|
| BiLSTM (old) | 8.9M | ~20s | ~1-2GB |
| PhoBERT (new) | 135M | ~1h | ~8-10GB |

Bạn đã sẵn sàng để test! 🚀
