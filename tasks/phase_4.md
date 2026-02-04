# Phase 4: Streaming Pipeline

## Goal
Real-time stress classification using Spark Structured Streaming with PhoBERT inference.

## Architecture
```
Kafka (voz.posts.raw.v1) → Spark Streaming → PhoBERT Inference → Cassandra (voz_classified_posts)
```

## Tasks

### 4.1 Spark Setup
- [ ] Dockerfile with PySpark + PyTorch
- [ ] Kafka connector dependencies
- [ ] Cassandra connector dependencies
- [ ] ONNX Runtime for inference

### 4.2 Streaming Consumer
- [ ] Read from Kafka topic
- [ ] Parse JSON messages
- [ ] Watermarking for late data

### 4.3 Model Inference
- [ ] Load ONNX model in Spark UDF
- [ ] Batch inference (micro-batch)
- [ ] PhoBERT tokenization

### 4.4 Cassandra Writer
- [ ] Write to voz_classified_posts
- [ ] Update counter tables
- [ ] Handle write failures

### 4.5 Fault Tolerance
- [ ] Checkpoint directory
- [ ] Exactly-once semantics
- [ ] Backpressure handling

### 4.6 Monitoring
- [ ] Spark UI metrics
- [ ] Processing rate tracking
- [ ] Lag monitoring

## Spark Job Structure

```python
# spark/kafka_to_cassandra_with_ml.py
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *

spark = SparkSession.builder \
    .appName("VOZ-Stress-Classifier") \
    .config("spark.cassandra.connection.host", "cassandra") \
    .config("spark.sql.streaming.checkpointLocation", "/tmp/checkpoint") \
    .getOrCreate()

# Read from Kafka
df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:9092") \
    .option("subscribe", "voz.posts.raw.v1") \
    .option("startingOffsets", "latest") \
    .load()

# Parse JSON
schema = StructType([
    StructField("post_id", StringType()),
    StructField("text", StringType()),
    StructField("url", StringType()),
    StructField("source", StringType()),
    StructField("timestamp", StringType()),
    StructField("crawled_at", StringType())
])

parsed = df.select(
    from_json(col("value").cast("string"), schema).alias("data")
).select("data.*")

# Apply ML inference (UDF)
@udf(returnType=ArrayType(FloatType()))
def classify_stress(text):
    # ONNX inference
    return model_inference(text)

classified = parsed.withColumn("aspect_probs", classify_stress(col("text")))

# Write to Cassandra
query = classified.writeStream \
    .foreachBatch(write_to_cassandra) \
    .outputMode("append") \
    .option("checkpointLocation", "/tmp/checkpoint/voz") \
    .start()
```

## Files Structure

```
spark/
  kafka_to_cassandra_with_ml.py  # Main streaming job
  model_inference.py              # ONNX inference wrapper
  cassandra_writer.py             # Cassandra batch writer
  requirements.txt                # Spark dependencies
  Dockerfile                      # Spark + ML image
ml/
  exports/
    phobert_stress.onnx           # Exported model
    tokenizer/                    # PhoBERT tokenizer files
cassandra/
  schema/
    05_voz_classified_posts.cql   # [EXISTS] Output table
scripts/
  start_spark_streaming.sh        # Launch script
  monitor_streaming.sh            # Health check
```

## Cassandra Output Schema

```cql
-- Already exists: cassandra/schema/05_voz_classified_posts.cql
CREATE TABLE IF NOT EXISTS voz_classified_posts (
    hour_bucket text,
    classified_at timestamp,
    post_id text,
    text text,
    url text,
    source text,
    original_timestamp timestamp,
    aspects list<int>,
    aspect_probs list<float>,
    confidence float,
    stress_label boolean,
    model_version text,
    processing_time_ms int,
    PRIMARY KEY ((hour_bucket), classified_at, post_id)
) WITH CLUSTERING ORDER BY (classified_at DESC, post_id ASC);

-- Counter tables for aggregation
CREATE TABLE IF NOT EXISTS voz_aspect_hourly (
    hour_bucket text,
    aspect_id int,
    count counter,
    PRIMARY KEY ((hour_bucket), aspect_id)
);
```

## Docker Configuration

```dockerfile
# Dockerfile.spark
FROM bitnami/spark:3.5

USER root

# Install Python dependencies
RUN pip install \
    pyspark==3.5.0 \
    onnxruntime==1.16.0 \
    transformers==4.36.0 \
    cassandra-driver==3.28.0

# Copy model and code
COPY ml/exports/phobert_stress.onnx /opt/models/
COPY spark/ /opt/spark-apps/

USER 1001
```

## Spark Submit Command

```bash
spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,\
com.datastax.spark:spark-cassandra-connector_2.12:3.4.1 \
  --conf spark.cassandra.connection.host=cassandra \
  --conf spark.sql.streaming.checkpointLocation=/tmp/checkpoint \
  --conf spark.streaming.backpressure.enabled=true \
  --conf spark.streaming.kafka.maxRatePerPartition=100 \
  /opt/spark-apps/kafka_to_cassandra_with_ml.py
```

## Inference UDF

```python
# spark/model_inference.py
import onnxruntime as ort
from transformers import AutoTokenizer

class StressClassifier:
    def __init__(self, model_path, tokenizer_path):
        self.session = ort.InferenceSession(model_path)
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
        self.threshold = 0.5

    def predict(self, text):
        # Tokenize
        inputs = self.tokenizer(
            text,
            max_length=256,
            padding="max_length",
            truncation=True,
            return_tensors="np"
        )

        # Inference
        outputs = self.session.run(None, {
            "input_ids": inputs["input_ids"],
            "attention_mask": inputs["attention_mask"]
        })

        # Sigmoid + threshold
        probs = 1 / (1 + np.exp(-outputs[0][0]))
        aspects = [i for i, p in enumerate(probs) if p > self.threshold]

        return {
            "aspects": aspects,
            "aspect_probs": probs.tolist(),
            "confidence": float(max(probs)) if aspects else 0.0,
            "stress_label": len(aspects) > 0
        }
```

## Backpressure & Rate Limiting

```python
# Spark config for backpressure
spark.conf.set("spark.streaming.backpressure.enabled", "true")
spark.conf.set("spark.streaming.backpressure.initialRate", "100")
spark.conf.set("spark.streaming.kafka.maxRatePerPartition", "100")

# Micro-batch trigger
query = df.writeStream \
    .trigger(processingTime="10 seconds") \  # Process every 10s
    .foreachBatch(process_batch) \
    .start()
```

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| Kafka unavailable | Retry with exponential backoff |
| Cassandra timeout | Batch retry, dead-letter queue |
| Model OOM | Limit batch size, use streaming batches |
| Late data | Watermark 1 hour, drop older |
| Duplicate posts | Cassandra upsert (post_id in PK) |
| Empty text | Skip with warning log |
| Very long text | Truncate to 256 tokens |
| ONNX load failure | Fail-fast, alert |
| Checkpoint corruption | Delete and restart from latest |
| Schema mismatch | Version check on startup |
| Spark worker failure | Auto-restart, checkpoint recovery |

## Monitoring Queries

```sql
-- Recent classifications
SELECT * FROM voz_classified_posts
WHERE hour_bucket = '2024-01-15-14'
LIMIT 10;

-- Aspect counts this hour
SELECT aspect_id, count
FROM voz_aspect_hourly
WHERE hour_bucket = '2024-01-15-14';

-- Processing lag (compare crawled_at vs classified_at)
SELECT post_id,
       classified_at - original_timestamp as lag_seconds
FROM voz_classified_posts
WHERE hour_bucket = '2024-01-15-14'
LIMIT 100;
```

## Health Checks

```bash
# Check Spark streaming status
curl http://spark-master:4040/api/v1/applications

# Check Kafka consumer lag
docker exec reddit-kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group spark-voz-classifier

# Check Cassandra write rate
docker exec reddit-cassandra nodetool tablestats reddit_rt.voz_classified_posts
```

## Validation Criteria

- [ ] Spark job starts without errors
- [ ] Reads from Kafka topic successfully
- [ ] ONNX model loads correctly
- [ ] Inference produces valid predictions
- [ ] Writes to Cassandra without failures
- [ ] Processing lag < 30 seconds
- [ ] No message loss (check consumer lag)
- [ ] Survives Kafka broker restart
- [ ] Recovers from checkpoint after Spark restart
- [ ] Counter tables update correctly

## Performance Targets

| Metric | Target |
|--------|--------|
| Throughput | > 100 posts/minute |
| Latency (end-to-end) | < 30 seconds |
| Kafka consumer lag | < 100 messages |
| Inference time | < 100ms per post |
| Cassandra write time | < 50ms per batch |
| Memory usage | < 4GB per executor |
