# TASK-004: Spark Structured Streaming Skeleton

**Owner:** ML/Spark Engineer
**Priority:** Critical
**Dependencies:** TASK-001 (Kafka Cluster Setup)
**Estimate:** 2 days

---

## Overview
Set up Apache Spark Structured Streaming framework with Kafka integration for processing Reddit posts in real-time.

---

## Subtasks

### 4.1 Verify Spark Cluster in Docker
**Status:** Not Started
**Type:** Automated
**Estimate:** 30 minutes

- [ ] Verify Spark Master service in docker-compose.yml
- [ ] Verify Spark Worker service in docker-compose.yml
- [ ] Check port configurations (8081 for UI, 7077 for master, 4040 for job UI)
- [ ] Verify volume mounts for apps and data
- [ ] Start Spark services
- [ ] **[USER TASK]** Access Spark Master UI at http://localhost:8081
- [ ] Verify worker registered with master

**Acceptance Criteria:**
- Spark Master running and accessible
- At least 1 worker connected
- Spark UI shows cluster resources

---

### 4.2 Project Structure Setup
**Status:** Not Started
**Type:** Automated
**Estimate:** 20 minutes

- [ ] Create `spark/` directory structure:
  - `spark/apps/` (application code)
  - `spark/apps/streaming/` (streaming jobs)
  - `spark/apps/batch/` (batch jobs)
  - `spark/data/` (test data)
  - `spark/checkpoints/` (streaming checkpoints)
  - `spark/config/` (configuration files)
- [ ] Create `spark/apps/streaming/requirements.txt`
- [ ] Create `.gitignore` for Spark artifacts

**Acceptance Criteria:**
- Directory structure created
- Ready for Spark development

---

### 4.3 Install Spark Dependencies
**Status:** Not Started
**Type:** Automated
**Estimate:** 30 minutes

**Dependencies needed:**
- [ ] pyspark (3.5.0)
- [ ] kafka-python
- [ ] python-dotenv

- [ ] Create `spark/apps/streaming/requirements.txt` with versions
- [ ] Document installation for local development
- [ ] Create virtual environment setup instructions

**Acceptance Criteria:**
- requirements.txt created with pinned versions
- Dependencies documented

---

### 4.4 Kafka-Spark Configuration
**Status:** Not Started
**Type:** Automated
**Estimate:** 1 hour

- [ ] Create `spark/config/spark_config.py`
- [ ] Define Spark session configuration:
  - App name
  - Master URL (spark://spark-master:7077)
  - Executor memory (2G)
  - Executor cores (2)
  - Kafka package: org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0
- [ ] Define Kafka source configuration:
  - Bootstrap servers (kafka:29092)
  - Subscribe to topic (reddit.posts.raw.v1)
  - Starting offsets (earliest/latest)
  - Max offsets per trigger
  - Fail on data loss (false for dev)
- [ ] Create config loader function

**Acceptance Criteria:**
- Configuration module created
- All parameters documented
- Easy to override for different environments

---

### 4.5 Create Spark Session Builder
**Status:** Not Started
**Type:** Automated
**Estimate:** 45 minutes

- [ ] Create `spark/apps/streaming/spark_session_builder.py`
- [ ] Implement `create_spark_session()` function
- [ ] Configure Spark session with:
  - Streaming checkpoint location
  - Log level (WARN for dev, INFO for prod)
  - Kafka packages
  - Shuffle partitions (tuned for cluster)
- [ ] Add error handling
- [ ] Add logging

**Acceptance Criteria:**
- Can create Spark session successfully
- Kafka package loaded
- Configuration applied correctly

---

### 4.6 Define Reddit Post Schema
**Status:** Not Started
**Type:** Automated
**Estimate:** 30 minutes

- [ ] Create `spark/apps/streaming/schemas.py`
- [ ] Define StructType schema for Reddit posts:
  - post_id (StringType)
  - kind (StringType)
  - subreddit (StringType)
  - title (StringType, nullable)
  - body (StringType)
  - created_utc (StringType/TimestampType)
  - author_hash (StringType)
  - permalink (StringType)
  - ingest_ts (StringType/TimestampType)
  - source (StringType)
- [ ] Add schema validation function
- [ ] Document schema version

**Acceptance Criteria:**
- Schema matches Kafka message format
- All fields properly typed
- Schema reusable across jobs

---

### 4.7 Kafka Source Setup
**Status:** Not Started
**Type:** Automated
**Estimate:** 1 hour

- [ ] Create `spark/apps/streaming/kafka_source.py`
- [ ] Implement function to read from Kafka:
  - Connect to Kafka topic
  - Configure starting offset strategy
  - Set max offsets per trigger (for backpressure)
- [ ] Parse Kafka message:
  - Extract key, value, timestamp, partition, offset
  - Deserialize value from JSON
- [ ] Apply schema to JSON data
- [ ] Add error handling for malformed JSON

**Acceptance Criteria:**
- Can read from Kafka topic
- JSON parsed correctly
- Schema applied successfully
- Errors handled gracefully

---

### 4.8 Schema Validation and Parsing
**Status:** Not Started
**Type:** Automated
**Estimate:** 1 hour

- [ ] Create `spark/apps/streaming/validators.py`
- [ ] Implement validation functions:
  - Check required fields present
  - Validate data types
  - Validate timestamp formats
  - Check field constraints (e.g., post_id not empty)
- [ ] Add validation column to DataFrame
- [ ] Separate valid and invalid records
- [ ] Route invalid records to error handling

**Acceptance Criteria:**
- Validation catches malformed records
- Valid records processed normally
- Invalid records isolated for DLQ

---

### 4.9 Deduplication Logic
**Status:** Not Started
**Type:** Automated
**Estimate:** 1.5 hours

- [ ] Implement deduplication based on `post_id`
- [ ] Configure watermark for late data (24 hours)
- [ ] Use `dropDuplicates()` with watermark
- [ ] Test with duplicate data
- [ ] Measure deduplication effectiveness

**Acceptance Criteria:**
- Duplicates removed correctly
- Watermark configured (24 hours)
- Late data handled appropriately
- Deduplication rate >99.9%

---

### 4.10 Checkpointing Configuration
**Status:** Not Started
**Type:** Automated
**Estimate:** 1 hour

- [ ] Configure checkpoint location:
  - Local: `spark/checkpoints/reddit_streaming/`
  - Container: `/opt/spark-data/checkpoints/`
- [ ] Set checkpoint interval (default: 10 seconds)
- [ ] Implement checkpoint cleanup for old runs
- [ ] Test checkpoint recovery:
  - Start job
  - Process some data
  - Kill job
  - Restart and verify recovery

**Acceptance Criteria:**
- Checkpointing enabled
- Checkpoint directory configured
- Recovery from checkpoint works
- No data loss during recovery

---

### 4.11 Basic Console Sink (for testing)
**Status:** Not Started
**Type:** Automated
**Estimate:** 30 minutes

- [ ] Implement console output for testing
- [ ] Format output for readability
- [ ] Add trigger configuration (processing time: 10 seconds)
- [ ] Limit rows shown (10-20)
- [ ] Test with mock data from Kafka

**Acceptance Criteria:**
- Console sink displays data
- Data formatted clearly
- Trigger interval configurable

---

### 4.12 Memory Sink (for testing)
**Status:** Not Started
**Type:** Automated
**Estimate:** 30 minutes

- [ ] Implement memory sink for unit testing
- [ ] Query memory table after each batch
- [ ] Create helper functions to inspect data
- [ ] Test with small datasets

**Acceptance Criteria:**
- Memory sink stores data
- Can query results
- Useful for testing transformations

---

### 4.13 Main Streaming Application
**Status:** Not Started
**Type:** Automated
**Estimate:** 2 hours

- [ ] Create `spark/apps/streaming/reddit_stream_processor.py`
- [ ] Implement main application:
  - Initialize Spark session
  - Read from Kafka
  - Parse and validate
  - Deduplicate
  - Apply basic transformations (timestamp parsing)
  - Write to console (for now)
- [ ] Add argument parsing:
  - --kafka-brokers
  - --topic
  - --checkpoint-location
  - --output-mode (append/update/complete)
- [ ] Implement graceful shutdown
- [ ] Add logging and metrics

**Acceptance Criteria:**
- Application runs end-to-end
- Reads from Kafka
- Processes data
- Outputs to console
- Handles shutdown gracefully

---

### 4.14 Error Handling and DLQ Integration
**Status:** Not Started
**Type:** Automated
**Estimate:** 1.5 hours

- [ ] Implement error handling for:
  - JSON parsing errors
  - Schema validation errors
  - Processing exceptions
- [ ] Integrate with DLQ (TASK-003)
- [ ] Route error records to DLQ topic
- [ ] Include error metadata
- [ ] Log all errors

**Acceptance Criteria:**
- All errors caught and handled
- Error records sent to DLQ
- No job failures from bad data
- Error metadata complete

---

### 4.15 Monitoring and Metrics
**Status:** Not Started
**Type:** Automated
**Estimate:** 1 hour

- [ ] Expose Spark metrics:
  - Input rate (records/sec)
  - Processing rate (records/sec)
  - Batch duration
  - Input rows
  - Processed rows
- [ ] Add custom metrics:
  - Valid records count
  - Invalid records count
  - Deduplication count
- [ ] Configure Spark UI access
- [ ] Document metrics locations

**Acceptance Criteria:**
- Metrics visible in Spark UI
- Custom metrics tracked
- Can monitor job health

---

### 4.16 Unit Tests
**Status:** Not Started
**Type:** Automated
**Estimate:** 2 hours

- [ ] Create `spark/apps/streaming/tests/`
- [ ] Test schema parsing
- [ ] Test validation logic
- [ ] Test deduplication
- [ ] Test error handling
- [ ] Test with sample data
- [ ] Mock Kafka for testing

**Acceptance Criteria:**
- All core functions tested
- Tests pass consistently
- Test coverage >80%

---

### 4.17 Integration Test with Kafka
**Status:** Not Started
**Type:** Automated + Manual
**Estimate:** 1 hour

- [ ] Ensure Kafka and Spark are running
- [ ] Start mock producer (TASK-002)
- [ ] Start Spark streaming job
- [ ] Let run for 5 minutes
- [ ] **[USER TASK]** Verify in Spark UI:
  - Job is running
  - Batches processing
  - Input rate matches producer rate
  - No errors in logs
- [ ] Check checkpoint directory has files
- [ ] Test graceful shutdown

**Acceptance Criteria:**
- Job processes data from Kafka
- No errors or failures
- Checkpoint files created
- Graceful shutdown works

---

### 4.18 Performance Tuning
**Status:** Not Started
**Type:** Automated
**Estimate:** 1.5 hours

- [ ] Tune batch interval (5s, 10s, 30s)
- [ ] Tune max offsets per trigger
- [ ] Tune shuffle partitions
- [ ] Measure processing latency
- [ ] Optimize for throughput vs latency
- [ ] Document optimal settings

**Acceptance Criteria:**
- Batch processing time < 60 seconds
- Can handle 1000+ records/minute
- Resource utilization optimized

---

### 4.19 Documentation
**Status:** Not Started
**Type:** Manual
**Estimate:** 1.5 hours

- [ ] Create `spark/apps/streaming/README.md`
- [ ] Document architecture
- [ ] Document how to run locally
- [ ] Document how to run in cluster
- [ ] Document configuration options
- [ ] Add troubleshooting guide
- [ ] Document checkpointing behavior
- [ ] Add example commands

**Acceptance Criteria:**
- Complete documentation
- Easy to follow
- Covers common issues

---

### 4.20 Submission Script
**Status:** Not Started
**Type:** Automated
**Estimate:** 1 hour

- [ ] Create `spark/scripts/submit-streaming-job.sh`
- [ ] Script parameters:
  - Master URL
  - Deploy mode (client/cluster)
  - Executor configuration
  - Application arguments
- [ ] Add validation checks
- [ ] Make script executable
- [ ] Test submission

**Acceptance Criteria:**
- Script submits job successfully
- Parameters configurable
- Works in both local and cluster mode

---

## Final Acceptance Criteria Checklist

- [ ] Spark job consumes from Kafka topic
- [ ] JSON parsing works correctly
- [ ] Schema validation functional
- [ ] Checkpointing enabled and tested
- [ ] Job recovers from failures without data loss
- [ ] Deduplication working (>99.9% effective)
- [ ] Error handling routes to DLQ
- [ ] Can process 1000+ records/minute
- [ ] All tests pass
- [ ] Documentation complete
- [ ] **[USER TASK]** Manual verification in Spark UI completed

---

## Dependencies for Next Tasks

This task must be completed before:
- TASK-005: Model Inference Stub (needs streaming framework)
- TASK-012: Spark-Cassandra Integration (builds on this)
- TASK-013: Text Cleaning Pipeline (uses this framework)
- TASK-014: End-to-End Data Flow Test (needs working stream)

---

## Rollback Plan

If this task fails:
1. Stop Spark streaming job
2. Clear checkpoint directory
3. Fix code issues
4. Restart from subtask 4.17 (integration test)

---

## Example Usage

```bash
# Submit streaming job
spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
  spark/apps/streaming/reddit_stream_processor.py \
  --kafka-brokers kafka:29092 \
  --topic reddit.posts.raw.v1 \
  --checkpoint-location /opt/spark-data/checkpoints/reddit_streaming
```

---

## Notes

- Start with console sink for initial testing
- Will add Cassandra sink in TASK-012
- Checkpointing is critical for exactly-once processing
- Monitor Spark UI to tune performance
- Watermark prevents memory issues with deduplication
- Test recovery frequently during development
