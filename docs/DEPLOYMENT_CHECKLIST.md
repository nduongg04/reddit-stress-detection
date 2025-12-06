# ✅ Deployment Checklist - Confidence Score Update

## Quick Reference - Các bước deploy

### Phase 1: Code Changes ✅ DONE
- [x] Cassandra schema: Thêm `confidence_scores map<text, double>`
- [x] Spark inference: Tính và return confidence_scores
- [x] Spark streaming: Ghi confidence_scores vào Cassandra
- [x] Airflow DAG: Query low-confidence posts (< 0.5), dùng đúng model ABSA
- [x] Docker compose: Mount ./ml và ./utils vào Airflow containers
- [x] Scripts: Tạo apply_confidence_score_schema.ps1/.sh

### Phase 2: Database Setup
```powershell
# Windows
.\scripts\apply_confidence_score_schema.ps1

# Linux/Mac
chmod +x scripts/apply_confidence_score_schema.sh
./scripts/apply_confidence_score_schema.sh
```

**Verify:**
- [ ] Script output: "✓ confidence_scores field is present in schema"

### Phase 3: Service Restart
```bash
# Restart Spark
docker-compose restart spark-master spark-worker

# Restart Airflow
docker-compose restart airflow-webserver airflow-scheduler
```

**Verify:**
- [ ] Spark logs: "Configuring Vietnamese ABSA PhoBERT model..."
- [ ] Airflow logs: "Loaded DAG <vietnamese_absa_daily_retrain>"

### Phase 4: Ollama Setup
```powershell
# Windows
.\scripts\setup_ollama.ps1

# Linux/Mac
chmod +x scripts/setup_ollama.sh
./scripts/setup_ollama.sh
```

**Verify:**
- [ ] Command output: "Successfully pulled llama3.1:8b"
- [ ] `docker exec reddit-ollama ollama list` shows llama3.1:8b

### Phase 5: Enable DAG
1. [ ] Open http://localhost:8082 (airflow/airflow)
2. [ ] Find DAG: `vietnamese_absa_daily_retrain`
3. [ ] Toggle switch: OFF → ON (🟢 Active)
4. [ ] Optional: Trigger manual test run

### Phase 6: Verification

#### 6.1. Spark Writing Confidence Scores
```bash
docker logs spark-master -f
```
- [ ] See batches with confidence_scores in output

#### 6.2. Cassandra Has Data
```sql
docker exec -it reddit-cassandra cqlsh

USE reddit_rt;
SELECT post_id, confidence_scores FROM classified_posts_by_hour LIMIT 3;
```
- [ ] Query returns non-NULL confidence_scores

#### 6.3. Airflow DAG Working
```bash
docker logs airflow-scheduler -f
```
- [ ] See: "Fetched X LOW-CONFIDENCE posts (confidence < 0.5)"
- [ ] Tasks complete without errors

---

## Troubleshooting Quick Fixes

### Cassandra schema error
```bash
# Recreate table if needed
docker exec -it reddit-cassandra cqlsh < cassandra/schema/03_classified_posts_by_hour.cql
```

### Airflow can't find modules
```bash
# Verify volumes mounted
docker inspect reddit-airflow-scheduler | grep "ml\|utils"

# If missing
docker-compose down
docker-compose up -d
```

### Spark not writing confidence_scores
```bash
# Check model exists
docker exec spark-master ls /opt/ml/models/vietnamese_absa_sentiment_phobert_v1/

# Restart Spark
docker-compose restart spark-master spark-worker
```

### DAG fetch 0 posts
```bash
# Check Cassandra has data in last 24h
docker exec -it reddit-cassandra cqlsh -e "
USE reddit_rt;
SELECT hour_partition, COUNT(*) FROM classified_posts_by_hour GROUP BY hour_partition;
"

# Adjust threshold in DAG if needed (increase from 0.5 to 0.7)
```

### Ollama timeout
```bash
# Check Ollama health
curl http://localhost:11434/api/tags

# Pull model if missing
docker exec reddit-ollama ollama pull llama3.1:8b
```

---

## Success Criteria

✅ **All checks passed when:**

1. **Cassandra:**
   - `confidence_scores` field exists in schema
   - Query returns map values like `{'công_việc': 0.42, ...}`

2. **Spark:**
   - Logs show "confidence_scores" in sample predictions
   - No errors in streaming pipeline

3. **Airflow:**
   - DAG visible and enabled in UI
   - Can fetch low-confidence posts
   - Tasks complete successfully

4. **Ollama:**
   - Model llama3.1:8b loaded
   - Can generate responses
   - API accessible at http://localhost:11434

5. **End-to-End:**
   - Kafka → Spark → Cassandra pipeline running
   - Low-confidence posts detected and stored
   - DAG can query and process them
   - Retrain flow completes without errors

---

## Daily Operation

**Automatic Schedule:** 2 AM UTC (9 AM Vietnam)

**Manual Trigger:** Airflow UI → DAG → ▶️ Trigger

**Monitor:** 
- Airflow UI: Task logs
- `cat airflow/logs/retraining_metrics.jsonl`
- `docker exec spark-master cat /opt/ml/models/registry/registry.json`

**Stop/Pause:** Airflow UI → Toggle DAG OFF

---

## Quick Commands Reference

```bash
# Apply schema
.\scripts\apply_confidence_score_schema.ps1

# Restart services
docker-compose restart spark-master spark-worker airflow-webserver airflow-scheduler

# Setup Ollama
.\scripts\setup_ollama.ps1

# Check Cassandra data
docker exec -it reddit-cassandra cqlsh -e "USE reddit_rt; SELECT * FROM classified_posts_by_hour LIMIT 3;"

# Check Spark logs
docker logs spark-master -f

# Check Airflow logs
docker logs airflow-scheduler -f

# View registry
docker exec spark-master cat /opt/ml/models/registry/registry.json

# View metrics
cat airflow/logs/retraining_metrics.jsonl
```

---

## Documentation

- **Full details:** `docs/CONFIDENCE_SCORE_UPDATE.md`
- **Deployment guide:** `docs/DEPLOYMENT_GUIDE.md`
- **This checklist:** `docs/DEPLOYMENT_CHECKLIST.md`

---

**Status:** Ready to deploy! 🚀

Follow checklist từ trên xuống, verify từng bước, và hệ thống sẽ chạy tự động với Active Learning!
