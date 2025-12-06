# Hướng Dẫn Deployment - Active Learning với Confidence Score

## Tóm tắt

Document này hướng dẫn chi tiết cách deploy hệ thống Active Learning với confidence score tracking. Sau khi hoàn thành, hệ thống sẽ tự động:

1. ✅ Phát hiện posts có confidence score thấp (< 0.5)
2. ✅ Re-label với Ollama (100 posts/ngày)
3. ✅ Retrain model tự động (2 AM UTC hàng ngày)
4. ✅ Hot-reload model mới mà không cần restart Spark

---

## Prerequisites

- Docker Desktop đang chạy
- Tất cả services đã build: Airflow, Spark, Cassandra, Kafka, Ollama
- Model `vietnamese_absa_sentiment_phobert_v1` đã có trong `ml/models/`

---

## Bước 1: Apply Cassandra Schema

### Option A: Sử dụng script tự động (Recommended)

**Windows (PowerShell):**
```powershell
.\scripts\apply_confidence_score_schema.ps1
```

**Linux/Mac:**
```bash
chmod +x scripts/apply_confidence_score_schema.sh
./scripts/apply_confidence_score_schema.sh
```

Script sẽ:
- Check Cassandra container đang chạy
- Đợi Cassandra ready
- Thêm trường `confidence_scores map<text, double>` vào bảng
- Verify schema đã update thành công

### Option B: Manual (nếu script fail)

```bash
# 1. Connect to Cassandra
docker exec -it reddit-cassandra cqlsh

# 2. Apply schema change
USE reddit_rt;
ALTER TABLE classified_posts_by_hour 
ADD confidence_scores map<text, double>;

# 3. Verify
DESCRIBE TABLE classified_posts_by_hour;

# Should see:
#   confidence_scores map<text, double>,
```

---

## Bước 2: Restart Services

### 2.1. Restart Spark (để load code mới)

```bash
docker-compose restart spark-master spark-worker
```

**Verify:**
```bash
docker logs spark-master -f
# Should see: "Configuring Vietnamese ABSA PhoBERT model..."
```

### 2.2. Restart Airflow (để load DAG mới)

```bash
docker-compose restart airflow-webserver airflow-scheduler
```

**Verify:**
```bash
docker logs airflow-scheduler -f
# Should see: "Loaded DAG <vietnamese_absa_daily_retrain>"
```

---

## Bước 3: Setup Ollama Model

Ollama cần download model `llama3.1:8b` (~4.7GB) trước khi chạy validation.

### Option A: Sử dụng script (Recommended)

**Windows:**
```powershell
.\scripts\setup_ollama.ps1
```

**Linux/Mac:**
```bash
chmod +x scripts/setup_ollama.sh
./scripts/setup_ollama.sh
```

### Option B: Manual

```bash
# Wait for Ollama to start
docker logs reddit-ollama -f

# Pull model
docker exec reddit-ollama ollama pull llama3.1:8b

# Verify
docker exec reddit-ollama ollama list
# Should see: llama3.1:8b
```

---

## Bước 4: Enable Airflow DAG

### 4.1. Access Airflow UI

Open browser: **http://localhost:8082**

**Credentials:**
- Username: `airflow`
- Password: `airflow`

### 4.2. Enable DAG

1. Find DAG: `vietnamese_absa_daily_retrain`
2. Toggle switch từ OFF → ON
3. DAG status should be: 🟢 Active

### 4.3. Trigger Manual Test (Optional)

Để test ngay không cần đợi 2 AM:

1. Click vào DAG name
2. Click nút ▶️ "Trigger DAG" (góc phải trên)
3. Confirm

**Monitor execution:**
- Click vào DAG run (hình tròn màu)
- Click vào task để xem logs
- Check các task chạy theo thứ tự:
  ```
  fetch_recent_posts → run_inference → select_uncertain_predictions → 
  validate_with_ollama → retrain_model → update_model_registry → send_metrics
  ```

---

## Bước 5: Verify Pipeline

### 5.1. Check Spark đang ghi confidence_scores

```bash
# Check Spark logs
docker logs spark-master -f

# Should see batches với confidence_scores:
# [Batch 0] Sample predictions:
# +----------+------------------------+------------------+------------------+
# |subreddit |title                   |aspect_sentiments |confidence_scores |
# +----------+------------------------+------------------+------------------+
# |vozforums |Mình stress công việc...|{công_việc -> -1} |{công_việc -> 0.42}|
# +----------+------------------------+------------------+------------------+
```

### 5.2. Check Cassandra có confidence_scores

```bash
docker exec -it reddit-cassandra cqlsh

USE reddit_rt;

SELECT post_id, confidence_scores
FROM classified_posts_by_hour
WHERE subreddit = 'vozforums'
  AND hour_partition = '2025-12-04-14'
LIMIT 5;
```

**Expected output:**
```
 post_id | confidence_scores
---------+-------------------------------------------------------
 abc123  | {'công_việc': 0.42, 'giấc_ngủ_thuốc': 0.38, ...}
 xyz789  | {'tình_yêu': 0.87, 'gia_đình': 0.92, ...}
```

### 5.3. Check Airflow DAG logs

```bash
# Check scheduler logs
docker logs airflow-scheduler -f

# Check task logs in Airflow UI:
# 1. Click on DAG run
# 2. Click on task "fetch_recent_posts"
# 3. Click "Log" button
# Should see: "Fetched X LOW-CONFIDENCE posts (confidence < 0.5)"
```

---

## Troubleshooting

### Issue 1: Cassandra ALTER TABLE failed

**Error:**
```
InvalidRequest: Error from server: code=2200 [Invalid query] 
message="Cannot add new column to a compact table"
```

**Solution:**
Bảng cũ dùng compact storage. Cần recreate table:

```sql
-- Backup data
COPY reddit_rt.classified_posts_by_hour TO 'backup.csv';

-- Drop and recreate
DROP TABLE reddit_rt.classified_posts_by_hour;

-- Run full schema script
docker exec -i reddit-cassandra cqlsh < cassandra/schema/03_classified_posts_by_hour.cql

-- Restore data (if needed)
COPY reddit_rt.classified_posts_by_hour FROM 'backup.csv';
```

---

### Issue 2: Airflow không thấy DAG

**Symptoms:**
- DAG không xuất hiện trong Airflow UI
- Scheduler logs: "Broken DAG: No module named 'ml.models'"

**Solution:**

```bash
# Check volumes mounted
docker inspect reddit-airflow-scheduler | grep -A 10 Mounts

# Should see:
#   ./ml:/opt/airflow/ml
#   ./utils:/opt/airflow/utils

# If missing, restart with docker-compose
docker-compose down
docker-compose up -d
```

---

### Issue 3: Spark không ghi confidence_scores

**Symptoms:**
- Cassandra có `confidence_scores = NULL` cho tất cả posts
- Spark logs không show confidence_scores trong sample output

**Solution:**

```bash
# 1. Check model file exists
docker exec spark-master ls -la /opt/ml/models/vietnamese_absa_sentiment_phobert_v1/

# 2. Check Spark code loaded
docker exec spark-master cat /opt/spark-apps/model_inference_absa.py | grep "confidence_scores"

# 3. Restart Spark
docker-compose restart spark-master spark-worker

# 4. Check logs again
docker logs spark-master -f
```

---

### Issue 4: DAG fetch 0 posts

**Symptoms:**
- Task `fetch_recent_posts` logs: "Fetched 0 LOW-CONFIDENCE posts"
- DAG skips execution

**Possible causes:**

1. **No data in Cassandra yet:**
   - Wait for Kafka producer to send data
   - Wait for Spark to process and write to Cassandra

2. **All posts have high confidence (> 0.5):**
   - Model quá tự tin
   - Có thể tăng threshold lên 0.6 hoặc 0.7

3. **Wrong time partition:**
   - Check Cassandra có data trong 24h qua
   ```sql
   SELECT hour_partition, COUNT(*)
   FROM classified_posts_by_hour
   GROUP BY hour_partition;
   ```

**Solution:**
```python
# Adjust threshold in DAG (airflow/dags/vietnamese_absa_retrain.py)
# Line ~115:
if min_confidence < 0.7:  # Changed from 0.5 to 0.7
    posts.append({...})
```

---

### Issue 5: Ollama validation timeout

**Symptoms:**
- Task `validate_with_ollama` fails
- Error: "Connection timeout to Ollama"

**Solution:**

```bash
# 1. Check Ollama running
docker ps | grep ollama

# 2. Check Ollama health
curl http://localhost:11434/api/tags

# 3. Check model loaded
docker exec reddit-ollama ollama list

# 4. If not loaded, pull model
docker exec reddit-ollama ollama pull llama3.1:8b

# 5. Restart Airflow
docker-compose restart airflow-webserver airflow-scheduler
```

---

## Monitoring & Metrics

### Check retrain metrics

```bash
# View retrain logs
cat airflow/logs/retraining_metrics.jsonl

# Should see JSON records like:
# {
#   "timestamp": "2025-12-04T02:00:00",
#   "model_version": "20251204_020000",
#   "validated_samples": 87,
#   "test_f1_micro": 0.952,
#   "test_f1_macro": 0.948
# }
```

### Check model registry

```bash
# View active models
docker exec spark-master cat /opt/ml/models/registry/registry.json

# Should see:
# {
#   "models": [
#     {
#       "version": "v1",
#       "model_dir": "/opt/ml/models/vietnamese_absa_sentiment_phobert_v1",
#       "active": false
#     },
#     {
#       "version": "20251204_020000",
#       "model_dir": "/opt/ml/models/vietnamese_absa_phobert_20251204_020000",
#       "active": true,
#       "test_f1_micro": 0.952
#     }
#   ]
# }
```

### Check Spark using new model

```bash
docker logs spark-master | grep "model version"

# Should see:
# [INFO] New model version detected: 20251204_020000
# [INFO] Reloading model: /opt/ml/models/vietnamese_absa_phobert_20251204_020000
# [INFO] ✓ Model loaded successfully
```

---

## Daily Operation

### Automatic Schedule

DAG chạy tự động **mỗi ngày lúc 2 AM UTC**:

```python
schedule_interval='0 2 * * *'  # 2 AM UTC = 9 AM Vietnam
```

**Timeline:**
- 2:00 AM - Fetch low-confidence posts (last 24h)
- 2:05 AM - Run inference
- 2:10 AM - Select uncertain predictions (top 100)
- 2:15 AM - Validate with Ollama (~10-15 phút cho 100 posts)
- 2:30 AM - Retrain model (~30-60 phút)
- 3:30 AM - Update registry
- 3:31 AM - Spark hot-reload model mới

### Manual Trigger

Nếu muốn chạy ngay:

1. Airflow UI → DAG `vietnamese_absa_daily_retrain`
2. Click ▶️ "Trigger DAG"
3. Monitor execution trong Graph View

### Stop DAG

Để tạm dừng auto-retrain:

1. Airflow UI → Toggle DAG OFF
2. DAG sẽ không chạy theo schedule nữa

---

## Expected Results

Sau khi deploy thành công:

✅ **Spark streaming:**
- Ghi `confidence_scores` vào Cassandra cho mỗi post
- Sample output shows aspect_sentiments + confidence_scores

✅ **Cassandra:**
- Bảng `classified_posts_by_hour` có trường `confidence_scores`
- Query trả về map: `{'công_việc': 0.42, 'tình_yêu': 0.87, ...}`

✅ **Airflow DAG:**
- Fetch ~50-100 low-confidence posts mỗi ngày (tùy traffic)
- Re-label với Ollama (100% automated)
- Retrain model với dữ liệu mới
- Update registry

✅ **Model versioning:**
- Model mới lưu tại `/opt/ml/models/vietnamese_absa_phobert_TIMESTAMP`
- Registry update với `active: true`
- Spark auto-reload model mới

✅ **Metrics:**
- F1 score tracking qua từng lần retrain
- Logs trong `retraining_metrics.jsonl`

---

## Summary

Pipeline đã được cập nhật để:

1. **Track confidence scores** - Mỗi prediction giờ có confidence score (0.0-1.0)
2. **Filter low-confidence** - Chỉ chọn posts model "không chắc chắn" (< 0.5)
3. **Limit 100 posts/day** - Tránh tràn RAM, tối ưu compute
4. **Use correct model** - ABSA model (30 labels) thay vì model cũ (10 labels)
5. **Automated retraining** - Ollama validate → Retrain → Hot-reload (không cần restart)

**Flow hoạt động hiệu quả, tự động, và chính xác!** 🚀
