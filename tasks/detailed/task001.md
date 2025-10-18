# TASK-001: Kafka Cluster Setup

**Owner:** Data Engineer
**Priority:** Critical
**Dependencies:** None
**Estimate:** 2 days

---

## Overview
Set up Apache Kafka cluster with proper configuration for real-time Reddit post streaming.

---

## Subtasks

### 1.1 Docker Infrastructure Setup
**Status:** Completed
**Type:** Automated
**Estimate:** 30 minutes

- [x] Create `docker-compose.yml` file
- [x] Define Zookeeper service configuration
- [x] Define Kafka broker service configuration
- [x] Configure service dependencies and health checks
- [x] Set up Docker volumes for data persistence
- [x] Define Docker network for inter-service communication

**Acceptance Criteria:**
- Docker compose file is valid YAML
- All services defined with proper health checks
- Volumes configured for persistence

---

### 1.2 Zookeeper Configuration
**Status:** Completed
**Type:** Automated
**Estimate:** 20 minutes

- [x] Set Zookeeper client port (2181)
- [x] Configure tick time (2000ms)
- [x] Set up data and log volumes
- [x] Configure health check endpoint
- [x] Test Zookeeper connectivity

**Acceptance Criteria:**
- Zookeeper starts successfully
- Health check passes
- Port 2181 is accessible

---

### 1.3 Kafka Broker Configuration
**Status:** Completed
**Type:** Automated
**Estimate:** 1 hour

- [x] Set broker ID and Zookeeper connection
- [x] Configure listener protocols (PLAINTEXT)
- [x] Set advertised listeners for internal/external access
- [x] Configure replication factors
  - Offsets topic: 1 (single node dev)
  - Transaction log: 1
- [x] Set auto-create topics to false (manual control)
- [x] Configure JMX port (9997) for monitoring
- [x] Set message retention policy (168 hours = 7 days)
- [x] Configure log segment size (1GB)
- [x] Set log retention check interval (5 minutes)

**Acceptance Criteria:**
- Kafka broker starts and connects to Zookeeper
- Ports 9092 (client) and 9997 (JMX) accessible
- Configuration matches requirements

---

### 1.4 Create Kafka Topics
**Status:** Completed
**Type:** Automated
**Estimate:** 1 hour

- [x] Create initialization script `scripts/init-kafka-topics.sh`
- [x] Define topic: `reddit.posts.raw.v1`
  - Partitions: 6
  - Replication factor: 1
  - Retention: 7 days
- [x] Define topic: `reddit.posts.dlq.v1`
  - Partitions: 3
  - Replication factor: 1
  - Retention: 7 days
- [x] Add topic listing verification
- [x] Add topic describe commands for validation
- [x] Make script executable

**Acceptance Criteria:**
- Both topics created successfully
- Partition strategy correct
- Retention policies configured
- Script is idempotent (can run multiple times)

---

### 1.5 Kafka UI Setup
**Status:** Completed
**Type:** Automated
**Estimate:** 30 minutes

- [x] Add Kafka UI service to docker-compose
- [x] Configure connection to Kafka broker
- [x] Configure connection to Zookeeper
- [x] Set up JMX monitoring connection
- [x] Expose on port 8080

**Acceptance Criteria:**
- Kafka UI accessible at http://localhost:8080
- Can view cluster information
- Can view topics and messages
- JMX metrics visible

---

### 1.6 Testing Scripts
**Status:** Completed
**Type:** Automated
**Estimate:** 1 hour

- [x] Create `scripts/test-kafka.sh` test script
- [x] Test 1: Container running check
- [x] Test 2: Broker connectivity check
- [x] Test 3: Topic existence verification
- [x] Test 4: Produce test message
- [x] Test 5: Consume test message
- [x] Test 6: JMX metrics accessibility
- [x] Test 7: Consumer group functionality
- [x] Make script executable
- [x] Add clear pass/fail output

**Acceptance Criteria:**
- All tests pass successfully
- Clear error messages on failure
- Script exits with proper status codes

---

### 1.7 Documentation
**Status:** Completed
**Type:** Manual
**Estimate:** 1 hour

- [x] Create `docs/kafka-setup.md` documentation
- [x] Document architecture decisions
- [x] Document topic naming conventions
- [x] Document partition strategy
- [x] Document retention policies
- [x] Add startup instructions
- [x] Add shutdown instructions
- [x] Add troubleshooting section
- [x] Document common issues and solutions

**Acceptance Criteria:**
- Documentation is complete and clear
- New team member can follow instructions
- All configuration explained

---

### 1.8 Start Services and Verify
**Status:** Completed
**Type:** Automated + Manual Verification
**Estimate:** 30 minutes

- [x] **[USER TASK]** Start Docker Desktop or Docker daemon
- [x] Run `docker-compose up -d` to start services
- [x] Wait for all services to become healthy
- [x] Run topic initialization script: `./scripts/init-kafka-topics.sh`
- [x] Verify topics created successfully
- [x] Run test script to validate setup: `./scripts/test-kafka.sh`
- [x] **[USER TASK]** Manually verify Kafka UI at http://localhost:8080
- [x] **[USER TASK]** Check topics visible in UI
- [x] **[USER TASK]** Verify JMX metrics in UI

**Acceptance Criteria:**
- All containers running (docker ps shows healthy)
- Topics created with correct configuration
- Test script passes all checks
- Kafka UI accessible and shows correct data
- No error logs in containers

---

### 1.9 Performance Baseline
**Status:** Completed
**Type:** Automated
**Estimate:** 30 minutes

- [x] Create performance test script
- [x] Measure baseline throughput (messages/sec): 53,475 records/sec
- [x] Measure baseline latency (p50, p95, p99): 22ms, 33ms, 34ms
- [x] Document baseline metrics in performance-results/
- [x] Verify can handle 1000+ messages/min: ✓ 3.2M+ msg/min

**Acceptance Criteria:**
- Baseline metrics documented
- Throughput meets minimum requirements
- Latency acceptable for real-time processing

---

### 1.10 Monitoring Setup
**Status:** Completed
**Type:** Automated
**Estimate:** 1 hour

- [x] Verify JMX exporter is running
- [x] Document available JMX metrics
- [x] Create sample queries for monitoring
- [x] Test metrics scraping via JMX port 9997
- [x] Document how to access metrics

**Acceptance Criteria:**
- JMX metrics accessible on port 9997
- Key metrics documented (throughput, lag, etc.)
- Monitoring queries tested

---

## Final Acceptance Criteria Checklist

- [x] Kafka cluster operational with health checks passing
- [x] Topics created with correct partitioning strategy (6 partitions for raw, 3 for DLQ)
- [x] Producer/consumer can publish/read test messages
- [x] Monitoring dashboard shows broker metrics
- [x] All test scripts pass
- [x] Documentation complete
- [x] **[USER TASK]** Manual verification completed

---

## Dependencies for Next Tasks

This task must be completed before:
- TASK-002: Mock Data Producer (depends on Kafka topics)
- TASK-003: Dead Letter Queue Configuration (depends on Kafka topics)
- TASK-004: Spark Structured Streaming Skeleton (depends on Kafka broker)
- TASK-009: Reddit API Integration (depends on Kafka infrastructure)

---

## Rollback Plan

If this task fails:
1. Run `docker-compose down -v` to remove all containers and volumes
2. Fix configuration issues
3. Restart from subtask 1.8

---

## Notes

- Using single-node Kafka for development (replication factor = 1)
- Production will need multi-node setup with replication factor = 3
- Topics set to NOT auto-create for better control
- Retention set to 7 days to balance storage and data availability
