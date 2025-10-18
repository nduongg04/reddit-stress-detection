# TASK-012: Spark-Cassandra Integration

**Owner:** ML/Spark Engineer
**Priority:** Critical
**Dependencies:** TASK-004 (Spark Structured Streaming Skeleton), TASK-006 (Cassandra Schema Design)
**Estimate:** 1.5 days

---

## Overview

Integrate Apache Spark Structured Streaming with Apache Cassandra to enable real-time data writes. Configure the Spark-Cassandra connector, implement write operations to multiple Cassandra tables, optimize write performance, and implement error handling for database operations.

---

## Subtasks

### Subtask 012.1: Spark-Cassandra Connector Setup

**Estimate:** 30 minutes

**Description:**
- Add Cassandra connector dependencies to Spark project
- Configure connector settings
- Verify connector installation

**Acceptance Criteria:**
- Connector library added to project
- Dependencies resolved correctly
- Connector version compatible with Spark and Cassandra versions

**Files to Create/Update:**
- `spark/streaming_job/build.sbt` (for Scala) or `requirements.txt` (for PySpark)

**For Scala (build.sbt):**
```scala
name := "reddit-streaming"
version := "1.0"
scalaVersion := "2.12.15"

libraryDependencies ++= Seq(
  "org.apache.spark" %% "spark-core" % "3.3.0",
  "org.apache.spark" %% "spark-sql" % "3.3.0",
  "org.apache.spark" %% "spark-streaming" % "3.3.0",
  "org.apache.spark" %% "spark-sql-kafka-0-10" % "3.3.0",
  "com.datastax.spark" %% "spark-cassandra-connector" % "3.2.0",
  "org.apache.kafka" % "kafka-clients" % "3.3.1"
)
```

**For PySpark (requirements.txt):**
```txt
pyspark==3.3.0
kafka-python==2.0.2
cassandra-driver==3.25.0
```

**Commands:**
```bash
cd spark/streaming_job

# For Scala
sbt clean compile

# For PySpark
pip install -r requirements.txt
```

---

### Subtask 012.2: Cassandra Connection Configuration

**Estimate:** 45 minutes

**Description:**
- Create Cassandra connection configuration
- Set up connection pooling
- Configure authentication and SSL (if needed)

**Acceptance Criteria:**
- Connection parameters defined
- Connection pool configured
- Test connection successful

**Files to Create:**
- `spark/streaming_job/config/cassandra_config.yaml`

**Configuration:**
```yaml
cassandra:
  # Contact points
  contact_points:
    - "localhost"  # Dev environment
    # - "cassandra1.prod.com"  # Production
    # - "cassandra2.prod.com"
    # - "cassandra3.prod.com"

  # Port
  port: 9042

  # Keyspace
  keyspace: "reddit_rt"

  # Authentication (optional)
  auth:
    enabled: false
    username: "cassandra_user"
    password: "cassandra_password"

  # Connection settings
  connection:
    connections_per_host: 2
    keep_alive: true
    timeout_ms: 30000
    retry_policy: "DowngradingConsistencyRetryPolicy"

  # Write settings
  write:
    consistency_level: "LOCAL_QUORUM"
    batch_size_bytes: 16384
    batch_buffer_size: 1000
    parallelism: 4
    throughput_mb_per_sec: 512

  # SSL settings (production)
  ssl:
    enabled: false
    keystore_path: "/path/to/keystore"
    keystore_password: "password"
    truststore_path: "/path/to/truststore"
    truststore_password: "password"
```

---

### Subtask 012.3: Spark Configuration for Cassandra

**Estimate:** 30 minutes

**Description:**
- Configure Spark session with Cassandra connector
- Set Cassandra-specific Spark configurations
- Optimize for streaming workload

**Acceptance Criteria:**
- Spark session configured correctly
- Cassandra parameters passed to Spark
- Configuration tested

**Files to Create:**
- `spark/streaming_job/src/spark_cassandra_config.py` (PySpark) or `.scala`

**PySpark Implementation:**
```python
from pyspark.sql import SparkSession
import yaml

def create_spark_session_with_cassandra(app_name="RedditStreamProcessor"):
    """
    Create Spark session configured for Cassandra
    """

    # Load Cassandra config
    with open('config/cassandra_config.yaml', 'r') as f:
        cassandra_config = yaml.safe_load(f)['cassandra']

    # Build Spark session
    spark = SparkSession.builder \
        .appName(app_name) \
        .config("spark.cassandra.connection.host", ','.join(cassandra_config['contact_points'])) \
        .config("spark.cassandra.connection.port", cassandra_config['port']) \
        .config("spark.cassandra.auth.username", cassandra_config['auth']['username']) \
        .config("spark.cassandra.auth.password", cassandra_config['auth']['password']) \
        .config("spark.cassandra.connection.keep_alive_ms", "60000") \
        .config("spark.cassandra.output.consistency.level", cassandra_config['write']['consistency_level']) \
        .config("spark.cassandra.output.batch.size.bytes", cassandra_config['write']['batch_size_bytes']) \
        .config("spark.cassandra.output.concurrent.writes", cassandra_config['write']['parallelism']) \
        .config("spark.cassandra.output.throughput_mb_per_sec", cassandra_config['write']['throughput_mb_per_sec']) \
        .config("spark.sql.streaming.checkpointLocation", "/tmp/spark_checkpoints") \
        .getOrCreate()

    # Set log level
    spark.sparkContext.setLogLevel("WARN")

    return spark

# Test connection
if __name__ == "__main__":
    spark = create_spark_session_with_cassandra()
    print("Spark session created successfully")
    spark.stop()
```

---

### Subtask 012.4: Schema Mapping Implementation

**Estimate:** 1 hour

**Description:**
- Map Kafka JSON schema to Cassandra table schemas
- Create transformation functions
- Handle data type conversions

**Acceptance Criteria:**
- Schema mappings defined
- Data types converted correctly
- All required fields mapped

**Files to Create:**
- `spark/streaming_job/src/schema_mapping.py`

**Implementation:**
```python
from pyspark.sql.types import *
from pyspark.sql.functions import *

# Define Kafka message schema
kafka_schema = StructType([
    StructField("post_id", StringType(), False),
    StructField("title", StringType(), True),
    StructField("body", StringType(), True),
    StructField("author", StringType(), True),
    StructField("subreddit", StringType(), False),
    StructField("created_utc", LongType(), False),
    StructField("score", IntegerType(), True),
    StructField("num_comments", IntegerType(), True),
    StructField("url", StringType(), True),
    StructField("type", StringType(), True),
    StructField("source", StringType(), True),
    StructField("ingestion_timestamp", StringType(), False),
    StructField("correlation_id", StringType(), True)
])

def transform_for_raw_posts_table(df):
    """
    Transform DataFrame for raw_posts_by_day table
    Partition key: post_date (derived from created_utc)
    Clustering key: post_id
    """
    return df.select(
        # Convert Unix timestamp to date for partition key
        to_date(from_unixtime(col("created_utc"))).alias("post_date"),
        col("post_id"),
        col("title"),
        col("body"),
        col("author"),
        col("subreddit"),
        from_unixtime(col("created_utc")).cast("timestamp").alias("created_timestamp"),
        col("score"),
        col("num_comments"),
        col("url"),
        col("type"),
        col("source"),
        current_timestamp().alias("ingestion_timestamp")
    )

def transform_for_classified_posts_table(df):
    """
    Transform DataFrame for classified_posts_by_hour table
    (After model inference)
    Partition key: hour_bucket
    Clustering key: post_id
    """
    return df.select(
        # Hour bucket for partitioning: YYYY-MM-DD HH:00:00
        date_format(from_unixtime(col("created_utc")), "yyyy-MM-dd HH:00:00").alias("hour_bucket"),
        col("post_id"),
        col("subreddit"),
        col("body"),
        col("stress_label").cast(IntegerType()),
        col("stress_score").cast(DoubleType()),
        col("model_version"),
        from_unixtime(col("created_utc")).cast("timestamp").alias("created_timestamp")
    )

def transform_for_subreddit_hourly_agg(df):
    """
    Transform DataFrame for agg_subreddit_hour table
    Aggregates: count, stress count, avg score
    """
    hourly_agg = df.groupBy(
        date_format(from_unixtime(col("created_utc")), "yyyy-MM-dd HH:00:00").alias("hour_bucket"),
        col("subreddit")
    ).agg(
        count("*").alias("total_posts"),
        sum(when(col("stress_label") == 1, 1).otherwise(0)).alias("stress_posts"),
        avg("stress_score").alias("avg_stress_score"),
        current_timestamp().alias("updated_at")
    )

    return hourly_agg.withColumn(
        "stress_percentage",
        (col("stress_posts") / col("total_posts") * 100).cast(DoubleType())
    )

def transform_for_global_hourly_agg(df):
    """
    Transform DataFrame for agg_global_hour table
    Global aggregates across all subreddits
    """
    global_agg = df.groupBy(
        date_format(from_unixtime(col("created_utc")), "yyyy-MM-dd HH:00:00").alias("hour_bucket")
    ).agg(
        count("*").alias("total_posts"),
        sum(when(col("stress_label") == 1, 1).otherwise(0)).alias("stress_posts"),
        avg("stress_score").alias("avg_stress_score"),
        count(col("subreddit").distinct()).alias("subreddits_active"),
        current_timestamp().alias("updated_at")
    )

    return global_agg.withColumn(
        "stress_percentage",
        (col("stress_posts") / col("total_posts") * 100).cast(DoubleType())
    )
```

---

### Subtask 012.5: Write to raw_posts_by_day Table

**Estimate:** 1 hour

**Description:**
- Implement write logic for raw posts table
- Handle write errors
- Test write performance

**Acceptance Criteria:**
- Data written successfully to raw_posts_by_day
- Partition keys correct
- Write latency acceptable (<50ms p99)

**Files to Create:**
- `spark/streaming_job/src/cassandra_writers.py`

**Implementation:**
```python
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
import logging

logger = logging.getLogger(__name__)

class CassandraWriter:
    """
    Handle writes to Cassandra tables
    """

    def __init__(self, config):
        self.config = config['cassandra']
        self.keyspace = self.config['keyspace']

    def write_raw_posts(self, df, epoch_id):
        """
        Write raw posts to raw_posts_by_day table
        Uses foreachBatch for efficient writes
        """
        try:
            # Transform data
            transformed_df = transform_for_raw_posts_table(df)

            # Write to Cassandra
            transformed_df.write \
                .format("org.apache.spark.sql.cassandra") \
                .options(table="raw_posts_by_day", keyspace=self.keyspace) \
                .mode("append") \
                .save()

            logger.info(f"Batch {epoch_id}: Written {transformed_df.count()} posts to raw_posts_by_day")

        except Exception as e:
            logger.error(f"Error writing batch {epoch_id} to raw_posts_by_day: {e}")
            raise

    def write_classified_posts(self, df, epoch_id):
        """
        Write classified posts to classified_posts_by_hour table
        """
        try:
            # Transform data
            transformed_df = transform_for_classified_posts_table(df)

            # Write to Cassandra
            transformed_df.write \
                .format("org.apache.spark.sql.cassandra") \
                .options(table="classified_posts_by_hour", keyspace=self.keyspace) \
                .mode("append") \
                .save()

            logger.info(f"Batch {epoch_id}: Written {transformed_df.count()} classified posts")

        except Exception as e:
            logger.error(f"Error writing batch {epoch_id} to classified_posts_by_hour: {e}")
            raise

    def write_subreddit_aggregates(self, df, epoch_id):
        """
        Write subreddit hourly aggregates
        """
        try:
            # Transform and aggregate
            agg_df = transform_for_subreddit_hourly_agg(df)

            # Write to Cassandra
            agg_df.write \
                .format("org.apache.spark.sql.cassandra") \
                .options(table="agg_subreddit_hour", keyspace=self.keyspace) \
                .mode("append") \
                .save()

            logger.info(f"Batch {epoch_id}: Written subreddit aggregates")

        except Exception as e:
            logger.error(f"Error writing subreddit aggregates: {e}")
            raise

    def write_global_aggregates(self, df, epoch_id):
        """
        Write global hourly aggregates
        """
        try:
            # Transform and aggregate
            agg_df = transform_for_global_hourly_agg(df)

            # Write to Cassandra
            agg_df.write \
                .format("org.apache.spark.sql.cassandra") \
                .options(table="agg_global_hour", keyspace=self.keyspace) \
                .mode("append") \
                .save()

            logger.info(f"Batch {epoch_id}: Written global aggregates")

        except Exception as e:
            logger.error(f"Error writing global aggregates: {e}")
            raise
```

---

### Subtask 012.6: Batch Write Implementation

**Estimate:** 1 hour

**Description:**
- Implement foreachBatch for efficient writes
- Add batch size optimization
- Handle partial batch failures

**Acceptance Criteria:**
- Batch writes working
- Write throughput optimized
- Partial failures handled gracefully

**Implementation:**
```python
def write_stream_to_cassandra(kafka_stream_df, cassandra_writer):
    """
    Write streaming data to Cassandra using foreachBatch
    """

    def process_batch(batch_df, batch_id):
        """
        Process each micro-batch
        """
        if batch_df.count() == 0:
            logger.info(f"Batch {batch_id}: Empty batch, skipping")
            return

        logger.info(f"Batch {batch_id}: Processing {batch_df.count()} records")

        try:
            # Write raw posts
            cassandra_writer.write_raw_posts(batch_df, batch_id)

            # TODO: After model inference is implemented:
            # cassandra_writer.write_classified_posts(batch_df, batch_id)
            # cassandra_writer.write_subreddit_aggregates(batch_df, batch_id)
            # cassandra_writer.write_global_aggregates(batch_df, batch_id)

        except Exception as e:
            logger.error(f"Batch {batch_id}: Write failed: {e}")
            # Option 1: Fail the batch (default)
            raise

            # Option 2: Write to DLQ (implement later)
            # write_to_dlq(batch_df, e)

    # Start streaming query with foreachBatch
    query = kafka_stream_df.writeStream \
        .foreachBatch(process_batch) \
        .outputMode("append") \
        .option("checkpointLocation", "/tmp/spark_checkpoints/cassandra_writes") \
        .trigger(processingTime="10 seconds") \
        .start()

    return query
```

---

### Subtask 012.7: Error Handling for Writes

**Estimate:** 1.5 hours

**Description:**
- Implement retry logic for failed writes
- Add error logging with context
- Create write failure metrics

**Acceptance Criteria:**
- Transient failures retried
- Persistent failures logged
- Write failure rate tracked

**Implementation:**
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from cassandra.cluster import NoHostAvailable, WriteTimeout

class ResilientCassandraWriter(CassandraWriter):
    """
    Cassandra writer with retry logic
    """

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((NoHostAvailable, WriteTimeout)),
        reraise=True
    )
    def write_raw_posts_with_retry(self, df, epoch_id):
        """
        Write with automatic retry for transient failures
        """
        try:
            return self.write_raw_posts(df, epoch_id)

        except (NoHostAvailable, WriteTimeout) as e:
            logger.warning(f"Transient write error, will retry: {e}")
            raise

        except Exception as e:
            logger.error(f"Permanent write error: {e}")
            # Write to local DLQ
            self._write_to_local_dlq(df, e, epoch_id)
            raise

    def _write_to_local_dlq(self, df, error, epoch_id):
        """
        Write failed batch to local parquet file for later replay
        """
        dlq_path = f"/tmp/cassandra_dlq/batch_{epoch_id}_{int(time.time())}.parquet"

        try:
            df.write.parquet(dlq_path)
            logger.error(f"Batch {epoch_id} written to DLQ: {dlq_path}")

        except Exception as dlq_error:
            logger.critical(f"Failed to write to DLQ: {dlq_error}")

# Prometheus metrics for write monitoring
from prometheus_client import Counter, Histogram

cassandra_writes_total = Counter(
    'spark_cassandra_writes_total',
    'Total Cassandra write operations',
    ['table', 'status']
)

cassandra_write_latency = Histogram(
    'spark_cassandra_write_latency_seconds',
    'Cassandra write latency',
    ['table']
)

cassandra_write_batch_size = Histogram(
    'spark_cassandra_write_batch_size',
    'Number of records per write batch',
    ['table']
)
```

---

### Subtask 012.8: Connection Pool Management

**Estimate:** 45 minutes

**Description:**
- Configure connection pooling
- Implement connection health checks
- Handle connection failures gracefully

**Acceptance Criteria:**
- Connection pool sized appropriately
- Stale connections detected and refreshed
- Connection errors handled

**Implementation:**
```python
from cassandra.cluster import Cluster, ExecutionProfile, EXEC_PROFILE_DEFAULT
from cassandra.policies import DCAwareRoundRobinPolicy, TokenAwarePolicy
from cassandra.auth import PlainTextAuthProvider

def create_cassandra_session(config):
    """
    Create Cassandra session with connection pooling
    """
    cassandra_config = config['cassandra']

    # Authentication
    auth_provider = None
    if cassandra_config['auth']['enabled']:
        auth_provider = PlainTextAuthProvider(
            username=cassandra_config['auth']['username'],
            password=cassandra_config['auth']['password']
        )

    # Load balancing policy
    profile = ExecutionProfile(
        load_balancing_policy=TokenAwarePolicy(
            DCAwareRoundRobinPolicy()
        ),
        request_timeout=cassandra_config['connection']['timeout_ms'] / 1000
    )

    # Create cluster
    cluster = Cluster(
        contact_points=cassandra_config['contact_points'],
        port=cassandra_config['port'],
        auth_provider=auth_provider,
        execution_profiles={EXEC_PROFILE_DEFAULT: profile},
        protocol_version=4
    )

    # Create session
    session = cluster.connect(cassandra_config['keyspace'])

    logger.info(f"Connected to Cassandra cluster: {cassandra_config['contact_points']}")

    return session, cluster
```

---

### Subtask 012.9: Write Performance Testing

**Estimate:** 2 hours

**Description:**
- Measure write throughput
- Test with various batch sizes
- Measure write latency (p50, p95, p99)
- **[USER TASK]** Verify write performance meets requirements

**Acceptance Criteria:**
- Write throughput measured (records/sec)
- Latency percentiles documented
- Performance meets requirements (p99 <50ms)

**Test Script:**
```python
import time
from datetime import datetime

def benchmark_cassandra_writes(spark, cassandra_writer, num_records=10000):
    """
    Benchmark Cassandra write performance
    """
    # Generate test data
    test_data = spark.range(num_records).selectExpr(
        "concat('test_', id) as post_id",
        "'Test Title' as title",
        "'Test body content for performance testing' as body",
        "'testuser' as author",
        "'test_subreddit' as subreddit",
        "unix_timestamp() as created_utc",
        "cast(rand() * 100 as int) as score",
        "cast(rand() * 50 as int) as num_comments",
        "'https://reddit.com/test' as url",
        "'submission' as type",
        "'test' as source"
    )

    # Measure write time
    start_time = time.time()

    cassandra_writer.write_raw_posts(test_data, 0)

    end_time = time.time()
    duration = end_time - start_time

    # Calculate metrics
    throughput = num_records / duration
    latency_per_record = (duration / num_records) * 1000  # ms

    print(f"Performance Results:")
    print(f"  Records written: {num_records}")
    print(f"  Duration: {duration:.2f} seconds")
    print(f"  Throughput: {throughput:.2f} records/sec")
    print(f"  Avg latency per record: {latency_per_record:.3f} ms")

    return {
        'throughput': throughput,
        'latency_ms': latency_per_record,
        'duration': duration
    }

# Run benchmark
if __name__ == "__main__":
    spark = create_spark_session_with_cassandra()
    cassandra_writer = CassandraWriter(config)

    # Test different batch sizes
    for batch_size in [100, 1000, 5000, 10000]:
        print(f"\nTesting with batch size: {batch_size}")
        results = benchmark_cassandra_writes(spark, cassandra_writer, batch_size)
```

---

### Subtask 012.10: Data Consistency Verification

**Estimate:** 1 hour

**Description:**
- Verify data consistency between Kafka and Cassandra
- Check for data loss
- Verify partition keys and clustering keys

**Acceptance Criteria:**
- No data loss detected
- Data matches source
- Keys generated correctly

**Verification Script:**
```python
def verify_data_consistency(spark, cassandra_session, num_samples=1000):
    """
    Verify data written to Cassandra matches source
    """
    # Read sample from Cassandra
    cassandra_df = spark.read \
        .format("org.apache.spark.sql.cassandra") \
        .options(table="raw_posts_by_day", keyspace="reddit_rt") \
        .load() \
        .limit(num_samples)

    print(f"Sample records from Cassandra:")
    cassandra_df.show(10)

    # Check for required fields
    required_fields = ['post_date', 'post_id', 'subreddit', 'created_timestamp']
    missing_fields = [f for f in required_fields if f not in cassandra_df.columns]

    if missing_fields:
        print(f"ERROR: Missing required fields: {missing_fields}")
        return False

    # Check for nulls in critical fields
    null_counts = cassandra_df.select([
        sum(col(c).isNull().cast("int")).alias(c)
        for c in required_fields
    ]).collect()[0]

    print(f"\nNull counts in critical fields:")
    for field in required_fields:
        print(f"  {field}: {null_counts[field]}")

    # Verify partition key distribution
    partition_dist = cassandra_df.groupBy('post_date').count()
    print(f"\nPartition distribution:")
    partition_dist.show()

    return True
```

---

### Subtask 012.11: Integration with Spark Streaming Job

**Estimate:** 1 hour

**Description:**
- Integrate Cassandra writes into main streaming job
- Update streaming pipeline
- Test end-to-end flow

**Acceptance Criteria:**
- Streaming job writes to Cassandra
- Pipeline runs continuously
- Checkpoints work correctly

**Files to Update:**
- `spark/streaming_job/src/main.py`

**Implementation:**
```python
from spark_cassandra_config import create_spark_session_with_cassandra
from cassandra_writers import ResilientCassandraWriter
from schema_mapping import kafka_schema

def main():
    # Load config
    with open('config/cassandra_config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Create Spark session
    spark = create_spark_session_with_cassandra()

    # Create Cassandra writer
    cassandra_writer = ResilientCassandraWriter(config)

    # Read from Kafka
    kafka_df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "localhost:9092") \
        .option("subscribe", "reddit.posts.raw.v1") \
        .option("startingOffsets", "latest") \
        .option("maxOffsetsPerTrigger", 1000) \
        .load()

    # Parse JSON
    parsed_df = kafka_df.select(
        from_json(col("value").cast("string"), kafka_schema).alias("data")
    ).select("data.*")

    # Write to Cassandra
    query = write_stream_to_cassandra(parsed_df, cassandra_writer)

    # Wait for termination
    query.awaitTermination()

if __name__ == "__main__":
    main()
```

---

### Subtask 012.12: Monitoring and Metrics

**Estimate:** 1 hour

**Description:**
- Add Cassandra write metrics to monitoring
- Create Grafana dashboard for Cassandra metrics
- Set up alerts for write failures

**Acceptance Criteria:**
- Write metrics visible in Grafana
- Alerts configured
- Latency and throughput tracked

**Metrics to Track:**
- Write operations per second
- Write latency (p50, p95, p99)
- Write failures
- Batch size distribution
- Connection pool utilization

---

### Subtask 012.13: Documentation

**Estimate:** 1 hour

**Description:**
- Document Cassandra integration
- Add configuration guide
- Create troubleshooting guide

**Acceptance Criteria:**
- Integration documented
- Configuration examples provided
- Common issues documented

**Files to Create:**
- `spark/streaming_job/docs/cassandra_integration.md`

---

### Subtask 012.14: Final Integration Test

**Estimate:** 1 hour

**Description:**
- Run full pipeline with Cassandra writes
- Process 10k test messages
- Verify all tables populated correctly
- **[USER TASK]** Verify data quality in Cassandra

**Acceptance Criteria:**
- All messages written successfully
- No data loss
- Performance acceptable

**Test Commands:**
```bash
# Start streaming job
spark-submit \
  --class com.reddit.StreamingJob \
  --master spark://localhost:7077 \
  --packages com.datastax.spark:spark-cassandra-connector_2.12:3.2.0 \
  target/reddit-streaming-1.0.jar

# Verify data in Cassandra
cqlsh -e "SELECT COUNT(*) FROM reddit_rt.raw_posts_by_day;"
cqlsh -e "SELECT * FROM reddit_rt.raw_posts_by_day LIMIT 10;"
```

---

## Rollback Plan

If Cassandra integration fails:

1. **Disable Cassandra writes:**
   ```python
   # Comment out Cassandra write in main.py
   # query = write_stream_to_cassandra(parsed_df, cassandra_writer)

   # Use console output instead
   query = parsed_df.writeStream.format("console").start()
   ```

2. **Revert to checkpoint:**
   ```bash
   # Remove corrupt checkpoints
   rm -rf /tmp/spark_checkpoints/cassandra_writes
   ```

3. **Restart Spark job**

---

## Testing Checklist

- [ ] Connector installed and configured
- [ ] Connection to Cassandra successful
- [ ] Schema mappings correct
- [ ] Write to raw_posts_by_day works
- [ ] Batch writes optimized
- [ ] Error handling prevents data loss
- [ ] Write performance meets requirements
- [ ] Data consistency verified
- [ ] Monitoring metrics working
- [ ] Documentation complete

---

## Dependencies

**Required before starting:**
- TASK-004: Spark streaming skeleton
- TASK-006: Cassandra cluster with tables

**Blocks:**
- TASK-014: End-to-End Data Flow Test
- TASK-015: Grafana Live Data Connection
- TASK-037: Aggregation Recompute DAG

---

## Notes

- Use LOCAL_QUORUM consistency for writes in production
- Monitor connection pool size under load
- Consider using prepared statements for better performance
- TTL settings in Cassandra tables handle data retention
- Test write performance with production-like data volumes

---

## Estimated Completion

**Total Time:** 14-16 hours (1.5 days)

**Breakdown:**
- Setup & Configuration: 3 hours
- Schema Mapping & Write Logic: 5 hours
- Error Handling & Testing: 4 hours
- Performance Testing & Optimization: 3 hours
- Documentation: 1 hour
