#!/usr/bin/env python3
"""
Kafka to Cassandra Streaming Pipeline with ABSA ML Inference

Reads Reddit posts from Kafka, applies Vietnamese PhoBERT ABSA model,
and writes results to Cassandra for real-time monitoring.
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, to_timestamp, date_format, current_timestamp,
    sha2, udf, struct, concat_ws, coalesce, lit, hour
)
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, LongType,
    BooleanType, ArrayType, MapType, DoubleType
)
import os
import sys

print("="*60)
print("Kafka → ABSA ML → Cassandra Streaming Pipeline")
print("Real-Time Vietnamese Mental Health Detection")
print("="*60)

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Create Spark session with Cassandra connector
print("\n1. Creating Spark session with Cassandra support...")
spark = SparkSession.builder \
    .appName("KafkaABSACassandra") \
    .config("spark.cassandra.connection.host", "cassandra") \
    .config("spark.cassandra.connection.port", "9042") \
    .config("spark.sql.shuffle.partitions", "4") \
    .config("spark.jars.packages", "com.datastax.spark:spark-cassandra-connector_2.12:3.5.0,org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")
print("✓ Spark session created")

# Define schema for Reddit posts
schema = StructType([
    StructField("post_id", StringType(), True),
    StructField("title", StringType(), True),
    StructField("body", StringType(), True),
    StructField("author", StringType(), True),
    StructField("subreddit", StringType(), True),
    StructField("created_utc", LongType(), True),
    StructField("score", IntegerType(), True),
    StructField("num_comments", IntegerType(), True),
    StructField("url", StringType(), True),
    StructField("permalink", StringType(), True),
    StructField("type", StringType(), True),
    StructField("source", StringType(), True),
    StructField("ingestion_timestamp", StringType(), True)
])

# Read from Kafka
print("\n2. Connecting to Kafka...")
kafka_df = spark \
    .readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:9092") \
    .option("subscribe", "reddit.posts.raw.v1") \
    .option("startingOffsets", "earliest") \
    .option("failOnDataLoss", "false") \
    .option("maxOffsetsPerTrigger", "100") \
    .load()

print("✓ Connected to Kafka topic: reddit.posts.raw.v1")
print("  Max 100 messages per batch")

# Parse JSON from Kafka
print("\n3. Parsing JSON data...")
parsed_df = kafka_df \
    .selectExpr("CAST(value AS STRING) as json_string") \
    .select(from_json(col("json_string"), schema).alias("data")) \
    .select("data.*")

# Transform data
print("\n4. Transforming data...")
transformed_df = parsed_df \
    .withColumn("created_timestamp", to_timestamp(col("created_utc"))) \
    .withColumn("date_partition", date_format(col("created_timestamp"), "yyyy-MM-dd")) \
    .withColumn("hour_partition", date_format(col("created_timestamp"), "yyyy-MM-dd-HH")) \
    .withColumn("ingest_ts", current_timestamp()) \
    .withColumn("author_hash", sha2(col("author"), 256)) \
    .withColumn(
        "text",
        concat_ws(" ", coalesce(col("title"), lit("")), coalesce(col("body"), lit("")))
    )

print("✓ Data transformation configured")

# Configure ABSA model paths (to be loaded on workers)
print("\n5. Configuring Vietnamese ABSA PhoBERT model...")
MODEL_PATH = "/opt/ml/models/vietnamese_absa_sentiment_phobert_v1"
ASPECTS_PATH = "/opt/ml/lda/absa_mental_health_aspects.json"
print(f"  Model path: {MODEL_PATH}")
print(f"  Aspects path: {ASPECTS_PATH}")

# Create UDF for batch prediction (loads model per partition)
@udf(StructType([
    StructField("aspect_sentiments", MapType(StringType(), IntegerType()), True),
    StructField("stress_score", DoubleType(), True),
    StructField("stress_label", BooleanType(), True),
    StructField("model_version", StringType(), True)
]))
def predict_absa_udf(text):
    """
    Predict ABSA aspects for text (model loaded lazily per worker)

    Returns dict with predictions
    """
    # Lazy import to avoid serialization issues
    import sys
    sys.path.insert(0, '/opt/spark-apps')

    # Load model lazily (singleton pattern per worker)
    global _model_cache
    if '_model_cache' not in globals():
        from model_inference_absa import ABSAStressDetectionModel
        _model_cache = ABSAStressDetectionModel(
            default_model=MODEL_PATH,
            aspects_file=ASPECTS_PATH,
            auto_reload=False
        )

    # Handle empty text
    if not text or text.strip() == "":
        return {
            'aspect_sentiments': {},
            'stress_score': 0.0,
            'stress_label': False,
            'model_version': 'vietnamese_absa_phobert_v1'
        }

    # Predict
    try:
        result = _model_cache.predict_single(text)
        return result
    except Exception as e:
        return {
            'aspect_sentiments': {},
            'stress_score': 0.0,
            'stress_label': False,
            'model_version': f'error: {str(e)[:50]}'
        }

print("✓ ABSA model UDF configured")

print("\n6. Applying ABSA model to streaming data...")

# Apply model predictions
ml_df = transformed_df \
    .withColumn("prediction", predict_absa_udf(col("text"))) \
    .select(
        col("post_id"),
        col("subreddit"),
        col("hour_partition"),
        col("created_timestamp").alias("created_utc"),
        col("title"),
        col("body"),
        col("author_hash"),
        col("permalink"),
        col("prediction.aspect_sentiments").alias("aspect_sentiments"),
        col("prediction.model_version").alias("model_version"),
        col("type").alias("kind"),
        col("ingest_ts").alias("processed_ts")
    )

print("✓ Model inference pipeline configured")

# Write to Cassandra
print("\n7. Writing to Cassandra (reddit_rt.classified_posts_by_hour)...")
print("   Press Ctrl+C to stop")
print("="*60)

def write_to_cassandra(df, epoch_id):
    """Write batch to Cassandra with ABSA results"""

    # Cache to avoid recomputation
    df.cache()

    count = df.count()
    print(f"\n[Batch {epoch_id}] Processing {count} records with ABSA model...")

    if count == 0:
        print(f"[Batch {epoch_id}] No records to process")
        return

    # Show sample predictions
    print(f"[Batch {epoch_id}] Sample predictions:")
    df.select("subreddit", "title", "aspect_sentiments") \
        .show(5, truncate=80)

    # Write to Cassandra
    try:
        df.write \
            .format("org.apache.spark.sql.cassandra") \
            .mode("append") \
            .options(
                table="classified_posts_by_hour",
                keyspace="reddit_rt",
                **{"spark.cassandra.connection.host": "cassandra", "spark.cassandra.connection.port": "9042"}
            ) \
            .save()

        print(f"[Batch {epoch_id}] ✓ Written to Cassandra")

    except Exception as e:
        print(f"[Batch {epoch_id}] ✗ Cassandra write error: {e}")

    df.unpersist()

# Start streaming query
query = ml_df \
    .writeStream \
    .foreachBatch(write_to_cassandra) \
    .option("checkpointLocation", "/tmp/spark_checkpoints_absa") \
    .trigger(processingTime="10 seconds") \
    .start()

print("\n✓ Streaming query started successfully!")
print("Waiting for data from Kafka...")
print("=" * 60)

query.awaitTermination()
