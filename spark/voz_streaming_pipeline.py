#!/usr/bin/env python3
"""
VOZ Streaming Pipeline with LLM Inference

Reads VOZ posts from Kafka, applies LLM-based stress detection and demographic extraction,
and writes results to Cassandra for real-time dashboard visualization.

Uses llama3.1:8b via Ollama for combined stress + demographics analysis.
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, to_timestamp, date_format, current_timestamp,
    udf, lit, array, coalesce
)
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, LongType,
    BooleanType, FloatType, ArrayType
)
import os
import sys
import json

print("=" * 70)
print("VOZ Streaming Pipeline with LLM Inference")
print("Real-Time Stress Detection + Demographics (llama3.1:8b)")
print("=" * 70)

# Configuration
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "voz.posts.raw.v1")
KAFKA_SERVERS = os.getenv("KAFKA_SERVERS", "kafka:9092")
CASSANDRA_HOST = os.getenv("CASSANDRA_HOST", "cassandra")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")  # Ollama runs on host
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
BATCH_INTERVAL = os.getenv("BATCH_INTERVAL", "30 seconds")  # LLM is slow, use larger batches

print(f"\nConfiguration:")
print(f"  Kafka Topic: {KAFKA_TOPIC}")
print(f"  Kafka Servers: {KAFKA_SERVERS}")
print(f"  Cassandra Host: {CASSANDRA_HOST}")
print(f"  Ollama URL: {OLLAMA_URL}")
print(f"  LLM Model: {LLM_MODEL}")
print(f"  Batch Interval: {BATCH_INTERVAL}")

# Create Spark session
print("\n1. Creating Spark session...")
spark = SparkSession.builder \
    .appName("VOZStreamingLLM") \
    .config("spark.cassandra.connection.host", CASSANDRA_HOST) \
    .config("spark.cassandra.connection.port", "9042") \
    .config("spark.sql.shuffle.partitions", "2") \
    .config("spark.sql.streaming.checkpointLocation", "/tmp/spark_checkpoints_voz") \
    .config("spark.jars.packages", "com.datastax.spark:spark-cassandra-connector_2.12:3.5.0,org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")
print("  Spark session created")

# Schema for VOZ posts from Kafka
voz_schema = StructType([
    StructField("post_id", StringType(), True),
    StructField("text", StringType(), True),
    StructField("url", StringType(), True),
    StructField("source", StringType(), True),
    StructField("timestamp", StringType(), True),  # ISO format
    StructField("crawled_at", StringType(), True),
])

# Read from Kafka
print("\n2. Connecting to Kafka...")
kafka_df = spark \
    .readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_SERVERS) \
    .option("subscribe", KAFKA_TOPIC) \
    .option("startingOffsets", "earliest") \
    .option("failOnDataLoss", "false") \
    .load()

print(f"  Connected to Kafka topic: {KAFKA_TOPIC}")

# Parse JSON
print("\n3. Parsing JSON data...")
parsed_df = kafka_df \
    .selectExpr("CAST(value AS STRING) as json_string") \
    .select(from_json(col("json_string"), voz_schema).alias("data")) \
    .select("data.*")

# Transform data
print("\n4. Transforming data...")
transformed_df = parsed_df \
    .withColumn("original_timestamp", to_timestamp(col("timestamp"))) \
    .withColumn("hour_bucket", date_format(current_timestamp(), "yyyy-MM-dd-HH")) \
    .withColumn("classified_at", current_timestamp()) \
    .filter(col("text").isNotNull() & (col("text") != ""))

print("  Data transformation configured")

# LLM Inference Schema
llm_result_schema = StructType([
    StructField("aspects", ArrayType(IntegerType()), True),
    StructField("aspect_probs", ArrayType(FloatType()), True),
    StructField("confidence", FloatType(), True),
    StructField("stress_label", BooleanType(), True),
    StructField("gender", StringType(), True),
    StructField("age_group", StringType(), True),
    StructField("occupation", StringType(), True),
    StructField("relationship", StringType(), True),
    StructField("reasoning", StringType(), True),
    StructField("processing_time_ms", IntegerType(), True),
])


def create_llm_predictor():
    """Create LLM predictor function with connection caching"""
    import requests
    import json
    import time

    # Load prompt template
    prompt_template = """Phân tích bài đăng tiếng Việt và trả về JSON:
- aspects: mảng số [0-9] cho các khía cạnh stress
- gender: "nam"/"nữ"/"unknown"
- age_group: "teen"/"young_adult"/"adult"/"middle_aged"/"senior"/"unknown"
- occupation: "student"/"office_worker"/"it_engineer"/"healthcare"/"teacher"/"blue_collar"/"freelance"/"unemployed"/"unknown"
- relationship: "single"/"dating"/"married"/"divorced"/"unknown"
- reasoning: giải thích ngắn

Khía cạnh: 0=Công việc, 1=Tài chính, 2=Học tập, 3=Gia đình, 4=Sức khỏe, 5=Tình cảm, 6=Hiện sinh, 7=Xã hội, 8=Sự kiện, 9=Hình ảnh bản thân

Bài đăng:
"""

    def predict_with_llm(text):
        """Predict stress and demographics using LLM"""
        default_result = {
            "aspects": [],
            "aspect_probs": [0.0] * 10,
            "confidence": 0.0,
            "stress_label": False,
            "gender": "unknown",
            "age_group": "unknown",
            "occupation": "unknown",
            "relationship": "unknown",
            "reasoning": "LLM inference failed",
            "processing_time_ms": 0
        }

        if not text or not text.strip():
            return default_result

        start_time = time.time()

        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": LLM_MODEL,
                    "prompt": prompt_template + text[:1000],  # Limit text length
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 500,
                        "num_ctx": 4096,
                    }
                },
                timeout=60
            )

            if response.status_code != 200:
                default_result["reasoning"] = f"API error: {response.status_code}"
                return default_result

            data = response.json()
            response_text = data.get("response", "")

            # Extract JSON
            start = response_text.find("{")
            end = response_text.rfind("}") + 1

            if start >= 0 and end > start:
                result = json.loads(response_text[start:end])

                # Validate aspects
                aspects = result.get("aspects", [])
                if isinstance(aspects, list):
                    aspects = [a for a in aspects if isinstance(a, int) and 0 <= a <= 9]
                else:
                    aspects = []

                # Build aspect probs
                aspect_probs = [1.0 if i in aspects else 0.0 for i in range(10)]

                processing_time = int((time.time() - start_time) * 1000)

                return {
                    "aspects": aspects,
                    "aspect_probs": aspect_probs,
                    "confidence": len(aspects) / 10.0 if aspects else 0.0,
                    "stress_label": len(aspects) > 0,
                    "gender": result.get("gender", "unknown"),
                    "age_group": result.get("age_group", "unknown"),
                    "occupation": result.get("occupation", "unknown"),
                    "relationship": result.get("relationship", "unknown"),
                    "reasoning": result.get("reasoning", "")[:500],
                    "processing_time_ms": processing_time
                }

        except Exception as e:
            default_result["reasoning"] = f"Error: {str(e)[:100]}"

        default_result["processing_time_ms"] = int((time.time() - start_time) * 1000)
        return default_result

    return predict_with_llm


# Register UDF
print("\n5. Registering LLM inference UDF...")
predict_udf = udf(create_llm_predictor(), llm_result_schema)
print("  LLM UDF registered")


def write_to_cassandra(batch_df, batch_id):
    """Write each batch to Cassandra with LLM inference"""
    try:
        count = batch_df.count()
        if count == 0:
            print(f"\n[Batch {batch_id}] No records to process")
            return

        print(f"\n[Batch {batch_id}] Processing {count} records with LLM...")

        # Apply LLM inference
        enriched_df = batch_df.withColumn("llm_result", predict_udf(col("text")))

        # Extract LLM result fields
        final_df = enriched_df \
            .withColumn("aspects", col("llm_result.aspects")) \
            .withColumn("aspect_probs", col("llm_result.aspect_probs")) \
            .withColumn("confidence", col("llm_result.confidence")) \
            .withColumn("stress_label", col("llm_result.stress_label")) \
            .withColumn("gender", col("llm_result.gender")) \
            .withColumn("age_group", col("llm_result.age_group")) \
            .withColumn("occupation", col("llm_result.occupation")) \
            .withColumn("relationship", col("llm_result.relationship")) \
            .withColumn("reasoning", col("llm_result.reasoning")) \
            .withColumn("processing_time_ms", col("llm_result.processing_time_ms")) \
            .withColumn("model_version", lit(f"{LLM_MODEL}_demo")) \
            .drop("llm_result")

        # Calculate stats
        stress_count = final_df.filter(col("stress_label") == True).count()
        stress_pct = (stress_count / count * 100) if count > 0 else 0

        print(f"[Batch {batch_id}] Stress detected: {stress_count}/{count} ({stress_pct:.1f}%)")

        # Select columns for Cassandra
        cassandra_df = final_df.select(
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
            col("reasoning"),
            col("gender"),
            col("age_group"),
            col("occupation"),
            col("relationship"),
            col("model_version"),
            col("processing_time_ms"),
        )

        # Write to Cassandra
        cassandra_df.write \
            .format("org.apache.spark.sql.cassandra") \
            .mode("append") \
            .options(
                table="voz_classified_posts",
                keyspace="reddit_rt",
            ) \
            .save()

        print(f"[Batch {batch_id}] Written to voz_classified_posts")

        # Update counter tables (aspect hourly counts)
        # Note: Counter updates should be done via separate Cassandra queries
        # For demo, we'll just log the distribution
        print(f"[Batch {batch_id}] Demographics distribution:")
        final_df.groupBy("gender").count().show(truncate=False)

        print(f"[Batch {batch_id}] Processing complete")

    except Exception as e:
        print(f"[Batch {batch_id}] Error: {e}")
        import traceback
        traceback.print_exc()


# Start streaming
print("\n6. Starting streaming pipeline...")
print(f"   Processing batches every {BATCH_INTERVAL}")
print("   Press Ctrl+C to stop")
print("=" * 70)
print()

query = transformed_df \
    .writeStream \
    .foreachBatch(write_to_cassandra) \
    .outputMode("append") \
    .option("checkpointLocation", "/tmp/spark_checkpoints_voz") \
    .trigger(processingTime=BATCH_INTERVAL) \
    .start()

try:
    query.awaitTermination()
except KeyboardInterrupt:
    print("\n\n" + "=" * 70)
    print("Stopping stream...")
    query.stop()
    spark.stop()
    print("Stream stopped successfully")
    print("=" * 70)
