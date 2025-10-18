# Implementation Guide

## Quick Start

All Phase 1 tasks have been broken down into detailed, actionable subtasks. You're now ready to start implementation!

---

## How to Use This Guide

### 1. Start with Foundation Tasks (Week 1)

Follow tasks in order for Phase 1:

#### Must Complete First:

- **TASK-001**: Kafka Cluster Setup (10 subtasks, 3 user tasks)
- **TASK-006**: Cassandra Schema Design & Setup (17 subtasks, 2 user tasks)

These have no dependencies and can be done in parallel.

#### Then Complete:

- **TASK-002**: Mock Data Producer (15 subtasks, 1 user task) - _Needs TASK-001_
- **TASK-003**: Dead Letter Queue Configuration (10 subtasks, 1 user task) - _Needs TASK-001_
- **TASK-004**: Spark Structured Streaming Skeleton (20 subtasks, 1 user task) - _Needs TASK-001_

#### Finally:

- **TASK-005**: Model Inference Stub (19 subtasks, 1 user task) - _Needs TASK-004_
- **TASK-007**: Grafana Dashboard Prototype (19 subtasks, **19 user tasks**) - _Needs TASK-006_
- **TASK-008**: Airflow Environment Setup (20 subtasks, 9 user tasks) - _Independent_

---

## Detailed Task Files

All detailed breakdowns are in `tasks/detailed/`:

- `task001.md` - Kafka Cluster Setup
- `task002.md` - Mock Data Producer
- `task003.md` - Dead Letter Queue Configuration
- `task004.md` - Spark Structured Streaming Skeleton
- `task005.md` - Model Inference Stub
- `task006.md` - Cassandra Schema Design & Setup
- `task007.md` - Grafana Dashboard Prototype
- `task008.md` - Airflow Dashboard Prototype

---

## Understanding Task Files

Each task file contains:

### Structure

- **Overview**: What the task accomplishes
- **Subtasks**: Numbered steps (15min - 2hr each)
- **Acceptance Criteria**: How to verify completion
- **Dependencies**: What must be done first
- **Rollback Plan**: What to do if it fails
- **Notes**: Additional context and tips

### Subtask Format

```markdown
### X.Y Subtask Name

**Status:** Not Started
**Type:** Automated / Manual / Automated + Manual
**Estimate:** Time estimate

- [ ] Action item 1
- [ ] Action item 2
- [ ] **[USER TASK]** Manual verification step, it must be verified/confirmed by user before continue, instruct the user how to verify and wait until it is verified

**Acceptance Criteria:**

- Clear success criteria
```

---

## User Tasks

Tasks marked with **[USER TASK]** require manual action:

- ✅ Manual verification in UIs
- ✅ Visual inspection
- ✅ Configuration decisions
- ✅ Approval/review gates

**Important:** User tasks cannot be skipped - they ensure quality!

---

## Progress Tracking

### As You Work:

1. **Open the task file** (e.g., `task001.md`)
2. **Check off subtasks** as you complete them
3. **Complete all acceptance criteria**
4. **Test thoroughly** before marking task done
5. **Update README.md** status when task complete

### Example:

```markdown
- [x] Create docker-compose.yml file ✅ DONE
- [x] Define Zookeeper service ✅ DONE
- [ ] Define Kafka broker service ⬅️ WORKING HERE
```

---

## Phase 1 Summary

### Total Breakdown

| Metric             | Count                           |
| ------------------ | ------------------------------- |
| **Major Tasks**    | 8                               |
| **Total Subtasks** | 130                             |
| **User Tasks**     | 38                              |
| **Estimated Time** | ~10 days (with parallelization) |

### By Task

| Task     | Subtasks | User Tasks | Estimated Time |
| -------- | -------- | ---------- | -------------- |
| TASK-001 | 10       | 3          | 2 days         |
| TASK-002 | 15       | 1          | 1 day          |
| TASK-003 | 10       | 1          | 0.5 days       |
| TASK-004 | 20       | 1          | 2 days         |
| TASK-005 | 19       | 1          | 1 day          |
| TASK-006 | 17       | 2          | 2 days         |
| TASK-007 | 19       | 19         | 1 day          |
| TASK-008 | 20       | 9          | 1 day          |

---

## Recommended Implementation Order

### Option 1: Sequential (Safer, Takes Longer)

```
Day 1-2:   TASK-001 (Kafka)
Day 3-4:   TASK-006 (Cassandra)
Day 5:     TASK-002 (Mock Producer) + TASK-003 (DLQ)
Day 6-7:   TASK-004 (Spark Streaming)
Day 8:     TASK-005 (Model Stub) + TASK-008 (Airflow)
Day 9:     TASK-007 (Grafana)
Day 10:    Testing & Integration
```

### Option 2: Parallel (Faster, Needs Multiple People)

```
Week 1:
  Data Engineer:     TASK-001 → TASK-002 → TASK-003
  ML Engineer:       TASK-004 → TASK-005
  DataOps Engineer:  TASK-006 → TASK-007 → TASK-008

Week 2:
  Integration and testing
```

---

## Tools & Resources

### You'll Need:

- ✅ Docker & Docker Compose
- ✅ Python 3.9+
- ✅ Text editor / IDE
- ✅ Web browser (for UIs)
- ✅ 8GB+ RAM (for running all services)
- ✅ 20GB+ disk space

### Services Ports:

- Kafka: `localhost:9092`
- Kafka UI: `http://localhost:8080`
- Cassandra: `localhost:9042`
- Spark Master UI: `http://localhost:8081`
- Grafana: `http://localhost:3000` (admin/admin)
- Airflow: `http://localhost:8082` (airflow/airflow)

---

## Testing Strategy

### After Each Task:

1. ✅ Run unit tests (if applicable)
2. ✅ Run integration tests
3. ✅ Manual verification via UI
4. ✅ Check logs for errors
5. ✅ Verify acceptance criteria met

### Before Moving to Next Task:

1. ✅ All subtasks checked off
2. ✅ All tests passing
3. ✅ Documentation updated
4. ✅ No errors in logs
5. ✅ Ready for next dependency

---

## Common Issues & Solutions

### Docker Issues

```bash
# If containers won't start
docker-compose down -v
docker-compose up -d

# If ports are in use
lsof -i :9092  # Find process using port
kill -9 <PID>  # Kill process
```

### Out of Memory

```bash
# Check Docker memory allocation
docker stats

# Increase Docker Desktop memory (Settings → Resources)
# Recommended: 8GB minimum
```

### Slow Performance

- Reduce Spark worker memory
- Reduce Kafka retention
- Limit mock producer rate
- Use smaller test datasets

---

## Getting Help

### If You Get Stuck:

1. **Check the task's Rollback Plan** section
2. **Check the task's Notes** section
3. **Review the PRD** (`docs/prd.md`) for requirements
4. **Check component logs**:
   ```bash
   docker logs reddit-kafka
   docker logs reddit-spark-master
   docker logs reddit-cassandra
   ```
5. **Review parent task** in `tasks/entry.md`

---

## After Phase 1

Once all Phase 1 tasks are complete:

1. ✅ All services running
2. ✅ Mock data flowing end-to-end
3. ✅ Dashboards showing data
4. ✅ Airflow scheduling DAGs

### Then move to:

- **Phase 2**: Real Data Flow (TASK-009 to TASK-018)
- **Phase 3 & 4**: Model Integration, Optimization & QA (TASK-019 to TASK-045)

Detailed breakdowns for Phase 2+ are ready — see sections below.

---

## Phase 2: Real Data Flow (Week 2)

### Overview

Move from mock to real Reddit data, integrate Spark with Cassandra, validate end-to-end flow, and light up dashboards with live data.

### Detailed Task Files

- `tasks/detailed/task009.md` — Reddit API Integration (PRAW)
- `tasks/detailed/task010.md` — Historical Backfill (PSAW)
- `tasks/detailed/task011.md` — Error Handling & Retry Logic
- `tasks/detailed/task012.md` — Spark-Cassandra Integration
- `tasks/detailed/task013.md` — Text Cleaning Pipeline
- `tasks/detailed/task014.md` — End-to-End Data Flow Test
- `tasks/detailed/task015.md` — Grafana Live Data Connection
- `tasks/detailed/task016.md` — Build Additional Dashboards
- `tasks/detailed/task017.md` — Configure Dashboard Refresh Intervals
- `tasks/detailed/task018.md` — Dataset Collection & Labeling

### Recommended Order

1. TASK-009 → TASK-011 (stabilize producer with retries)
2. TASK-010 (historical backfill after live producer works)
3. TASK-012 → TASK-013 (Spark writes + text cleaning)
4. TASK-014 (end-to-end validation at scale)
5. TASK-015 → TASK-016 → TASK-017 (dashboards on real data)
6. TASK-018 (curate labeled dataset for modeling)

### Phase 2 is Complete When:

- [ ] Live Reddit producer streams reliably to Kafka
- [ ] Historical backfill completes with deduping and checkpoints
- [ ] Spark writes to Cassandra with acceptable write latency
- [ ] Text cleaning pipeline handles edge cases with tests
- [ ] End-to-end (Kafka → Spark → Cassandra) passes at 10k+ messages
- [ ] Grafana shows live production data with <5s query times
- [ ] Dashboard auto-refresh tuned and stable
- [ ] Initial labeled dataset (10k+) versioned and ready

---

## Phase 3 & 4: Model Integration + Optimization & QA

### Overview

Integrate the trained model, productionize the ML lifecycle, harden performance and reliability, and complete QA/UAT.

### One Comprehensive Guide

All remaining tasks (TASK-019 through TASK-045) are combined in:

- `tasks/detailed/task019.md` — Comprehensive guide covering:
  - Model training, selection, fine-tuning, and deployment
  - Airflow DAGs for training, registry, recomputes, and data quality
  - Monitoring and alerts across Kafka, Spark, Cassandra, and producers
  - Load/performance testing and resource tuning
  - Security hardening and documentation
  - QA and UAT, plus post-launch optimization

### Suggested Flow

- Replace model stub with trained model (TASK-020) and add versioning/registry (TASK-021)
- Add training/registration DAGs (TASK-022) and operational dashboards/alerts (TASK-023–TASK-026)
- Continue with operational DAGs, optimizations, monitoring, and quality gates per `task019.md`

### Phase 3/4 Are Complete When:

- [ ] Real model inference in Spark meets latency/quality targets
- [ ] Model versions tracked with rollback path
- [ ] Automated training/registration pipeline runs successfully
- [ ] System-level monitoring and alerting in place and tested
- [ ] Performance SLAs met under load and tuned
- [ ] QA test plan and UAT passed; docs updated

## Success Criteria

### Phase 1 is Complete When:

- [ ] All services running without errors
- [ ] Kafka topics created and accessible
- [ ] Mock producer generating data
- [ ] Spark consuming and processing data
- [ ] Data stored in Cassandra
- [ ] Grafana displaying dashboards
- [ ] Airflow running sample DAGs
- [ ] All tests passing
- [ ] Documentation complete
- [ ] Team can demo the system

---

## Let's Build! 🚀

You now have:

- ✅ 8 detailed task breakdowns
- ✅ 130 actionable subtasks
- ✅ Clear acceptance criteria
- ✅ Rollback plans
- ✅ Testing strategies

**Start with TASK-001 or TASK-006 and follow the subtasks step-by-step!**

Good luck! 🎯
