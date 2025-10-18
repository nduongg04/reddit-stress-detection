# Complete Project Flow Explanation

**Real-Time Reddit Stress Detection System - End-to-End Data Flow**

---

## 📊 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         REAL-TIME DATA FLOW                                  │
└─────────────────────────────────────────────────────────────────────────────┘

     Reddit API                 Kafka               Spark Streaming           Cassandra              Grafana
         │                        │                        │                      │                      │
         │                        │                        │                      │                      │
    ┌────▼────┐              ┌───▼───┐              ┌─────▼──────┐         ┌────▼─────┐         ┌─────▼──────┐
    │  PRAW   │─────────────▶│ Topic │─────────────▶│   Spark    │────────▶│  Tables  │────────▶│ Dashboards │
    │Producer │  JSON Posts  │reddit │  Consume +   │  + Model   │ Write   │ + Aggs   │  Query  │  + Alerts  │
    └─────────┘              │.posts │  Process +   │ Inference  │ Results └──────────┘         └────────────┘
         │                   │.raw.v1│  Classify    └────────────┘
         │                   └───────┘              ┌─────────────┐
    ┌────▼────┐                  │                 │             │
    │  PSAW   │                  │                 │  DistilBERT │
    │Backfill │──────────────────┘                 │    Model    │
    └─────────┘              DLQ Topic             └─────────────┘
                            ┌───────┐                     │
                            │reddit │                     │
                            │.posts │              ┌──────▼──────┐
                            │.dlq.v1│              │  Training   │
                            └───────┘              │   Dataset   │
                                                   └─────────────┘
                                                          │
                                                   ┌──────▼──────┐
                   ┌─────────────────────────────▶│   Airflow   │
                   │      Orchestration            │    DAGs     │
                   │                               └─────────────┘
                   └───────────────────────────────────────────────┘
```

---

## 🔄 Complete Data Flow (Step by Step)

### **Phase 1: Data Collection & Ingestion**

#### Step 1: Reddit Data Collection

**Location**: `producers/reddit_producer/`

**How it works**:

1. **Real-time streaming (PRAW)**:
   ```python
   # producers/reddit_producer/reddit_stream.py
   # Connects to Reddit API via PRAW
   # Monitors specific subreddits: r/anxiety, r/depression, r/stress, etc.
   # Streams new posts as they're created
   ```

2. **Historical backfill (PSAW)**:
   ```python
   # producers/reddit_producer/backfill/praw_backfill.py
   # Fetches historical posts (last 3-6 months)
   # Runs nightly via Airflow DAG
   ```

**Data collected**:
```json
{
  "post_id": "abc123",
  "subreddit": "anxiety",
  "title": "I'm feeling so overwhelmed",
  "body": "I can't handle work stress anymore...",
  "author": "user123",
  "created_utc": 1700000000,
  "score": 42,
  "num_comments": 15
}
```

#### Step 2: Kafka Message Queue

**Location**: Kafka topics defined in `scripts/init-kafka-topics.sh`

**Topics**:
- `reddit.posts.raw.v1` - All incoming posts
- `reddit.posts.dlq.v1` - Failed/malformed messages

**Purpose**:
- Buffers incoming posts
- Decouples producer from consumer
- Provides fault tolerance (messages persist if Spark is down)
- Enables replay and reprocessing

---

### **Phase 2: Stream Processing & Classification**

#### Step 3: Spark Structured Streaming

**Location**: `spark/apps/streaming/`

**Main script**: `reddit_stream_with_inference.py`

**What happens**:

```python
# 1. Read from Kafka
df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "localhost:9092") \
    .option("subscribe", "reddit.posts.raw.v1") \
    .load()

# 2. Parse JSON and validate schema
posts = df.select(from_json(col("value"), schema).alias("data")) \
    .select("data.*")

# 3. Text Cleaning Pipeline
# Location: spark/apps/streaming/text_cleaning/
cleaned = posts.withColumn("cleaned_text", clean_text_udf(col("body")))

# Removes:
# - URLs (http://, https://)
# - Emojis (😊, 🔥)
# - Markdown formatting ([link], **bold**)
# - Special characters
# - Extra whitespace

# 4. Deduplication
# Uses watermark to remove duplicate posts within 24 hours
deduped = cleaned.dropDuplicates(["post_id"])

# 5. Model Inference (THE KEY STEP!)
# Location: spark/apps/streaming/models/inference_udf.py
predictions = deduped.withColumn(
    "prediction",
    predict_stress_udf(col("cleaned_text"))
)
# Returns: {stress_label: "STRESS", stress_score: 0.87}

# 6. Write to Cassandra
predictions.writeStream \
    .foreachBatch(write_to_cassandra) \
    .start()
```

#### Step 4: ML Model Inference

**Location**: `ml/models/reddit_stress_v1/`

**How inference works**:

```python
# Model loaded once at Spark startup
model = pipeline("text-classification", model="ml/models/reddit_stress_v1")

@pandas_udf("struct<stress_label:string, stress_score:double>")
def predict_stress(texts: pd.Series) -> pd.DataFrame:
    """
    Runs DistilBERT model on batch of texts

    Input: ["I'm so stressed", "Nice weather today"]
    Output: [
        {label: "STRESS", score: 0.92},
        {label: "NON_STRESS", score: 0.78}
    ]
    """
    results = model(texts.tolist(), batch_size=32)
    return pd.DataFrame({
        'stress_label': [r['label'] for r in results],
        'stress_score': [r['score'] for r in results]
    })
```

**Model details**:
- **Architecture**: DistilBERT (66M parameters)
- **Training**: Fine-tuned on labeled Reddit posts
- **Performance**: ~50ms per post, F1 score ≥0.83
- **Location**: `ml/models/reddit_stress_v1/pytorch_model.bin`

---

### **Phase 3: Storage & Aggregation**

#### Step 5: Cassandra Storage

**Location**: `cassandra/schema/`

**Schema design** (optimized for time-series queries):

**Table 1: `raw_posts_by_day`**
```sql
-- Stores raw ingested posts
-- Partition by day for time-range queries
PRIMARY KEY ((day_bucket), ingest_ts, post_id)
TTL: 14 days
```

**Table 2: `classified_posts_by_hour`**
```sql
-- Stores posts with stress predictions
-- Partition by subreddit + hour for dashboard queries
PRIMARY KEY ((subreddit, hour_bucket), created_utc, post_id)
TTL: 90 days

Columns:
- post_id, subreddit, text, cleaned_text
- stress_label (STRESS/NON_STRESS)
- stress_score (0.0-1.0)
- model_version
- created_utc, ingest_ts
```

**Table 3: `agg_subreddit_hour`**
```sql
-- Hourly aggregated metrics per subreddit
PRIMARY KEY ((subreddit, hour_bucket))
TTL: 180 days

Columns:
- total_posts_count
- stress_posts_count
- stress_percentage
- avg_stress_score
```

**Table 4: `agg_global_hour`**
```sql
-- Platform-wide hourly aggregates
PRIMARY KEY (hour_bucket)
TTL: 180 days

Columns:
- total_posts_count
- stress_posts_count
- stress_percentage
- avg_stress_score
- active_subreddits_count
```

**Why Cassandra?**
- Fast time-series writes (50ms p99)
- Efficient time-range queries for dashboards
- Automatic data expiration via TTL
- Horizontal scalability

---

### **Phase 4: Visualization & Monitoring**

#### Step 6: Grafana Dashboards

**Location**: `grafana/`

**Dashboard 1: Real-Time Stress Overview**

Queries Cassandra directly:
```sql
-- Global stress trend (last 24 hours)
SELECT hour_bucket, stress_percentage
FROM reddit_rt.agg_global_hour
WHERE hour_bucket >= now() - 24h
ORDER BY hour_bucket ASC

-- Top stressed subreddits
SELECT subreddit, stress_percentage
FROM reddit_rt.agg_subreddit_hour
WHERE hour_bucket >= now() - 1h
ORDER BY stress_percentage DESC
LIMIT 10
```

**Dashboard 2: Subreddit Analysis**
- Compare multiple subreddits over time
- Filter by time range (1h, 6h, 24h, 7d)

**Dashboard 3: System Health**
- Kafka consumer lag
- Spark processing time
- Model inference latency
- Pipeline uptime

**Refresh rate**: 30-60 seconds

---

### **Phase 5: Orchestration & Automation**

#### Step 7: Airflow DAGs

**Location**: `airflow/dags/`

**DAG 1: `producer_ctl`**
- Checks Reddit producer health every 5 minutes
- Auto-restarts on failure

**DAG 2: `psaw_backfill_daily`**
- Runs nightly at 2:00 AM
- Fetches historical posts
- Fills gaps in data

**DAG 3: `model_train_register`**
- Runs weekly on Sunday at 3:00 AM
- Extracts new labeled data
- Trains new model version
- Evaluates performance
- Registers if metrics improve

**DAG 4: `agg_recompute_daily`**
- Recomputes aggregations for data consistency
- Runs daily at 1:00 AM

**DAG 5: `data_quality_checks`**
- Validates record counts, null rates, schema
- Runs hourly
- Alerts on quality violations

---

## 📚 Model Training Flow (Separate from Real-Time Flow)

### Where is the Dataset?

**Location**: `ml/dataset/`

**Structure**:
```
ml/dataset/
├── raw/                      # Extracted from Cassandra
│   └── unlabeled_posts.csv   # 15,000 posts for labeling
├── labeled/                  # Human-labeled data
│   └── labeled_posts.csv     # Posts with STRESS/NON_STRESS labels
├── splits/                   # Train/val/test splits
│   ├── train.csv            # 70% (~10,500 posts)
│   ├── val.csv              # 15% (~2,250 posts)
│   └── test.csv             # 15% (~2,250 posts)
└── scripts/
    ├── extract_data.py      # Extract from Cassandra
    ├── label_ui.py          # Labeling interface
    └── prepare_dataset.py   # Create splits
```

### Training Pipeline

**Step 1: Data Collection (TASK-018)**
```bash
# Extract posts from Cassandra
python ml/dataset/scripts/extract_data.py --num-posts 15000

# Label posts via UI
streamlit run ml/dataset/scripts/label_ui.py

# Create train/val/test splits
python ml/dataset/scripts/prepare_dataset.py
```

**Step 2: Model Training (TASK-019)**
```bash
# Train DistilBERT model
cd ml/models
python train.py --epochs 3 --batch-size 16

# What happens:
# 1. Load labeled data from ml/dataset/splits/
# 2. Tokenize text with DistilBERT tokenizer
# 3. Fine-tune model for 3 epochs
# 4. Evaluate on test set
# 5. Save model to ml/models/reddit_stress_v1/
```

**Output**:
```
ml/models/reddit_stress_v1/
├── pytorch_model.bin         # Model weights (~250MB)
├── config.json              # Model configuration
├── tokenizer_config.json    # Tokenizer settings
├── vocab.txt                # Vocabulary
└── metadata.json            # Training metrics
```

**Step 3: Model Deployment (TASK-020)**
```python
# Replace dummy model in Spark
# Location: spark/apps/streaming/models/inference_udf.py

# OLD: Dummy random predictions
# NEW: Load trained model
model = pipeline("text-classification", model="ml/models/reddit_stress_v1")
```

---

## 🔄 How Real-Time Data is Processed

### Timeline of a Single Post

```
T=0s    Reddit user creates post "I'm so stressed about finals"
        ↓
T=1s    PRAW producer detects new post
        ↓
T=2s    Post sent to Kafka topic reddit.posts.raw.v1
        ↓
T=5s    Spark reads from Kafka (micro-batch every 5s)
        ↓
T=7s    Text cleaning: Remove URLs, emojis, extra spaces
        ↓
T=8s    Deduplication: Check if post_id already processed
        ↓
T=10s   Model inference: DistilBERT predicts STRESS (0.92)
        ↓
T=12s   Write to Cassandra:
        - classified_posts_by_hour (individual post)
        - agg_subreddit_hour (update hourly aggregate)
        ↓
T=15s   Grafana queries Cassandra (auto-refresh every 30s)
        ↓
T=30s   Dashboard updates with new stress percentage
```

**Total latency**: ~30 seconds from Reddit to Dashboard ✅ (Target: <60s)

---

## 🎯 Key Integration Points

### 1. **Dataset → Model Training**
```
Cassandra (raw posts) → Extract → Label → Splits → Train → Model
```

### 2. **Model → Spark Inference**
```
Trained model (ml/models/) → Loaded in Spark → Applied via PandasUDF
```

### 3. **Kafka → Spark → Cassandra**
```
Kafka (buffered messages) → Spark (process + classify) → Cassandra (store)
```

### 4. **Cassandra → Grafana**
```
Cassandra (aggregated data) → Grafana queries → Dashboard displays
```

### 5. **Airflow → Everything**
```
Airflow DAGs control:
- Producer health checks
- Backfill jobs
- Model retraining
- Data quality checks
```

---

## 📝 Summary of Components

### Data Sources
- **Reddit API (PRAW)**: Real-time posts (`producers/reddit_producer/`)
- **Pushshift (PSAW)**: Historical backfill (`producers/reddit_producer/backfill/`)

### Message Queue
- **Apache Kafka**: Buffer and decouple components (Docker: port 9092)

### Processing
- **Spark Streaming**: Clean, dedupe, classify (`spark/apps/streaming/`)
- **ML Model**: DistilBERT stress classifier (`ml/models/reddit_stress_v1/`)

### Storage
- **Cassandra**: Time-series optimized storage (`cassandra/schema/`)
  - Raw posts (14 day TTL)
  - Classified posts (90 day TTL)
  - Aggregates (180 day TTL)

### Visualization
- **Grafana**: Real-time dashboards (Docker: port 3000)
  - Queries Cassandra directly
  - Auto-refresh every 30-60s

### Orchestration
- **Apache Airflow**: DAG scheduling (Docker: port 8082)
  - Producer control
  - Backfill jobs
  - Model training
  - Quality checks

### Model Training (Offline)
- **Dataset**: `ml/dataset/` (labeled Reddit posts)
- **Training**: `ml/models/train.py` (DistilBERT fine-tuning)
- **Evaluation**: `ml/models/evaluate.py` (metrics + plots)

---

## 🚀 Complete Project Status

### ✅ Phase 1: Foundation (COMPLETE)
- Kafka cluster ✓
- Mock producer ✓
- Spark streaming skeleton ✓
- Cassandra schema ✓
- Grafana dashboards ✓
- Airflow environment ✓

### ✅ Phase 2: Real Data Flow (COMPLETE)
- Reddit producer (PRAW) ✓
- Historical backfill (PSAW) ✓
- Error handling ✓
- Spark-Cassandra integration ✓
- Text cleaning pipeline ✓
- End-to-end testing ✓
- Grafana live data ✓

### 🔄 Phase 3: Model Integration (IN PROGRESS - TASK-019)
- ✅ Dataset collection infrastructure
- ✅ Model training infrastructure
- ⏳ **Train production model** (requires labeled data or use sample)
- ⏳ Deploy model to Spark (TASK-020)
- ⏳ Model versioning (TASK-021)
- ⏳ Automated training DAG (TASK-022)

### ⏳ Phase 4: Optimization & QA (PENDING)
- Load testing
- Performance tuning
- Documentation
- QA/UAT

---

## 🎓 Key Concepts

### Why Two Separate Flows?

**1. Real-Time Flow**: Reddit → Kafka → Spark → Cassandra → Grafana
- Purpose: Process live posts
- Frequency: Continuous (24/7)
- Latency: ~30 seconds

**2. Training Flow**: Cassandra → Dataset → Train → Model
- Purpose: Improve model accuracy
- Frequency: Weekly (via Airflow)
- Latency: 1-2 hours

### How They Connect

The **trained model** (from training flow) is **deployed** to Spark (real-time flow) to classify posts.

```
Training Flow creates model → Model deployed to Spark → Spark uses model for real-time inference
```

---

## 📖 Further Reading

- **Architecture**: `docs/prd.md`
- **Task breakdown**: `tasks/detailed/`
- **Setup guides**:
  - Kafka: `docs/kafka-setup.md`
  - Cassandra: `docs/cassandra-setup.md`
  - Grafana: `docs/grafana-setup.md`
  - Airflow: `docs/airflow-setup.md`
- **Model training**: `ml/models/TRAINING_GUIDE.md`
- **Dataset prep**: `ml/dataset/README.md`

---

**Questions? Check the documentation or ask for clarification on any component!**
