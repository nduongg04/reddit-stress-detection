# TASK-019 to TASK-045: Model Integration, Optimization & Production Deployment

**Owner:** ML Engineer, Data Engineer, DataOps/Viz Engineer (All Team Members)
**Priority:** Critical
**Dependencies:** TASK-018 (Dataset Collection & Labeling)
**Estimate:** 3 weeks (remaining project time)

---

## Overview

This consolidated task breakdown covers all remaining work from model training through production deployment, including:

- **Phase 3:** Model Integration (TASK-019 to TASK-029)
- **Phase 4:** Optimization & QA (TASK-030 to TASK-042)
- **Post-Launch:** Monitoring & Optimization (TASK-043 to TASK-045)

---

# PHASE 3: MODEL INTEGRATION (Week 3)

## TASK-019: Model Selection & Fine-Tuning (3 days)

### Quick Steps:

1. **Choose base model:** DistilBERT (`distilbert-base-uncased`) - smaller, faster
2. **Install dependencies:**

   ```bash
   pip install transformers torch scikit-learn pandas
   ```

3. **Training script:** `ml/models/train.py`

   ```python
   from transformers import DistilBertForSequenceClassification, DistilBertTokenizer, Trainer, TrainingArguments
   import pandas as pd

   # Load data
   train = pd.read_csv('ml/dataset/splits/train.csv')
   val = pd.read_csv('ml/dataset/splits/val.csv')

   # Initialize model
   model = DistilBertForSequenceClassification.from_pretrained('distilbert-base-uncased', num_labels=2)
   tokenizer = DistilBertTokenizer.from_pretrained('distilbert-base-uncased')

   # Tokenize
   train_encodings = tokenizer(train['text'].tolist(), truncation=True, padding=True, max_length=512)
   val_encodings = tokenizer(val['text'].tolist(), truncation=True, padding=True, max_length=512)

   # Training arguments
   training_args = TrainingArguments(
       output_dir='ml/models/checkpoints',
       num_train_epochs=3,
       per_device_train_batch_size=16,
       learning_rate=2e-5,
       evaluation_strategy="epoch",
       save_strategy="epoch",
       load_best_model_at_end=True
   )

   # Train
   trainer = Trainer(model=model, args=training_args, train_dataset=train_dataset, eval_dataset=val_dataset)
   trainer.train()

   # Save
   model.save_pretrained('ml/models/reddit_stress_v1')
   tokenizer.save_pretrained('ml/models/reddit_stress_v1')
   ```

4. **Evaluate:**

   ```python
   from sklearn.metrics import classification_report

   predictions = trainer.predict(test_dataset)
   print(classification_report(test_labels, predictions.predictions.argmax(-1)))
   ```

**Target Metrics:**

- Accuracy ≥0.80
- Precision ≥0.82
- Recall ≥0.85
- F1 Score ≥0.83

---

## TASK-020: Model Inference Integration (2 days)

### Quick Steps:

1. **Replace dummy model in Spark:** Update `spark/streaming/model_inference.py`

   ```python
   from pyspark.sql.functions import pandas_udf, PandasUDFType
   from transformers import pipeline

   # Load model once (broadcast to workers)
   model = pipeline("text-classification", model="ml/models/reddit_stress_v1")

   @pandas_udf("struct<stress_label:string, stress_score:double>")
   def predict_stress(texts):
       results = model(texts.tolist(), batch_size=32)
       return pd.DataFrame({
           'stress_label': [r['label'] for r in results],
           'stress_score': [r['score'] for r in results]
       })

   # Use in streaming pipeline
   df.withColumn("prediction", predict_stress("text"))
   ```

2. **Test inference latency:** Target <100ms per post

---

## TASK-021: Model Versioning & Registry (1.5 days)

### Quick Steps:

1. **Create model storage structure:**

   ```bash
   mkdir -p ml/models/registry/{v1,v2,metadata}
   ```

2. **Save with metadata:**

   ```python
   import json
   metadata = {
       "version": "1.0.0",
       "training_date": "2024-10-07",
       "metrics": {"accuracy": 0.85, "f1": 0.84},
       "dataset_version": "1.0.0"
   }
   with open('ml/models/registry/v1/metadata.json', 'w') as f:
       json.dump(metadata, f)
   ```

3. **Version control:** Use DVC or git-lfs for model files

---

## TASK-022: Model Training Airflow DAG (2 days)

### Quick Steps:

1. **Create DAG:** `airflow/dags/model_training.py`

   ```python
   from airflow import DAG
   from airflow.operators.python import PythonOperator
   from datetime import datetime

   def train_model():
       # Run training script
       import subprocess
       subprocess.run(["python", "ml/models/train.py"])

   with DAG('model_train_register', start_date=datetime(2024,10,1), schedule_interval='@weekly') as dag:
       train = PythonOperator(task_id='train_model', python_callable=train_model)
   ```

2. **Schedule:** Weekly on Sunday 3:00 AM UTC

---

## TASK-023: DLQ Monitoring Dashboard (1 day)

### Quick Steps:

1. **Add panel to Grafana System Health dashboard**
2. **Query DLQ metrics:**
   ```sql
   SELECT COUNT(*) as dlq_count FROM reddit_rt.dlq_messages
   WHERE hour_bucket >= now() - 24h
   ```
3. **Alert:** If DLQ rate >5%

---

## TASK-024: Producer Metrics & Health Checks (1 day)

### Quick Steps:

1. **Already implemented in TASK-009** (health endpoint)
2. **Add Prometheus metrics:**

   ```python
   from prometheus_client import Counter, Histogram

   messages_sent = Counter('reddit_messages_sent_total', 'Messages sent')
   api_latency = Histogram('reddit_api_latency_seconds', 'API latency')
   ```

---

## TASK-025: Kafka Configuration Optimization (1 day)

### Quick Steps:

1. **Tune Kafka settings in docker-compose.yml:**
   ```yaml
   KAFKA_NUM_PARTITIONS: 6
   KAFKA_DEFAULT_REPLICATION_FACTOR: 1
   KAFKA_LOG_RETENTION_HOURS: 168
   ```
2. **Test with load:** 5k posts/min

---

## TASK-026: Alerting Rules Configuration (1.5 days)

### Quick Steps:

1. **Configure Grafana alerts:**

   - No data >5 min
   - Stress % deviation >2σ
   - Pipeline latency >120s
   - Error rate >5%

2. **Notification channels:** Slack, Email

---

## TASK-027: Producer Control Airflow DAG (1 day)

### Quick Steps:

1. **Create health check DAG:**
   ```python
   with DAG('producer_ctl', schedule_interval='*/5 * * * *') as dag:
       check_health = BashOperator(task_id='health', bash_command='curl http://reddit-producer:8080/health')
   ```

---

## TASK-028: Backfill Airflow DAG (1 day)

### Quick Steps:

1. **Create nightly backfill DAG:**
   ```python
   with DAG('psaw_backfill_daily', schedule_interval='0 2 * * *') as dag:
       backfill = PythonOperator(task_id='backfill', python_callable=run_backfill)
   ```

---

## TASK-029: Slack Integration (0.5 days)

### Quick Steps:

1. **Create Slack webhook**
2. **Add to Grafana notification channels**
3. **Test alerts**

---

# PHASE 4: OPTIMIZATION & QA (Week 4)

## TASK-030: Load Testing & Stress Testing (2 days)

### Quick Steps:

1. **Use mock producer to generate 5k posts/min**
2. **Measure end-to-end latency**
3. **Test failure recovery**
4. **Document performance**

---

## TASK-031: Architecture Documentation (2 days)

### Quick Steps:

1. **Create diagrams:** Use draw.io or mermaid
   ```mermaid
   graph LR
       A[Reddit API] --> B[Kafka]
       B --> C[Spark Streaming]
       C --> D[Cassandra]
       D --> E[Grafana]
   ```
2. **Document setup guide**
3. **Write troubleshooting guide**

---

## TASK-032: Security Hardening (2 days)

### Quick Steps:

1. **Enable TLS for Kafka, Cassandra**
2. **Use secrets manager for credentials**
3. **Hash PII (usernames)**
4. **Enable RBAC in Grafana**
5. **Run security audit**

---

## TASK-033: Model Drift Detection (2 days)

### Quick Steps:

1. **Track prediction distribution over time**
2. **Alert if stress % changes >10% week-over-week**
3. **Add to System Health dashboard**

---

## TASK-034: Batch Size & Parallelism Optimization (1.5 days)

### Quick Steps:

1. **Tune Spark settings:**
   ```python
   spark.conf.set("spark.sql.shuffle.partitions", "200")
   spark.conf.set("spark.executor.cores", "4")
   spark.conf.set("spark.executor.memory", "8g")
   ```
2. **Test different batch sizes for PandasUDF**

---

## TASK-035: Performance Tuning (1 day)

### Quick Steps:

1. **Profile Spark job**
2. **Optimize memory usage**
3. **Minimize shuffles**

---

## TASK-036: Comprehensive Monitoring Setup (2 days)

### Quick Steps:

1. **Set up Prometheus exporters:**
   - Kafka JMX exporter
   - Spark metrics
   - Cassandra JMX exporter
2. **Centralized logging:** ELK stack or CloudWatch
3. **Distributed tracing:** Jaeger (optional)

---

## TASK-037: Aggregation Recompute DAG (1.5 days)

### Quick Steps:

1. **Create daily batch job to recompute aggregations**
2. **Compare with streaming aggregations**
3. **Alert on discrepancies**

---

## TASK-038: Data Quality Checks DAG (2 days)

### Quick Steps:

1. **Create hourly quality checks:**
   - Record counts within expected range
   - Null rate <1%
   - Schema validation
   - Duplicate detection
2. **Alert on violations**

---

## TASK-039: End-to-End QA Testing (2 days)

### Quick Steps:

1. **Test all features:**
   - Data ingestion
   - Model inference
   - Cassandra writes
   - Dashboard updates
   - Alerts
2. **Test failure recovery**
3. **Document results**

---

## TASK-040: User Acceptance Testing (UAT) (1 day)

### Quick Steps:

1. **Invite stakeholders to test dashboards**
2. **Conduct training session**
3. **Gather feedback**
4. **Create action items**

---

## TASK-041: Runbook Documentation (2 days)

### Quick Steps:

1. **Document operational procedures:**
   - How to restart producer
   - How to restart Spark job
   - How to rollback model
   - How to restore Cassandra backup
   - How to respond to alerts
2. **Include common errors and solutions**

---

## TASK-042: Deployment Guide (1 day)

### Quick Steps:

1. **Document production deployment:**
   - Infrastructure provisioning
   - CI/CD pipeline setup
   - Deployment checklist
   - Rollback procedure
2. **Create Terraform/CloudFormation templates (optional)**

---

# POST-LAUNCH TASKS

## TASK-043: Model Performance Monitoring Dashboard (1 day)

### Quick Steps:

1. **Add Grafana dashboard for model metrics:**
   - Precision, Recall, F1 over time
   - Inference latency
   - Prediction distribution
2. **Track 30-day trends**

---

## TASK-044: Cost Optimization Analysis (1 day)

### Quick Steps:

1. **Analyze cloud resource costs**
2. **Identify optimization opportunities:**
   - Auto-scaling
   - Reserved instances
   - TTL optimization
3. **Document recommendations**

---

## TASK-045: Export Functionality (1 day)

### Quick Steps:

1. **Add CSV export to Grafana dashboards**
2. **Create API endpoint for data export (optional)**
3. **Test with large datasets**

---

# SIMPLIFIED IMPLEMENTATION CHECKLIST

## Priority 1: Critical Path (Must Complete)

- [x] TASK-001 to TASK-008: Foundation ✓
- [x] TASK-009 to TASK-015: Data Flow ✓
- [ ] TASK-019: Train model
- [ ] TASK-020: Deploy model to Spark
- [ ] TASK-030: Load testing
- [ ] TASK-039: QA testing
- [ ] TASK-040: UAT

## Priority 2: Essential Features

- [ ] TASK-016-017: Additional dashboards
- [ ] TASK-022: Model training automation
- [ ] TASK-026: Alerting
- [ ] TASK-031: Documentation
- [ ] TASK-041: Runbooks

## Priority 3: Nice to Have

- [ ] TASK-021: Model registry
- [ ] TASK-033: Drift detection
- [ ] TASK-036: Advanced monitoring
- [ ] TASK-044: Cost optimization

---

# QUICK REFERENCE COMMANDS

## Start All Services

```bash
docker-compose up -d
```

## Train Model

```bash
python ml/models/train.py
```

## Run Spark Streaming

```bash
spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.0 \
  spark/streaming/main.py
```

## Check System Health

```bash
# Kafka
kafka-consumer-groups --bootstrap-server localhost:9092 --list

# Cassandra
docker exec cassandra nodetool status

# Spark
curl http://localhost:4040  # Spark UI

# Grafana
curl http://localhost:3000/api/health
```

## Common Issues & Solutions

### Issue: Kafka consumer lag growing

**Solution:** Increase Spark parallelism or batch interval

### Issue: Model inference slow

**Solution:** Increase batch size, use GPU, or optimize model

### Issue: Cassandra write timeout

**Solution:** Increase write timeout, check disk space, optimize schema

### Issue: Dashboard not updating

**Solution:** Check Cassandra connection, verify data freshness

---

# ESTIMATED TIMELINE

## Week 3: Model Integration

- Days 1-3: Train and evaluate model (TASK-019)
- Days 4-5: Deploy model to Spark (TASK-020)
- Days 6-7: Airflow DAGs and monitoring (TASK-022-029)

## Week 4: Optimization & QA

- Days 1-2: Load testing and optimization (TASK-030, 034-035)
- Days 3-4: Documentation (TASK-031, 041-042)
- Days 5-7: QA and UAT (TASK-039-040)

## Post-Launch

- Ongoing: Monitoring and optimization (TASK-043-045)

---

# SUCCESS CRITERIA

✓ **Functional:**

- System processes 1000+ posts/hour
- Model accuracy ≥80%
- Dashboards update within 60s
- Alerts trigger correctly

✓ **Performance:**

- End-to-end latency <60s (p95)
- Model inference <100ms per post
- Dashboard queries <5s
- 99.5% uptime

✓ **Quality:**

- Error rate <1%
- DLQ rate <5%
- Data quality checks passing
- Documentation complete

---

# NOTES

- Focus on getting the full pipeline working first, then optimize
- Use existing tools and libraries when possible
- Document decisions and trade-offs
- Test thoroughly before production
- Keep stakeholders informed of progress
- Prioritize based on business value
- Be prepared to iterate and improve

---

## Total Estimated Time: 3 weeks (with team parallelization)

**Breakdown:**

- Model work (ML Engineer): 8 days
- Infrastructure (Data Engineer): 6 days
- Dashboards & Monitoring (DataOps): 7 days
- QA & Documentation (All): 4 days
