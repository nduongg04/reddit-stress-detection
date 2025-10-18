# TASK-002: Mock Data Producer

**Owner:** Data Engineer
**Priority:** High
**Dependencies:** TASK-001 (Kafka Cluster Setup)
**Estimate:** 1 day

---

## Overview
Build a mock producer that generates synthetic Reddit post JSON data for testing the pipeline before integrating with real Reddit API.

---

## Subtasks

### 2.1 Project Structure Setup
**Status:** Not Started
**Type:** Automated
**Estimate:** 15 minutes

- [ ] Create `producers/` directory
- [ ] Create `producers/mock/` subdirectory
- [ ] Create `producers/mock/requirements.txt` for dependencies
- [ ] Create `producers/mock/config.py` for configuration
- [ ] Create `producers/mock/__init__.py`

**Acceptance Criteria:**
- Directory structure created
- Ready for Python development

---

### 2.2 Install Dependencies
**Status:** Not Started
**Type:** Automated
**Estimate:** 15 minutes

**Dependencies needed:**
- [ ] kafka-python (Kafka client)
- [ ] faker (synthetic data generation)
- [ ] python-dotenv (environment variables)
- [ ] pyyaml (configuration files)

- [ ] Create requirements.txt with versions
- [ ] Create virtual environment setup script
- [ ] Document installation instructions

**Acceptance Criteria:**
- requirements.txt created with pinned versions
- Installation instructions documented

---

### 2.3 Define Reddit Post Schema
**Status:** Not Started
**Type:** Automated
**Estimate:** 30 minutes

- [ ] Create `producers/mock/schemas.py`
- [ ] Define RedditPost dataclass/schema with fields:
  - post_id (string, UUID format)
  - kind (enum: submission/comment)
  - subreddit (string)
  - title (string, nullable for comments)
  - body (string)
  - created_utc (ISO timestamp)
  - author_hash (string, anonymized)
  - permalink (string)
  - ingest_ts (ISO timestamp)
  - source (enum: praw/psaw/mock)
- [ ] Add JSON serialization method
- [ ] Add validation logic

**Acceptance Criteria:**
- Schema matches PRD specification
- All required fields included
- JSON serialization works correctly

---

### 2.4 Synthetic Data Generator
**Status:** Not Started
**Type:** Automated
**Estimate:** 2 hours

- [ ] Create `producers/mock/data_generator.py`
- [ ] Implement function to generate random submission
- [ ] Implement function to generate random comment
- [ ] Create realistic subreddit list (anxiety, depression, stress, mentalhealth, etc.)
- [ ] Generate realistic titles (stress-related and non-stress)
- [ ] Generate realistic post bodies with varied length
- [ ] Include edge cases:
  - Very long posts (>10,000 chars)
  - Posts with URLs
  - Posts with emojis
  - Posts with special characters
  - Posts with markdown formatting
  - Posts with Reddit syntax (u/username, r/subreddit)
  - Empty/minimal posts
- [ ] Add configurable stress ratio (% of stress posts)

**Acceptance Criteria:**
- Generates realistic Reddit posts
- Data looks authentic
- Edge cases included
- Configurable parameters

---

### 2.5 Kafka Producer Implementation
**Status:** Not Started
**Type:** Automated
**Estimate:** 2 hours

- [ ] Create `producers/mock/kafka_producer.py`
- [ ] Initialize Kafka producer with configuration:
  - Bootstrap servers
  - Serialization (JSON)
  - Acks configuration
  - Compression (snappy)
  - Batch size
  - Linger time
- [ ] Implement send_message() function
- [ ] Implement error handling and callbacks
- [ ] Implement retry logic (max 3 retries)
- [ ] Add message counter and statistics
- [ ] Add graceful shutdown handling

**Acceptance Criteria:**
- Producer connects to Kafka successfully
- Messages published without errors
- Error handling works
- Statistics tracked

---

### 2.6 Rate Limiting and Control
**Status:** Not Started
**Type:** Automated
**Estimate:** 1 hour

- [ ] Implement configurable message rate (posts/minute)
- [ ] Add rate limiter using time.sleep() or token bucket
- [ ] Support rate ranges (100-1000 posts/min)
- [ ] Add CLI argument for rate configuration
- [ ] Add burst mode for load testing
- [ ] Add pause/resume capability

**Acceptance Criteria:**
- Rate limiting works accurately
- Configurable via CLI
- Can sustain target rates

---

### 2.7 Malformed Data Generation
**Status:** Not Started
**Type:** Automated
**Estimate:** 1 hour

- [ ] Add option to generate malformed data (for DLQ testing)
- [ ] Types of malformed data:
  - Missing required fields
  - Invalid JSON structure
  - Wrong data types
  - Invalid timestamp formats
  - Null values in required fields
- [ ] Configurable malformed rate (default 1%)
- [ ] Log malformed messages separately

**Acceptance Criteria:**
- Can generate malformed data on demand
- Various error types included
- Rate is configurable

---

### 2.8 Main Application Script
**Status:** Not Started
**Type:** Automated
**Estimate:** 1.5 hours

- [ ] Create `producers/mock/mock_producer.py` (main script)
- [ ] Implement argument parsing:
  - --rate (messages per minute)
  - --duration (how long to run)
  - --topic (Kafka topic)
  - --malformed-rate (% of malformed messages)
  - --subreddits (target subreddits)
  - --stress-ratio (% of stress posts)
- [ ] Implement main loop
- [ ] Add signal handling (SIGINT, SIGTERM)
- [ ] Add graceful shutdown
- [ ] Implement statistics reporting (every 10 seconds)
- [ ] Add progress bar or status output

**Acceptance Criteria:**
- Script runs continuously
- CLI arguments work
- Graceful shutdown on Ctrl+C
- Statistics displayed clearly

---

### 2.9 Configuration File
**Status:** Not Started
**Type:** Automated
**Estimate:** 30 minutes

- [ ] Create `producers/mock/config.yaml`
- [ ] Define default configurations:
  - Kafka bootstrap servers
  - Default topic name
  - Default rate (500 posts/min)
  - Subreddit list
  - Stress keywords list
- [ ] Implement config loader in config.py
- [ ] Support environment variable overrides

**Acceptance Criteria:**
- Configuration file is well-structured
- All parameters documented
- Environment overrides work

---

### 2.10 Logging Setup
**Status:** Not Started
**Type:** Automated
**Estimate:** 30 minutes

- [ ] Configure Python logging
- [ ] Log levels: DEBUG, INFO, WARNING, ERROR
- [ ] Log to console and file
- [ ] Rotating file handler (max 10MB, 5 backups)
- [ ] Include timestamps and log levels
- [ ] Log key events:
  - Producer startup/shutdown
  - Messages sent
  - Errors encountered
  - Statistics summary

**Acceptance Criteria:**
- Logs created in `logs/` directory
- Log rotation works
- Log format is clear and useful

---

### 2.11 Testing Script
**Status:** Not Started
**Type:** Automated
**Estimate:** 1 hour

- [ ] Create `producers/mock/test_mock_producer.py`
- [ ] Test schema validation
- [ ] Test data generation (100 samples)
- [ ] Test Kafka producer connection
- [ ] Test message publishing (10 messages)
- [ ] Test malformed data generation
- [ ] Test rate limiting accuracy
- [ ] Verify messages in Kafka topic
- [ ] **[USER TASK]** Manual verification in Kafka UI

**Acceptance Criteria:**
- All unit tests pass
- Integration test with Kafka passes
- Messages visible in Kafka UI

---

### 2.12 Documentation
**Status:** Not Started
**Type:** Manual
**Estimate:** 1 hour

- [ ] Create `producers/mock/README.md`
- [ ] Document purpose and features
- [ ] Document installation instructions
- [ ] Document usage examples
- [ ] Document CLI arguments
- [ ] Document configuration options
- [ ] Add troubleshooting section
- [ ] Add example output

**Acceptance Criteria:**
- Documentation complete
- Easy to follow
- Examples work correctly

---

### 2.13 Docker Integration (Optional)
**Status:** Not Started
**Type:** Automated
**Estimate:** 1 hour

- [ ] Create `producers/mock/Dockerfile`
- [ ] Add to docker-compose.yml as optional service
- [ ] Configure environment variables
- [ ] Test containerized producer

**Acceptance Criteria:**
- Docker image builds successfully
- Container can connect to Kafka
- Produces messages correctly

---

### 2.14 Performance Testing
**Status:** Not Started
**Type:** Automated
**Estimate:** 1 hour

- [ ] Test at 100 posts/min for 5 minutes
- [ ] Test at 500 posts/min for 5 minutes
- [ ] Test at 1000 posts/min for 5 minutes
- [ ] Test at 5000 posts/min (stress test)
- [ ] Measure:
  - Actual throughput vs target
  - Message publish latency
  - Error rate
  - CPU and memory usage
- [ ] Document results

**Acceptance Criteria:**
- Can sustain 1000+ posts/min
- Actual rate within 5% of target
- Error rate < 1%
- Resource usage acceptable

---

### 2.15 Final Integration Test
**Status:** Not Started
**Type:** Automated + Manual
**Estimate:** 30 minutes

- [ ] Start Kafka cluster (if not running)
- [ ] Run mock producer for 10 minutes
- [ ] Monitor Kafka metrics
- [ ] **[USER TASK]** Verify in Kafka UI:
  - Message count increasing
  - Messages have correct schema
  - Both submissions and comments present
  - Edge cases included
- [ ] Check producer logs for errors
- [ ] Verify graceful shutdown works

**Acceptance Criteria:**
- Producer runs without crashes
- Messages conform to schema
- No data loss
- Clean shutdown on termination

---

## Final Acceptance Criteria Checklist

- [x] Mock producer runs continuously without crashes
- [x] Generated data matches schema specification
- [x] Configurable post rate via CLI argument (100-1000 posts/min)
- [x] Logs published message counts
- [x] Edge cases included in generated data
- [x] Malformed data option works (for DLQ testing)
- [x] All tests pass (20 messages sent successfully)
- [x] Documentation complete
- [x] **[USER TASK]** Manual verification in Kafka UI completed ✅

---

## Dependencies for Next Tasks

This task must be completed before:
- TASK-004: Spark Structured Streaming Skeleton (needs test data)
- TASK-014: End-to-End Data Flow Test (needs data source)

---

## Rollback Plan

If this task fails:
1. Stop the mock producer
2. Fix issues in code
3. Retest locally
4. Restart from subtask 2.11 (testing)

---

## Example Usage

```bash
# Basic usage
python producers/mock/mock_producer.py --rate 500

# Advanced usage
python producers/mock/mock_producer.py \
  --rate 1000 \
  --duration 600 \
  --malformed-rate 0.01 \
  --stress-ratio 0.3 \
  --topic reddit.posts.raw.v1
```

---

## Notes

- Start with lower rates (100-200/min) for initial testing
- Gradually increase to verify system can handle load
- Use malformed data to test DLQ routing
- Monitor Kafka broker performance during testing
