#!/usr/bin/env python3
"""
Kafka to Cassandra Streaming Pipeline with PhoBERT ML + Qwen Demographics

Reads VOZ posts from Kafka, applies:
1. PhoBERT stress detection model (ONNX) for stress aspects
2. Qwen 8B LLM for demographics extraction (age, occupation, relationship)
Writes results to Cassandra for real-time monitoring.
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, to_timestamp, date_format, current_timestamp,
    udf, lit, coalesce
)
from pyspark.sql.types import (
    StructType, StructField, StringType, ArrayType,
    BooleanType, FloatType, IntegerType
)
import os
import sys
import time
import json
import requests

print("=" * 60)
print("VOZ Kafka → PhoBERT ML + Qwen LLM → Cassandra Pipeline")
print("Real-Time Vietnamese Stress Detection + Demographics")
print("=" * 60)

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "voz.posts.raw.v1")
CASSANDRA_HOST = os.getenv("CASSANDRA_HOST", "cassandra")
CASSANDRA_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "reddit_rt")
MODEL_PATH = os.getenv("MODEL_PATH", "/opt/models/phobert_stress.onnx")
TOKENIZER_PATH = os.getenv("TOKENIZER_PATH", "/opt/models/tokenizer")
CHECKPOINT_DIR = os.getenv("CHECKPOINT_DIR", "/tmp/spark_checkpoints_voz")
MODEL_VERSION = os.getenv("MODEL_VERSION", "phobert_v1")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "host.docker.internal:11434")

# Create Spark session
print("\n1. Creating Spark session with Cassandra support...")
spark = SparkSession.builder \
    .appName("VOZ-Stress-Classifier") \
    .config("spark.cassandra.connection.host", CASSANDRA_HOST) \
    .config("spark.cassandra.connection.port", "9042") \
    .config("spark.sql.shuffle.partitions", "4") \
    .config("spark.sql.streaming.checkpointLocation", CHECKPOINT_DIR) \
    .config("spark.streaming.backpressure.enabled", "true") \
    .config("spark.streaming.kafka.maxRatePerPartition", "100") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")
print("✓ Spark session created")

# VOZ post schema
voz_schema = StructType([
    StructField("post_id", StringType(), True),
    StructField("text", StringType(), True),
    StructField("url", StringType(), True),
    StructField("source", StringType(), True),
    StructField("timestamp", StringType(), True),
    StructField("crawled_at", StringType(), True)
])

# Prediction output schema (PhoBERT stress + Qwen demographics)
prediction_schema = StructType([
    StructField("aspects", ArrayType(IntegerType()), True),
    StructField("aspect_probs", ArrayType(FloatType()), True),
    StructField("confidence", FloatType(), True),
    StructField("stress_label", BooleanType(), True),
    StructField("age_group", StringType(), True),
    StructField("occupation", StringType(), True),
    StructField("relationship", StringType(), True)
])

# Read from Kafka
print(f"\n2. Connecting to Kafka ({KAFKA_BOOTSTRAP_SERVERS})...")
kafka_df = spark \
    .readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
    .option("subscribe", KAFKA_TOPIC) \
    .option("startingOffsets", "latest") \
    .option("failOnDataLoss", "false") \
    .load()

print(f"✓ Connected to Kafka topic: {KAFKA_TOPIC}")

# Parse JSON
print("\n3. Parsing JSON data...")
parsed_df = kafka_df \
    .selectExpr("CAST(value AS STRING) as json_string", "timestamp as kafka_ts") \
    .select(
        from_json(col("json_string"), voz_schema).alias("data"),
        col("kafka_ts")
    ) \
    .select("data.*", "kafka_ts")

# Transform data
print("\n4. Transforming data...")
transformed_df = parsed_df \
    .withColumn("hour_bucket", date_format(current_timestamp(), "yyyy-MM-dd-HH")) \
    .withColumn("original_timestamp", to_timestamp(col("timestamp"))) \
    .filter(col("text").isNotNull() & (col("text") != ""))

print("✓ Data transformation configured")

# Create ML prediction UDF
print(f"\n5. Loading PhoBERT stress model from {MODEL_PATH}...")


def extract_demographics_with_llm(text):
    """Extract demographics using Llama 3.1 8B via Ollama."""
    try:
        prompt = f"""Analyze this Vietnamese social media post and extract demographics. Return ONLY valid JSON.

Post: "{text[:500]}"

Extract:
- age_group: one of ["13-17", "18-25", "26-35", "36-45", "46-60", "60+", "unknown"]
- occupation: one of ["student", "office_worker", "freelancer", "business_owner", "unemployed", "retired", "unknown"]
- relationship: one of ["single", "dating", "married", "divorced", "unknown"]

Rules:
- If no clear indicator, use "unknown"
- Look for hints like: "em" (young), "tôi đi làm" (worker), "vợ/chồng" (married), "sinh viên" (student)
- Do NOT guess, only infer from clear evidence

Return JSON only:
{{"age_group": "...", "occupation": "...", "relationship": "..."}}"""

        response = requests.post(
            f"http://{OLLAMA_HOST}/api/generate",
            json={
                "model": "llama3.1:8b",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1}
            },
            timeout=60
        )

        if response.status_code == 200:
            result = response.json().get("response", "")
            # Extract JSON from response - handle <think> tags
            try:
                # Find JSON by looking for last { and matching }
                # Find the JSON object
                start = result.rfind("{")
                end = result.rfind("}") + 1
                if start >= 0 and end > start:
                    json_str = result[start:end]
                    data = json.loads(json_str)
                    extracted = {
                        "age_group": data.get("age_group", "unknown"),
                        "occupation": data.get("occupation", "unknown"),
                        "relationship": data.get("relationship", "unknown")
                    }
                    print(f"[Llama] Extracted: {extracted}")
                    return extracted
            except json.JSONDecodeError as e:
                print(f"[Llama] JSON parse error: {e}")
            except Exception as e:
                print(f"[Llama] Error: {e}")

        print(f"[Llama] No valid response, status: {response.status_code}")
        return {"age_group": "unknown", "occupation": "unknown", "relationship": "unknown"}

    except Exception as e:
        print(f"[Llama] Error: {e}")
        return {"age_group": "unknown", "occupation": "unknown", "relationship": "unknown"}


def create_predict_udf():
    """Create prediction UDF with PhoBERT + parallel Qwen demographics."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def predict_stress(text):
        """Predict stress aspects + demographics in parallel."""
        if not text or not text.strip():
            return {
                "aspects": [], "aspect_probs": [0.0] * 9, "confidence": 0.0,
                "stress_label": False, "age_group": "unknown",
                "occupation": "unknown", "relationship": "unknown"
            }

        try:
            import numpy as np

            # Lazy load PhoBERT model
            if not hasattr(predict_stress, "_session"):
                import onnxruntime as ort
                from transformers import AutoTokenizer
                predict_stress._session = ort.InferenceSession(MODEL_PATH, providers=['CPUExecutionProvider'])
                predict_stress._tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_PATH)
                print("✓ PhoBERT model loaded")

            # Run PhoBERT and Qwen in parallel
            with ThreadPoolExecutor(max_workers=2) as executor:
                # Submit LLM first (slower)
                llm_future = executor.submit(extract_demographics_with_llm, text)

                # Run PhoBERT inference
                inputs = predict_stress._tokenizer(text, max_length=256, padding="max_length", truncation=True, return_tensors="np")
                outputs = predict_stress._session.run(None, {
                    "input_ids": inputs["input_ids"].astype(np.int64),
                    "attention_mask": inputs["attention_mask"].astype(np.int64)
                })
                logits = outputs[0][0]
                probs = 1 / (1 + np.exp(-logits))
                aspects = [int(i) for i, p in enumerate(probs) if p > 0.5]
                aspect_probs = [float(p) for p in probs]

                # Get LLM result (with timeout)
                try:
                    demographics = llm_future.result(timeout=30)
                except:
                    demographics = {"age_group": "unknown", "occupation": "unknown", "relationship": "unknown"}

            return {
                "aspects": aspects, "aspect_probs": aspect_probs,
                "confidence": float(max(probs)) if aspects else 0.0,
                "stress_label": len(aspects) > 0,
                "age_group": demographics.get("age_group", "unknown"),
                "occupation": demographics.get("occupation", "unknown"),
                "relationship": demographics.get("relationship", "unknown")
            }

        except Exception as e:
            print(f"Prediction error: {e}")
            return {
                "aspects": [], "aspect_probs": [0.0] * 9, "confidence": 0.0,
                "stress_label": False, "age_group": "unknown",
                "occupation": "unknown", "relationship": "unknown"
            }

    return udf(predict_stress, prediction_schema)


predict_udf = create_predict_udf()
print("✓ ML prediction UDF configured")

# Apply ML predictions
print("\n6. Configuring ML inference pipeline...")
ml_df = transformed_df.withColumn("prediction", predict_udf(col("text")))

# Extract prediction fields (stress aspects + demographics)
enriched_df = ml_df \
    .withColumn("aspects", col("prediction.aspects")) \
    .withColumn("aspect_probs", col("prediction.aspect_probs")) \
    .withColumn("confidence", col("prediction.confidence")) \
    .withColumn("stress_label", col("prediction.stress_label")) \
    .withColumn("age_group", col("prediction.age_group")) \
    .withColumn("occupation", col("prediction.occupation")) \
    .withColumn("relationship", col("prediction.relationship")) \
    .withColumn("classified_at", current_timestamp()) \
    .withColumn("model_version", lit(MODEL_VERSION)) \
    .drop("prediction")

print("✓ ML inference configured")


def write_to_cassandra(batch_df, batch_id):
    """Write batch to Cassandra tables."""
    try:
        count = batch_df.count()
        if count == 0:
            print(f"\n[Batch {batch_id}] No records to process")
            return

        start_time = time.time()
        print(f"\n[Batch {batch_id}] Processing {count} records...")

        # Calculate stress statistics
        stress_count = batch_df.filter(col("stress_label") == True).count()
        stress_pct = (stress_count / count * 100) if count > 0 else 0
        print(f"[Batch {batch_id}] Stress detected: {stress_count}/{count} ({stress_pct:.1f}%)")

        # Write to voz_classified_posts (with demographics)
        classified_df = batch_df.select(
            col("hour_bucket"),
            col("classified_at"),
            col("post_id"),
            col("text"),
            col("url"),
            col("source"),
            col("original_timestamp"),
            col("aspects"),
            col("aspect_probs"),
            col("confidence"),
            col("stress_label"),
            col("age_group"),
            col("occupation"),
            col("relationship"),
            col("model_version")
        )

        classified_df.write \
            .format("org.apache.spark.sql.cassandra") \
            .mode("append") \
            .options(
                table="voz_classified_posts",
                keyspace=CASSANDRA_KEYSPACE
            ) \
            .save()

        processing_time = int((time.time() - start_time) * 1000)
        print(f"[Batch {batch_id}] ✓ Written to voz_classified_posts in {processing_time}ms")

        # Log aspect distribution for this batch
        if stress_count > 0:
            print(f"[Batch {batch_id}] Aspect breakdown:")
            aspect_names = ["work", "self", "health", "study", "love", "family", "money", "events", "exist"]
            from pyspark.sql.functions import explode
            aspects_exploded = batch_df.filter(col("stress_label") == True) \
                .select(explode(col("aspects")).alias("aspect_id")) \
                .groupBy("aspect_id").count() \
                .collect()
            for row in aspects_exploded:
                idx = row["aspect_id"]
                name = aspect_names[idx] if idx < len(aspect_names) else f"aspect_{idx}"
                print(f"           {name}: {row['count']}")

    except Exception as e:
        print(f"[Batch {batch_id}] ✗ Error: {e}")
        import traceback
        traceback.print_exc()


# Start streaming
print("\n7. Starting streaming pipeline...")
print(f"   Kafka: {KAFKA_BOOTSTRAP_SERVERS} / {KAFKA_TOPIC}")
print(f"   Cassandra: {CASSANDRA_HOST} / {CASSANDRA_KEYSPACE}")
print("   Processing batches every 10 seconds")
print("   Press Ctrl+C to stop")
print("=" * 60 + "\n")

query = enriched_df \
    .writeStream \
    .foreachBatch(write_to_cassandra) \
    .outputMode("append") \
    .option("checkpointLocation", f"{CHECKPOINT_DIR}/voz-classifier") \
    .trigger(processingTime='10 seconds') \
    .start()

try:
    query.awaitTermination()
except KeyboardInterrupt:
    print("\n\n" + "=" * 60)
    print("Stopping stream...")
    query.stop()
    spark.stop()
    print("✓ Stream stopped successfully")
    print("=" * 60)
