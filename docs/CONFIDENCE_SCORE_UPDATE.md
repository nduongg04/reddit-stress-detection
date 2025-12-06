# Cập Nhật Confidence Score cho Active Learning

## Tóm tắt thay đổi

Đã cập nhật toàn bộ pipeline để hỗ trợ **confidence score** trong việc chọn lọc dữ liệu cho Active Learning. Model ABSA (vietnamese_absa_sentiment_phobert_v1) giờ đây sẽ tính toán và lưu độ tin cậy của mỗi prediction, giúp DAG retrain có thể chọn những bài viết mà model "không chắc chắn" để re-label.

## Chi tiết các thay đổi

### 1. **Cassandra Schema** (`cassandra/schema/03_classified_posts_by_hour.cql`)

**Thêm trường mới:**
```sql
confidence_scores map<text, double>  -- Aspect → Confidence score (aspect_name → 0.0-1.0)
```

**Mục đích:** 
- Lưu confidence score cho từng aspect (10 aspects)
- Score nằm trong khoảng 0.0 - 1.0
- Map aspect_name (e.g., "công_việc") → confidence score

**Ví dụ:**
```json
{
  "công_việc": 0.87,
  "giấc_ngủ_thuốc": 0.45,  // Low confidence
  "tình_yêu": 0.92
}
```

---

### 2. **Spark Model Inference** (`spark/model_inference_absa.py`)

**Cập nhật `predict_batch` method:**

```python
# Build aspect → sentiment map với confidence scores
confidence_scores = {}
for i, sentiment in enumerate(sentiment_labels):
    aspect_name = self.aspects[i]['aspect_name']
    # Get confidence (probability of predicted class)
    confidence = float(probs[i, sentiment_labels[i] + 1])
    confidence_scores[aspect_name] = confidence
```

**Thay đổi return value:**
```python
{
    'aspect_sentiments': {'công_việc': -1, 'tình_yêu': 1},
    'confidence_scores': {'công_việc': 0.87, 'tình_yêu': 0.92, ...},  # NEW
    'stress_score': 0.7,
    'stress_label': True,
    'model_version': 'v1'
}
```

---

### 3. **Spark Streaming** (`spark/kafka_to_cassandra_with_absa.py`)

**Cập nhật UDF schema:**
```python
@udf(StructType([
    StructField("aspect_sentiments", MapType(StringType(), IntegerType()), True),
    StructField("confidence_scores", MapType(StringType(), DoubleType()), True),  # NEW
    StructField("stress_score", DoubleType(), True),
    StructField("stress_label", BooleanType(), True),
    StructField("model_version", StringType(), True)
]))
```

**Cập nhật DataFrame select:**
```python
ml_df = transformed_df \
    .withColumn("prediction", predict_absa_udf(col("text"))) \
    .select(
        ...
        col("prediction.confidence_scores").alias("confidence_scores"),  # NEW
        ...
    )
```

**Kết quả:** Spark giờ sẽ ghi `confidence_scores` vào Cassandra cùng với `aspect_sentiments`

---

### 4. **Airflow DAG** (`airflow/dags/vietnamese_absa_retrain.py`)

#### 4.1. Task 1: `fetch_recent_posts`

**Trước:**
- Query bảng có `stress_score`, `stress_label` (model cũ)
- Fetch tất cả posts trong 24h

**Sau:**
- Query bảng ABSA với `confidence_scores`
- **Chỉ fetch low-confidence posts (min confidence < 0.5)**
- Tự động filter trong Python:

```python
confidence_values = list(row.confidence_scores.values())
min_confidence = min(confidence_values)

# Only include LOW confidence posts (< 0.5)
if min_confidence < 0.5:
    posts.append({...})
```

**Lợi ích:**
- Giảm số lượng posts cần validate (chỉ những posts model không chắc chắn)
- Tiết kiệm RAM và compute
- Active Learning hiệu quả hơn

#### 4.2. Task 2: `run_inference`

**Trước:**
- Dùng model cũ (10 labels)
- Sigmoid activation

**Sau:**
- **Dùng đúng model ABSA (30 labels = 10 aspects × 3 sentiments)**
- Softmax activation per aspect
- Reshape logits: `[30] → [10, 3]`
- Giới hạn **top 100 lowest-confidence** để tránh tràn RAM

```python
# Load correct ABSA model
model_dir = '/opt/ml/models/vietnamese_absa_sentiment_phobert_v1'
model = PhoBERTMultiLabelClassifier('vinai/phobert-base-v2', num_labels=30)

# Reshape and softmax
logits_reshaped = logits.squeeze().view(10, 3)
probs = torch.softmax(logits_reshaped, dim=1).numpy()  # [10, 3]
```

---

### 5. **Docker Compose** (`docker-compose.yml`)

**Thêm volumes cho Airflow containers:**

```yaml
airflow-webserver:
  volumes:
    - ./ml:/opt/airflow/ml          # NEW: Access to models and training scripts
    - ./utils:/opt/airflow/utils    # NEW: Access to ollama_validator.py

airflow-scheduler:
  volumes:
    - ./ml:/opt/airflow/ml          # NEW
    - ./utils:/opt/airflow/utils    # NEW
```

**Lợi ích:**
- DAG có thể import `train_absa_phobert.py`
- DAG có thể import `ollama_validator.py`
- Không cần rebuild image khi sửa code

---

## Flow hoạt động mới

### **Giai đoạn 1: Thu thập Low-Confidence Data**

```
Spark Stream → Cassandra
  ↓
  - Post có aspect_sentiments: {'công_việc': -1}
  - Post có confidence_scores: {'công_việc': 0.42}  ← LOW!
```

### **Giai đoạn 2: Active Learning (Daily 2 AM)**

```
1. fetch_recent_posts:
   - Query Cassandra (last 24h)
   - Filter: min(confidence_scores) < 0.5
   - Limit: Top 100 lowest-confidence posts
   
   Output: 100 posts model "không chắc chắn"

2. run_inference:
   - Re-run ABSA model (30 labels)
   - Get fresh probabilities [10 aspects, 3 sentiments each]
   
3. select_uncertain_predictions:
   - Calculate entropy-based uncertainty
   - Rank by uncertainty score
   
4. validate_with_ollama:
   - Send 100 posts → Ollama (llama3.1:8b)
   - Get corrected labels
   - Save to validated_TIMESTAMP.csv

5. retrain_model:
   - Combine: vozforums_absa_labeled.csv + validated_TIMESTAMP.csv
   - Train new model: vietnamese_absa_phobert_TIMESTAMP
   - Save to /opt/ml/models/

6. update_model_registry:
   - Update registry.json
   - Mark new model as active

7. Spark Hot-Reload:
   - Detect registry change
   - Load new model
   - Continue streaming with new model
```

---

## Ví dụ minh họa

### **Cassandra Record**

```json
{
  "post_id": "abc123",
  "subreddit": "vozforums",
  "title": "Mình stress công việc quá",
  "aspect_sentiments": {
    "công_việc": -1,
    "giấc_ngủ_thuốc": -1
  },
  "confidence_scores": {
    "công_việc": 0.42,        // LOW confidence!
    "giấc_ngủ_thuốc": 0.38,   // LOW confidence!
    "tình_yêu": 0.95,
    "gia_đình": 0.88,
    ...
  },
  "model_version": "v1"
}
```

**Min confidence = 0.38 < 0.5** → Được chọn để re-label

---

### **Active Learning Output**

```csv
post_id,text,sentiment_0_công_việc,sentiment_1_giấc_ngủ_thuốc,...
active_learning_20251204_001,Mình stress công việc quá,-1,-1,...
```

**Validated by Ollama → Corrected labels → Retrain**

---

## Lợi ích

1. **Hiệu quả hơn:** Chỉ re-label những posts model không chắc chắn (< 0.5)
2. **Tiết kiệm tài nguyên:** Giới hạn 100 posts/ngày → Không tràn RAM
3. **Chính xác hơn:** Sử dụng đúng model ABSA (30 labels) thay vì model cũ (10 labels)
4. **Tự động hoàn toàn:** Không cần can thiệp thủ công, Ollama tự validate

---

## Các bước triển khai

### 1. **Cập nhật Cassandra schema**

```bash
docker exec -it reddit-cassandra cqlsh -f /schema/03_classified_posts_by_hour.cql
```

hoặc thêm trường thủ công:

```sql
ALTER TABLE reddit_rt.classified_posts_by_hour 
ADD confidence_scores map<text, double>;
```

### 2. **Restart Spark containers**

```bash
docker-compose restart spark-master spark-worker
```

Spark sẽ load code mới và bắt đầu ghi `confidence_scores` vào Cassandra.

### 3. **Restart Airflow containers**

```bash
docker-compose restart airflow-webserver airflow-scheduler
```

DAG mới sẽ được load với logic query `confidence_scores`.

### 4. **Kích hoạt DAG**

- Truy cập Airflow UI: http://localhost:8082 (airflow/airflow)
- Enable DAG: `vietnamese_absa_daily_retrain`
- Chờ lịch tự chạy (2 AM UTC) hoặc trigger thủ công

---

## Monitoring

### **Check confidence scores trong Cassandra**

```sql
USE reddit_rt;

SELECT post_id, confidence_scores
FROM classified_posts_by_hour
WHERE subreddit = 'vozforums'
  AND hour_partition = '2025-12-04-14'
LIMIT 10;
```

### **Check low-confidence posts count**

```python
# In Airflow logs
print(f"Fetched {len(posts)} LOW-CONFIDENCE posts (confidence < 0.5)")
print(f"Average min confidence: {avg_confidence:.3f}")
```

### **Check retrain metrics**

```bash
cat /opt/airflow/logs/retraining_metrics.jsonl
```

---

## Troubleshooting

### **Issue: confidence_scores = NULL trong Cassandra**

**Nguyên nhân:** Schema chưa được apply hoặc Spark chưa restart

**Giải pháp:**
```bash
# Apply schema
docker exec -it reddit-cassandra cqlsh -f /schema/03_classified_posts_by_hour.cql

# Restart Spark
docker-compose restart spark-master spark-worker
```

---

### **Issue: DAG không fetch được posts**

**Nguyên nhân:** Tất cả posts đều có confidence > 0.5 (model quá tự tin)

**Giải pháp:**
- Kiểm tra lại threshold (có thể tăng lên 0.6 hoặc 0.7)
- Hoặc trigger DAG vào thời điểm có nhiều posts hơn

---

### **Issue: Import error trong DAG**

**Nguyên nhân:** Volumes chưa được mount

**Giải pháp:**
```bash
# Check volumes
docker inspect reddit-airflow-webserver | grep -A 10 Mounts

# Restart with new volumes
docker-compose down
docker-compose up -d
```

---

## Kết luận

Hệ thống giờ đây có khả năng:
- ✅ Tính toán confidence score cho mỗi aspect prediction
- ✅ Lưu confidence scores vào Cassandra
- ✅ Tự động chọn low-confidence posts (< 0.5) để re-label
- ✅ Giới hạn 100 posts/ngày để tránh tràn RAM
- ✅ Sử dụng đúng model ABSA (vietnamese_absa_sentiment_phobert_v1)
- ✅ Active Learning hoàn toàn tự động với Ollama

**Flow retrain giờ đây hiệu quả và chính xác hơn rất nhiều!**
