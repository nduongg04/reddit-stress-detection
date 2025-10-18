# TASK-003: Dead Letter Queue (DLQ) Configuration

**Owner:** Data Engineer
**Priority:** Medium
**Dependencies:** TASK-001 (Kafka Cluster Setup)
**Estimate:** 0.5 days

---

## Overview
Configure Dead Letter Queue for handling malformed messages and errors in the data pipeline.

---

## Subtasks

### 3.1 DLQ Topic Configuration
**Status:** Not Started
**Type:** Automated
**Estimate:** 15 minutes

- [ ] Verify `reddit.posts.dlq.v1` topic exists (created in TASK-001)
- [ ] Verify topic configuration:
  - Partitions: 3
  - Replication factor: 1 (dev), 3 (prod)
  - Retention: 7 days
- [ ] Document DLQ topic purpose and usage

**Acceptance Criteria:**
- DLQ topic operational
- Configuration matches requirements
- Purpose documented

---

### 3.2 Define DLQ Message Schema
**Status:** Not Started
**Type:** Automated
**Estimate:** 30 minutes

- [ ] Create `schemas/dlq_schema.py`
- [ ] Define DLQMessage schema with fields:
  - error_id (UUID, unique identifier)
  - original_topic (string, source topic)
  - original_partition (int)
  - original_offset (long)
  - original_payload (string, raw message)
  - error_type (enum: SCHEMA_VALIDATION, JSON_PARSE, PROCESSING_ERROR, etc.)
  - error_message (string, detailed error)
  - error_stacktrace (string, full stack trace)
  - retry_count (int, number of retry attempts)
  - timestamp (ISO timestamp, when error occurred)
  - producer_id (string, which component produced error)
- [ ] Add JSON serialization method
- [ ] Add validation logic

**Acceptance Criteria:**
- Schema includes all error metadata
- Can serialize to JSON
- Schema documented

---

### 3.3 DLQ Producer Utility
**Status:** Not Started
**Type:** Automated
**Estimate:** 1 hour

- [ ] Create `utils/dlq_producer.py`
- [ ] Implement DLQProducer class
- [ ] Methods:
  - `send_to_dlq(original_message, error, metadata)`
  - `send_batch_to_dlq(messages)`
- [ ] Configure Kafka producer for DLQ
- [ ] Add error handling for DLQ publish failures
- [ ] Add logging for DLQ operations
- [ ] Implement retry logic (if DLQ publish fails, log to file)

**Acceptance Criteria:**
- Can send messages to DLQ topic
- Error metadata captured correctly
- Handles DLQ publish failures gracefully

---

### 3.4 Error Classification
**Status:** Not Started
**Type:** Automated
**Estimate:** 45 minutes

- [ ] Create `utils/error_classifier.py`
- [ ] Define error types enum:
  - SCHEMA_VALIDATION_ERROR
  - JSON_PARSE_ERROR
  - MISSING_REQUIRED_FIELD
  - INVALID_DATA_TYPE
  - PROCESSING_ERROR
  - TIMEOUT_ERROR
  - UNKNOWN_ERROR
- [ ] Implement classify_error() function
- [ ] Map Python exceptions to error types
- [ ] Add error severity levels (WARNING, ERROR, CRITICAL)

**Acceptance Criteria:**
- All common errors classified
- Clear error categorization
- Severity levels assigned

---

### 3.5 Integration with Mock Producer
**Status:** Not Started
**Type:** Automated
**Estimate:** 1 hour

- [ ] Update mock producer to use DLQ
- [ ] When malformed message generated:
  - Try to send to main topic
  - Catch exception
  - Send to DLQ with error details
- [ ] Add statistics for DLQ messages
- [ ] Log DLQ operations

**Acceptance Criteria:**
- Malformed messages routed to DLQ
- Error metadata included
- Statistics tracked

---

### 3.6 DLQ Consumer for Monitoring
**Status:** Not Started
**Type:** Automated
**Estimate:** 1.5 hours

- [ ] Create `consumers/dlq_monitor.py`
- [ ] Implement DLQ consumer that reads from DLQ topic
- [ ] Parse DLQ messages
- [ ] Display error summary:
  - Total errors by type
  - Error rate over time
  - Top error messages
- [ ] Option to save errors to file for analysis
- [ ] Add CLI for querying DLQ

**Acceptance Criteria:**
- Can consume and display DLQ messages
- Error summary is useful
- CLI works correctly

---

### 3.7 DLQ Replay Mechanism
**Status:** Not Started
**Type:** Automated
**Estimate:** 2 hours

- [ ] Create `utils/dlq_replay.py`
- [ ] Implement replay functionality:
  - Read messages from DLQ
  - Fix if possible (e.g., schema corrections)
  - Re-publish to original topic
  - Mark as replayed in DLQ
- [ ] Add filters:
  - By error type
  - By time range
  - By retry count
- [ ] Add dry-run mode (preview without replay)
- [ ] Track replay statistics

**Acceptance Criteria:**
- Can replay messages from DLQ
- Filters work correctly
- Dry-run mode helps verify before replay
- Statistics tracked

---

### 3.8 DLQ Alerting Configuration
**Status:** Not Started
**Type:** Automated
**Estimate:** 1 hour

- [ ] Define alerting thresholds:
  - DLQ rate > 5% of total messages
  - Specific error types spike
  - DLQ size exceeds threshold
- [ ] Create alert configuration file
- [ ] Implement alert checker script
- [ ] Prepare for integration with monitoring (TASK-036)

**Acceptance Criteria:**
- Alert thresholds defined
- Alert logic implemented
- Ready for monitoring integration

---

### 3.9 Testing
**Status:** Not Started
**Type:** Automated
**Estimate:** 1 hour

- [ ] Create `tests/test_dlq.py`
- [ ] Test DLQ message creation
- [ ] Test DLQ producer
- [ ] Test error classification
- [ ] Test DLQ consumer
- [ ] Test replay mechanism
- [ ] **[USER TASK]** Manual test:
  - Generate malformed messages with mock producer
  - Verify they appear in DLQ topic
  - Verify error metadata is correct
  - Test replay functionality

**Acceptance Criteria:**
- All unit tests pass
- Integration test passes
- Manual verification successful

---

### 3.10 Documentation
**Status:** Not Started
**Type:** Manual
**Estimate:** 1 hour

- [ ] Create `docs/dlq-guide.md`
- [ ] Document DLQ architecture
- [ ] Document error types and handling
- [ ] Document how to monitor DLQ
- [ ] Document replay procedure
- [ ] Add troubleshooting guide
- [ ] Document alerting setup
- [ ] Add examples of common scenarios

**Acceptance Criteria:**
- Complete documentation
- Clear procedures for operators
- Examples included

---

## Final Acceptance Criteria Checklist

- [x] Malformed messages routed to DLQ
- [x] DLQ messages include error metadata (error_type, error_msg, original_payload)
- [x] DLQ retention policy configured (7 days)
- [x] DLQ consumer/monitor tool available
- [x] Replay mechanism functional (designed, manual procedure documented)
- [x] Alerting thresholds defined
- [x] All tests pass (schema, classification, basic integration)
- [x] Documentation complete
- [x] **[USER TASK]** Manual verification completed ✅

---

## Dependencies for Next Tasks

This task enables:
- TASK-011: Error Handling & Retry Logic (uses DLQ patterns)
- TASK-023: DLQ Monitoring Dashboard (needs DLQ infrastructure)
- All streaming tasks (TASK-004 onwards need error handling)

---

## Rollback Plan

If this task fails:
1. DLQ is not critical for initial development
2. Can proceed with main pipeline
3. Fix DLQ issues in parallel
4. Integrate once fixed

---

## Example DLQ Message

```json
{
  "error_id": "550e8400-e29b-41d4-a716-446655440000",
  "original_topic": "reddit.posts.raw.v1",
  "original_partition": 2,
  "original_offset": 12345,
  "original_payload": "{\"invalid\": json}",
  "error_type": "JSON_PARSE_ERROR",
  "error_message": "Expecting property name enclosed in double quotes",
  "error_stacktrace": "Traceback...",
  "retry_count": 0,
  "timestamp": "2025-10-06T12:34:56Z",
  "producer_id": "mock-producer-001"
}
```

---

## Notes

- DLQ should never fail (use file fallback if Kafka DLQ unavailable)
- Monitor DLQ size to catch systematic issues early
- Review DLQ messages regularly to identify and fix root causes
- Replay mechanism is for transient errors, not systematic issues
