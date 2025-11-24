#!/usr/bin/env python3
"""
Kafka to Cassandra Streaming Pipeline

Reads Reddit posts from Kafka and writes to Cassandra.
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, to_timestamp, date_format
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, LongType

print("="*60)
print("Kafka → Cassandra Streaming Pipeline")
print("="*60)

# Create Spark session with Cassandra connector
print("\n1. Creating Spark session with Cassandra support...")
spark = SparkSession.builder \
    .appName("KafkaToCassandra") \
    .config("spark.cassandra.connection.host", "cassandra") \
    .config("spark.cassandra.connection.port", "9042") \
    .config("spark.sql.shuffle.partitions", "4") \
    .config("spark.sql.streaming.checkpointLocation", "/tmp/spark_checkpoints_cassandra") \
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
    StructField("ingestion_timestamp", StringType(), True),
    StructField("search_category", StringType(), True)  # Added for Vietnamese collection
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

# Transform for Cassandra (match table schema)
print("\n4. Transforming data for Cassandra...")
from pyspark.sql.functions import current_timestamp, sha2

transformed_df = parsed_df \
    .withColumn("created_timestamp", to_timestamp(col("created_utc"))) \
    .withColumn("date_partition", date_format(col("created_timestamp"), "yyyy-MM-dd")) \
    .withColumn("ingest_ts", current_timestamp()) \
    .withColumn("author_hash", sha2(col("author"), 256)) \
    .select(
        col("date_partition"),
        col("ingest_ts"),
        col("post_id"),
        col("author_hash"),
        col("body"),
        col("created_timestamp").alias("created_utc"),  # Keep as timestamp
        col("type").alias("kind"),
        col("permalink"),
        col("source"),
        col("subreddit"),
        col("title"),
        col("search_category")  # Added for Vietnamese collection
    )

print("✓ Data transformation configured")

# Write to Cassandra
print("\n5. Writing to Cassandra (reddit_rt.raw_posts_by_day)...")
print("   Press Ctrl+C to stop")
print("="*60)
print()

def write_to_cassandra(batch_df, batch_id):
    """Write each batch to Cassandra."""
    try:
        print(f"\n[Batch {batch_id}] Processing {batch_df.count()} records...")

        batch_df.write \
            .format("org.apache.spark.sql.cassandra") \
            .mode("append") \
            .options(
                table="raw_posts_by_day",
                keyspace="reddit_rt",
                **{"spark.cassandra.connection.host": "cassandra", "spark.cassandra.connection.port": "9042"}
            ) \
            .save()

        print(f"[Batch {batch_id}] ✓ Written to Cassandra")

    except Exception as e:
        print(f"[Batch {batch_id}] ✗ Error: {e}")

# Start streaming query
query = transformed_df \
    .writeStream \
    .foreachBatch(write_to_cassandra) \
    .outputMode("append") \
    .option("checkpointLocation", "/tmp/spark_checkpoints_cassandra") \
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
