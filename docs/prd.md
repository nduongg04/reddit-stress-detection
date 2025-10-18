# Product Requirements Document

## Real-Time Reddit Stress Post Detection System

## Executive Summary

### Objective

Build an end-to-end real-time big data pipeline that detects and classifies stress-related Reddit posts using natural language processing and streaming technologies. The system will continuously collect Reddit posts, analyze content for signs of stress (anxiety, burnout, depression), and visualize stress trends across subreddits on a live Grafana dashboard.

### Key Benefits

- **Real-time insights** into mental health discussions on social media
- **Automated detection** eliminating manual data scraping
- **Scalable architecture** handling 1,000+ posts per minute
- **Actionable visualizations** for researchers and analysts

---

## Problem Statement

Mental health discussions on social media platforms provide early signals of societal stress trends. However, current approaches face significant challenges:

- **Volume:** Reddit's massive data volume makes real-time monitoring difficult
- **Automation:** No automated system exists for detecting stress in live posts
- **Manual processes:** Analysts rely on time-consuming manual data scraping and post-analysis
- **Scalability:** Existing tools cannot handle streaming data at scale

This project addresses these gaps with an automated, scalable, real-time pipeline for stress detection and visualization.

---

## Goals & Success Metrics

### Primary Goals

- 🧩 Detect stress-related posts from Reddit in real time
- ⚡ Process data efficiently with streaming & distributed computation
- 📊 Store and visualize trends in an accessible dashboard
- 🤖 Continuously improve detection via retraining and monitoring

### Success Metrics

| Metric                      | Target                            | Priority |
| --------------------------- | --------------------------------- | -------- |
| End-to-end latency          | ≤ 60 seconds (Reddit → Dashboard) | High     |
| Throughput                  | ≥ 1,000 posts/minute              | High     |
| Model Recall (Stress class) | ≥ 0.85                            | High     |
| Pipeline Uptime             | ≥ 99%                             | High     |
| Data Quality                | < 1% missing/invalid records      | Medium   |
| Dashboard Refresh Interval  | 30–60 seconds                     | Medium   |

---

## Product Scope

### In Scope

- Reddit ingestion via PRAW (real-time) and PSAW (historical backfill)
- Real-time message streaming using Apache Kafka
- Stream processing and classification with Spark Structured Streaming
- NLP-based stress detection using Hugging Face Transformer models (via PySpark PandasUDF)
- Scalable, query-optimized storage using Apache Cassandra
- Real-time visualization with Grafana dashboards
- Workflow orchestration and monitoring via Apache Airflow

### Out of Scope

- Individual mental health interventions or direct notifications to Reddit users
- Integration with external social media APIs (Twitter, Discord, etc.)
- Deep contextual psychology interpretation or clinical diagnosis
- User authentication or personalized dashboards (Phase 1)

---

## System Architecture

### High-Level Data Flow

```
Reddit API → Kafka → Spark Streaming + HF Model → Cassandra → Grafana
                             ↑
                          Airflow (Orchestration)
```

### Technology Stack

| Layer             | Technology                 | Function                              |
| ----------------- | -------------------------- | ------------------------------------- |
| **Data Source**   | Reddit API (PRAW/PSAW)     | Collect Reddit posts and comments     |
| **Ingestion**     | Apache Kafka               | Queue posts for streaming pipeline    |
| **Processing**    | Spark Structured Streaming | Clean, classify, and aggregate data   |
| **ML Model**      | HuggingFace + PySpark UDF  | NLP stress classification             |
| **Storage**       | Apache Cassandra           | Persist raw and processed posts       |
| **Visualization** | Grafana                    | Display live metrics and trends       |
| **Orchestration** | Apache Airflow             | Schedule, monitor, and retrain models |

### Architecture Diagram Components

- **Data Ingestion Layer:** PRAW/PSAW producers → Kafka topics
- **Stream Processing Layer:** Spark Structured Streaming jobs
- **ML Inference Layer:** Hugging Face model (DistilBERT/RoBERTa) via Pandas UDF
- **Storage Layer:** Cassandra tables (raw, classified, aggregated)
- **Presentation Layer:** Grafana dashboards with alerting
- **Orchestration Layer:** Airflow DAGs for scheduling and monitoring

---

## Functional Requirements

### 5.1 Data Ingestion

**Owner:** Data Engineer

#### Requirements

- Use PRAW to stream submissions and comments in real time from target subreddits
- Use PSAW for historical backfills (last 3–6 months of data)
- Publish JSON records to Kafka topic `reddit.posts.raw.v1`
- Handle rate limits with exponential backoff and retry logic
- Route malformed data to dead letter queue `reddit.posts.dlq.v1`

#### Data Schema

Required metadata fields:

```
- post_id (string, unique identifier)
- kind (enum: submission/comment)
- subreddit (string)
- title (string, nullable for comments)
- body (string)
- created_utc (timestamp)
- author_hash (string, anonymized)
- permalink (string)
- ingest_ts (timestamp)
- source (enum: praw/psaw)
```

#### Acceptance Criteria

- ✅ Producer continuously streams data with <1% failure rate
- ✅ Rate limiting handled gracefully without data loss
- ✅ DLQ captures malformed records with error metadata

---

### 5.2 Stream Processing

**Owner:** ML Engineer

#### Requirements

- Spark Structured Streaming job consumes from `reddit.posts.raw.v1`
- Parse JSON and validate schema
- Deduplicate based on `post_id` with 24-hour watermark
- Clean text data:
  - Remove URLs, emojis, and markdown formatting
  - Normalize whitespace
  - Handle Unicode characters
- Apply Hugging Face model via Pandas UDF:
  - **Input:** Cleaned text
  - **Output:** `stress_label` (binary), `stress_score` (0-1), `model_version`
- Write enriched records to Cassandra table `classified_posts_by_hour`

#### Aggregation Requirements

Generate hourly statistics:

- `total_cnt`: Total posts processed
- `stress_cnt`: Number of stress-labeled posts
- `avg_score`: Average stress confidence score
- `pct_stress`: Percentage of posts classified as stress

Write aggregations to:

- `agg_subreddit_hour`: Aggregates by subreddit
- `agg_global_hour`: Platform-wide aggregates

#### Acceptance Criteria

- ✅ Streaming job processes data with <60s latency
- ✅ Deduplication rate >99.9%
- ✅ Text cleaning handles edge cases (emojis, URLs, code blocks)
- ✅ Model inference completes within batch processing window

---

### 5.3 Machine Learning Model

**Owner:** ML Engineer

#### Model Requirements

- Fine-tune small Transformer model (DistilBERT or RoBERTa)
- Train on labeled Reddit dataset (stress vs non-stress posts)
- Binary classification with confidence scores
- Model size optimized for real-time inference (<500MB)

#### Training Dataset

- Minimum 10,000 labeled examples
- Balanced class distribution (50/50 stress/non-stress)
- Includes diverse subreddit sources
- Quality validation and inter-annotator agreement >0.8

#### Evaluation Metrics

- **Accuracy:** ≥0.80
- **Precision:** ≥0.82
- **Recall:** ≥0.85 (prioritize catching stress posts)
- **F1 Score:** ≥0.83

#### Model Management

- Model artifacts stored under `/artifacts/model_vX/`
- Version tracking with metadata (training date, metrics, dataset version)
- Retrain weekly via Airflow DAG `model_train_register`
- A/B testing capability for model comparison

#### Acceptance Criteria

- ✅ Model meets minimum recall threshold
- ✅ Inference latency <100ms per post
- ✅ Model versioning and rollback capability implemented

---

### 5.4 Storage

**Owner:** DataOps Engineer

#### Cassandra Schema

**Keyspace:** `reddit_rt`

- Replication Factor: 3
- Replication Strategy: NetworkTopologyStrategy

#### Tables

**1. raw_posts_by_day**

```
PRIMARY KEY ((date_partition), ingest_ts, post_id)
- Stores raw ingested posts
- TTL: 14 days
```

**2. classified_posts_by_hour**

```
PRIMARY KEY ((subreddit, hour_partition), created_utc, post_id)
- Stores classified posts with stress labels
- TTL: 90 days
```

**3. agg_subreddit_hour**

```
PRIMARY KEY ((subreddit, hour_partition))
- Hourly aggregates by subreddit
- TTL: 180 days
```

**4. agg_global_hour**

```
PRIMARY KEY (hour_partition)
- Platform-wide hourly aggregates
- TTL: 180 days
```

#### Configuration

- Compaction Strategy: TimeWindowCompactionStrategy
- Compression: LZ4
- Read Repair: 0.1
- Speculative Retry: 99percentile

#### Acceptance Criteria

- ✅ Write latency <50ms (p99)
- ✅ Read latency <10ms (p99)
- ✅ TTL enforcement verified
- ✅ Compaction strategy optimized for time-series data

---

### 5.5 Visualization

**Owner:** DataOps Engineer

#### Grafana Dashboards

**Dashboard 1: Real-Time Stress Overview**

- Global stress percentage trend (line chart)
- Total posts processed (counter)
- Average stress score (gauge)
- Top 10 subreddits by stress percentage (bar chart)

**Dashboard 2: Subreddit Analysis**

- Subreddit comparison (multi-line chart)
- Hourly post volume by subreddit
- Stress distribution histogram
- Time-based filters (1h, 6h, 24h, 7d)

**Dashboard 3: System Health**

- Kafka consumer lag
- Spark batch processing time
- Cassandra write/read latency
- Model inference latency
- Pipeline uptime percentage

#### Alerting Rules

- **No Data Alert:** Trigger if no data received for >5 minutes
- **Stress Spike Alert:** Trigger if stress % deviates >2σ from baseline
- **Pipeline Lag Alert:** Trigger if end-to-end latency >120 seconds
- **Error Rate Alert:** Trigger if DLQ rate >5%

#### Alert Channels

- Slack webhook to #data-alerts
- Email to on-call engineer
- PagerDuty integration for critical alerts

#### Acceptance Criteria

- ✅ Dashboards update within 60 seconds
- ✅ All alerts tested and functional
- ✅ Dashboard accessible to stakeholders
- ✅ Mobile-responsive dashboard design

---

### 5.6 Orchestration & Monitoring

**Owner:** DataOps Engineer

#### Airflow DAGs

**1. producer_ctl**

- Start/stop Reddit producers
- Health check every 5 minutes
- Auto-restart on failure

**2. psaw_backfill_daily**

- Nightly historical ingestion
- Catchup for missed data
- Runs at 2:00 AM UTC

**3. model_train_register**

- Weekly model retraining pipeline
- Data extraction → training → evaluation → registration
- Runs Sunday at 3:00 AM UTC

**4. agg_recompute_daily**

- Consistency backfill for aggregations
- Reconciliation checks
- Runs daily at 1:00 AM UTC

**5. data_quality_checks**

- Validate record counts, null rates, schema drift
- Runs hourly
- Alerts on quality threshold violations

#### Monitoring Requirements

- Prometheus exporters for Kafka, Spark, Cassandra metrics
- Custom metrics for pipeline-specific KPIs
- Log aggregation via ELK stack or CloudWatch
- Distributed tracing for end-to-end latency analysis

#### Acceptance Criteria

- ✅ All DAGs scheduled and tested
- ✅ Failure notifications working
- ✅ Monitoring dashboards populated
- ✅ Runbooks documented for common failures

---

## Non-Functional Requirements

### Performance

- **Scalability:** Support >5,000 posts/minute with horizontal scaling of Kafka and Spark clusters
- **Latency:** End-to-end latency ≤60 seconds (p95)
- **Throughput:** Process minimum 1,000 posts/minute continuously

### Reliability

- **Fault Tolerance:** At-least-once delivery via Kafka offsets and Spark checkpointing
- **Resilience:** Auto-restart jobs on failure; Airflow retries with exponential backoff
- **Uptime:** ≥99% pipeline availability

### Security

- **Encryption:** TLS 1.3 between all service communications
- **Secrets Management:** Store Reddit API credentials and database passwords in HashiCorp Vault or AWS Secrets Manager
- **Data Anonymization:** Hash author usernames; no personally identifiable information stored
- **Access Control:** Role-based access control (RBAC) for Grafana dashboards

### Compliance & Ethics

- **Privacy:** Anonymize all user identifiers; comply with Reddit API Terms of Service
- **Ethics:** No personal data stored or visualized; aggregate metrics only
- **Transparency:** Document data retention policies and model limitations

### Observability

- **Metrics:** Prometheus exporters for all infrastructure components
- **Logging:** Centralized logging with structured JSON logs
- **Tracing:** Distributed tracing for debugging latency issues
- **Alerting:** Multi-channel alerting (Slack, email, PagerDuty)

### Maintainability

- **Documentation:** Comprehensive runbooks and architecture diagrams
- **Code Quality:** Automated testing (unit, integration, end-to-end)
- **Version Control:** All code in Git with CI/CD pipelines
- **Reproducibility:** Infrastructure-as-Code (Terraform/CloudFormation)

---

## User Stories

### Data Engineer

**Story 1:** As a data engineer, I want to stream Reddit posts in real time so that the pipeline has fresh data continuously.

**Acceptance Criteria:**

- Kafka topics receive data continuously with <1% failure rate
- Dead letter queue (DLQ) handles <1% of messages
- Producer health dashboard shows green status

---

**Story 2:** As a data engineer, I want to monitor producer health so that I can quickly identify and resolve ingestion issues.

**Acceptance Criteria:**

- Grafana dashboard displays producer metrics (messages/sec, errors, lag)
- Alerts trigger when producer stops or error rate exceeds threshold
- Logs are searchable and correlate with metrics

---

### ML Engineer

**Story 3:** As an ML engineer, I want to classify each post's stress level using a fine-tuned model so that we can identify concerning content.

**Acceptance Criteria:**

- Stress labels and confidence scores written to Cassandra within ≤60s of ingestion
- Model recall ≥0.85 on validation dataset
- Model version tracked in each classified record

---

**Story 4:** As an ML engineer, I want to retrain models weekly so that detection accuracy remains high as language evolves.

**Acceptance Criteria:**

- Airflow DAG successfully trains, evaluates, and registers new model
- Model performance metrics tracked over time
- Rollback mechanism available if new model underperforms

---

### DataOps Engineer

**Story 5:** As a DataOps engineer, I want to monitor live dashboards showing stress trends so that stakeholders have access to real-time insights.

**Acceptance Criteria:**

- Grafana dashboards update within <60 seconds
- Alerts trigger when data pipeline stops or anomalies detected
- Dashboard accessible to authorized users with proper authentication

---

**Story 6:** As a DataOps engineer, I want automated data quality checks so that I can trust the accuracy of visualizations.

**Acceptance Criteria:**

- Hourly data quality DAG validates record counts, null rates, and schema compliance
- Alerts sent to Slack when quality thresholds violated
- Quality metrics tracked over time in dashboard

---

### Analyst / Viewer

**Story 7:** As an analyst, I want to view stress trends by subreddit or time range so that I can identify patterns and anomalies.

**Acceptance Criteria:**

- Grafana dashboards display accurate, current metrics
- Time range filters work correctly (1h, 6h, 24h, 7d, 30d)
- Subreddit comparison charts update dynamically

---

**Story 8:** As an analyst, I want to export dashboard data so that I can perform deeper analysis offline.

**Acceptance Criteria:**

- Export functionality available for CSV download
- Exported data includes all visible metrics and time ranges
- Export completes within 30 seconds for typical queries

---

## Implementation Timeline

### Week 1: Foundation

| Team Member              | Tasks                                                                                                        |
| ------------------------ | ------------------------------------------------------------------------------------------------------------ |
| **Data Engineer**        | - Set up Kafka cluster and topics<br>- Build mock producer for testing<br>- Configure DLQ                    |
| **ML/Spark Engineer**    | - Set up Spark Structured Streaming skeleton<br>- Create model inference stub<br>- Test PandasUDF pattern    |
| **DataOps/Viz Engineer** | - Design and implement Cassandra schema<br>- Create sample Grafana dashboard<br>- Set up Airflow environment |

### Week 2: Real Data Flow

| Team Member              | Tasks                                                                                                         |
| ------------------------ | ------------------------------------------------------------------------------------------------------------- |
| **Data Engineer**        | - Integrate Reddit API (PRAW)<br>- Implement PSAW for historical backfill<br>- Add error handling and retries |
| **ML/Spark Engineer**    | - Connect Spark to Cassandra<br>- Implement text cleaning pipeline<br>- Test end-to-end data flow             |
| **DataOps/Viz Engineer** | - Connect Grafana to Cassandra<br>- Build live data dashboards<br>- Configure refresh intervals               |

### Week 3: Model Integration

| Team Member              | Tasks                                                                                               |
| ------------------------ | --------------------------------------------------------------------------------------------------- |
| **Data Engineer**        | - Implement DLQ monitoring<br>- Add producer metrics<br>- Optimize Kafka configuration              |
| **ML/Spark Engineer**    | - Integrate Hugging Face model<br>- Build model training DAG<br>- Implement versioning and registry |
| **DataOps/Viz Engineer** | - Configure alerting rules<br>- Build additional Airflow DAGs<br>- Set up Slack integration         |

### Week 4: Optimization & QA

| Team Member              | Tasks                                                                                                  |
| ------------------------ | ------------------------------------------------------------------------------------------------------ |
| **Data Engineer**        | - Stress test pipeline (>5k posts/min)<br>- Document architecture and runbooks<br>- Security hardening |
| **ML/Spark Engineer**    | - Implement drift detection<br>- Optimize batch sizes and parallelism<br>- Performance tuning          |
| **DataOps/Viz Engineer** | - Set up comprehensive monitoring<br>- Final QA testing<br>- User acceptance testing                   |

---

## Risks & Mitigation

| Risk                                 | Impact                 | Likelihood | Mitigation Strategy                                                                                          |
| ------------------------------------ | ---------------------- | ---------- | ------------------------------------------------------------------------------------------------------------ |
| **Reddit API rate limits**           | Data ingestion delays  | High       | - Use stream endpoints with proper throttling<br>- Implement exponential backoff<br>- Use PSAW for backfills |
| **Model inference latency too high** | Pipeline slowdown      | Medium     | - Optimize batch sizes<br>- Use smaller model (DistilBERT)<br>- Implement GPU acceleration if needed         |
| **Kafka or Spark crash**             | Data loss risk         | Medium     | - Enable Spark checkpointing<br>- Configure Kafka replication<br>- Implement DLQ replay mechanism            |
| **Vocabulary drift**                 | Reduced model accuracy | High       | - Weekly model retraining<br>- Data drift detection DAG<br>- Monitor model performance metrics               |
| **Cassandra write overload**         | Storage bottleneck     | Low        | - Apply write batching<br>- Optimize partition keys<br>- Horizontal scaling                                  |
| **Cost overruns**                    | Budget constraints     | Medium     | - Monitor cloud resource usage<br>- Implement auto-scaling policies<br>- Optimize retention policies         |
| **Data quality issues**              | Incorrect insights     | Medium     | - Hourly data quality checks<br>- Schema validation<br>- Anomaly detection alerts                            |

---

## Deliverables

### Core Infrastructure

- ✅ Kafka producer service (Reddit → Kafka)
- ✅ Spark streaming pipeline (Kafka → Cassandra)
- ✅ Cassandra database schema and configuration

### Machine Learning

- ✅ Hugging Face stress classifier model (trained and evaluated)
- ✅ Model training and evaluation pipeline
- ✅ Model registry and versioning system

### Visualization & Monitoring

- ✅ Grafana dashboards (3 dashboards: Overview, Subreddit Analysis, System Health)
- ✅ Alerting rules and notification channels

### Orchestration

- ✅ Airflow DAGs (5 DAGs: producer control, backfill, training, aggregation, quality checks)
- ✅ Monitoring and logging infrastructure

### Documentation

- ✅ Architecture documentation with diagrams
- ✅ Runbooks for common operational tasks
- ✅ Setup and deployment guides
- ✅ Troubleshooting guide
- ✅ API documentation for internal services

---

## Future Roadmap

### Phase 2: Enhanced Detection (Q1 2026)

- Multi-language stress detection (Vietnamese, Japanese, Spanish)
- Subreddit-specific sentiment calibration
- Topic clustering (anxiety, burnout, relationships, work stress)

### Phase 3: Advanced Analytics (Q2 2026)

- Predictive analytics for stress trend forecasting
- Correlation analysis with external events (news, holidays)
- Anomaly detection using time-series algorithms

### Phase 4: Integration & Automation (Q3 2026)

- Integration with Prometheus alert manager
- Slack bot for interactive queries
- Auto model retraining based on drift threshold
- Self-healing pipeline capabilities

### Phase 5: Scale & Expand (Q4 2026)

- Multi-platform support (Twitter, Discord)
- Real-time recommendations for mental health resources
- Research API for academic partnerships
- Mobile app for dashboard access

---

## Appendix

### Glossary

- **PRAW:** Python Reddit API Wrapper for real-time streaming
- **PSAW:** Python Pushshift API Wrapper for historical data
- **DLQ:** Dead Letter Queue for handling failed messages
- **TTL:** Time To Live for automatic data expiration
- **UDF:** User Defined Function for custom Spark transformations
- **RF:** Replication Factor in Cassandra

### References

- Reddit API Documentation: https://www.reddit.com/dev/api
- Apache Kafka Documentation: https://kafka.apache.org/documentation/
- Spark Structured Streaming Guide: https://spark.apache.org/docs/latest/structured-streaming-programming-guide.html
- Hugging Face Transformers: https://huggingface.co/docs/transformers/
