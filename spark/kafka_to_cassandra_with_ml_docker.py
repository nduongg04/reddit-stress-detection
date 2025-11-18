#!/usr/bin/env python3
"""
Kafka to Cassandra Streaming Pipeline with ML Inference

Reads Reddit posts from Kafka, applies v4 stress detection model,
and writes results to Cassandra for real-time monitoring.
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, to_timestamp, date_format, current_timestamp,
    sha2, udf, struct, concat_ws, coalesce, lit, hour
)
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, LongType,
    BooleanType, FloatType
)
import os
import sys

print("="*60)
print("Kafka → ML → Cassandra Streaming Pipeline")
print("Real-Time Stress Detection with v4 Model")
print("="*60)

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Create Spark session with Cassandra connector
print("\n1. Creating Spark session with Cassandra support...")
spark = SparkSession.builder \
    .appName("KafkaMLCassandra") \
    .config("spark.cassandra.connection.host", "cassandra") \
    .config("spark.cassandra.connection.port", "9042") \
    .config("spark.sql.shuffle.partitions", "4") \
    .config("spark.sql.streaming.checkpointLocation", "/tmp/spark_checkpoints_ml") \
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
    .load()

print("✓ Connected to Kafka topic: reddit.posts.raw.v1")

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

# Load ML model and create UDF
print("\n5. Loading v4 stress detection model...")

# Import model after Spark is initialized
from model_inference import get_model_instance

# Initialize model (will be broadcast to workers)
try:
    model = get_model_instance()
    print(f"✓ Model loaded: {model.model_version}")
    print(f"   Device: {model.device}")
except Exception as e:
    print(f"✗ Failed to load model: {e}")
    print("   Please ensure ml/models/reddit_stress_v4 exists")
    sys.exit(1)


# Define prediction return schema
prediction_schema = StructType([
    StructField("stress_label", BooleanType(), True),
    StructField("stress_score", FloatType(), True),
    StructField("model_version", StringType(), True)
])


def predict_stress(text):
    """
    Predict stress for a single text.
    This function will be called by Spark workers.
    """
    if not text or text.strip() == "":
        return {"stress_label": False, "stress_score": 0.0, "model_version": "v4"}

    try:
        from model_inference import get_model_instance
        model = get_model_instance()
        result = model.predict_single(text)
        return result
    except Exception as e:
        print(f"Prediction error: {e}")
        return {"stress_label": False, "stress_score": 0.0, "model_version": "v4"}


# Register UDF
predict_udf = udf(predict_stress, prediction_schema)

# Apply ML predictions
print("\n6. Configuring ML inference...")
ml_df = transformed_df.withColumn("prediction", predict_udf(col("text")))

# Extract prediction fields
enriched_df = ml_df \
    .withColumn("stress_label", col("prediction.stress_label")) \
    .withColumn("stress_score", col("prediction.stress_score")) \
    .withColumn("model_version", col("prediction.model_version")) \
    .withColumn("processed_ts", current_timestamp()) \
    .drop("prediction")

print("✓ ML inference configured")


def write_to_cassandra(batch_df, batch_id):
    """
    Write each batch to Cassandra.
    Writes to both raw_posts_by_day and classified_posts_by_hour tables.
    """
    try:
        count = batch_df.count()
        if count == 0:
            print(f"\n[Batch {batch_id}] No records to process")
            return

        print(f"\n[Batch {batch_id}] Processing {count} records...")

        # Calculate stress statistics for this batch
        stress_count = batch_df.filter(col("stress_label") == True).count()
        stress_pct = (stress_count / count * 100) if count > 0 else 0

        print(f"[Batch {batch_id}] Stress detected: {stress_count}/{count} ({stress_pct:.1f}%)")

        # 1. Write to raw_posts_by_day (raw data storage)
        raw_df = batch_df.select(
            col("date_partition"),
            col("ingest_ts"),
            col("post_id"),
            col("author_hash"),
            col("body"),
            col("created_timestamp").alias("created_utc"),
            col("type").alias("kind"),
            col("permalink"),
            col("source"),
            col("subreddit"),
            col("title")
        )

        raw_df.write \
            .format("org.apache.spark.sql.cassandra") \
            .mode("append") \
            .options(table="raw_posts_by_day", keyspace="reddit_rt") \
            .save()

        print(f"[Batch {batch_id}] ✓ Written to raw_posts_by_day")

        # 2. Write to classified_posts_by_hour (ML predictions)
        classified_df = batch_df.select(
            col("subreddit"),
            col("hour_partition"),
            col("created_timestamp").alias("created_utc"),
            col("post_id"),
            col("title"),
            col("body"),
            col("author_hash"),
            col("permalink"),
            col("stress_label"),
            col("stress_score"),
            col("model_version"),
            col("processed_ts")
        )

        classified_df.write \
            .format("org.apache.spark.sql.cassandra") \
            .mode("append") \
            .options(table="classified_posts_by_hour", keyspace="reddit_rt") \
            .save()

        print(f"[Batch {batch_id}] ✓ Written to classified_posts_by_hour")

        # 3. Update hourly aggregates (simplified - proper aggregation should use Cassandra updates)
        # For now, we'll log the stats - actual aggregation should be done in a separate process
        print(f"[Batch {batch_id}] Aggregation stats:")
        batch_df.groupBy("subreddit", "hour_partition") \
            .agg({"stress_label": "count", "stress_score": "avg"}) \
            .show(truncate=False)

        print(f"[Batch {batch_id}] ✓ Batch processing complete")

    except Exception as e:
        print(f"[Batch {batch_id}] ✗ Error: {e}")
        import traceback
        traceback.print_exc()


# Start streaming query
print("\n7. Starting streaming pipeline...")
print("   Processing batches every 10 seconds")
print("   Press Ctrl+C to stop")
print("="*60)
print()

query = enriched_df \
    .writeStream \
    .foreachBatch(write_to_cassandra) \
    .outputMode("append") \
    .option("checkpointLocation", "/tmp/spark_checkpoints_ml") \
    .trigger(processingTime='10 seconds') \
    .start()

try:
    query.awaitTermination()
except KeyboardInterrupt:
    print("\n\n" + "="*60)
    print("Stopping stream...")
    query.stop()
    spark.stop()
    print("✓ Stream stopped successfully")
    print("="*60)
