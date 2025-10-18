# TASK-016: Build Additional Dashboards

**Owner:** DataOps/Viz Engineer
**Priority:** Medium
**Dependencies:** TASK-015 (Grafana Live Data Connection)
**Estimate:** 2 days

---

## Overview

Create two additional Grafana dashboards to provide comprehensive monitoring and analysis capabilities: **Subreddit Analysis Dashboard** for content insights and **System Health Dashboard** for infrastructure monitoring.

---

## Subtasks

### Subtask 016.1: Dashboard Planning and Design

**Estimate:** 1 hour

**Description:**
- Design dashboard layouts and panel arrangements
- Define metrics and queries needed for each panel
- Create wireframes for both dashboards
- **[USER TASK]** Review and approve dashboard designs

**Acceptance Criteria:**
- Dashboard layouts designed
- Metrics list finalized
- Wireframes documented

**Design Document:**
```markdown
## Dashboard 2: Subreddit Analysis

Layout (3 rows):
Row 1: Subreddit Selector + Time Range
Row 2: Multi-line chart (stress % over time by subreddit)
Row 3: Post volume bar chart + Stress distribution histogram

## Dashboard 3: System Health

Layout (4 rows):
Row 1: Pipeline Status Overview (4 stat panels)
Row 2: Kafka metrics (lag, throughput)
Row 3: Spark metrics (batch time, processing rate)
Row 4: Cassandra metrics (latency, operations/sec)
```

---

### Subtask 016.2: Create Subreddit Analysis Dashboard

**Estimate:** 30 minutes

**Description:**
- Create new dashboard in Grafana
- Configure dashboard settings
- Set up dashboard variables
- **[USER TASK]** Create dashboard via Grafana UI

**Acceptance Criteria:**
- Dashboard created with proper name
- Variables configured
- Settings applied

**Steps:**
1. Navigate to Grafana UI → Dashboards → New Dashboard
2. Name: "Subreddit Analysis"
3. Add dashboard description
4. Configure time range picker

**Dashboard Settings:**
```json
{
  "title": "Subreddit Analysis",
  "tags": ["reddit", "analysis", "subreddit"],
  "timezone": "utc",
  "refresh": "1m",
  "time": {
    "from": "now-24h",
    "to": "now"
  }
}
```

---

### Subtask 016.3: Subreddit Variable Setup

**Estimate:** 30 minutes

**Description:**
- Create dashboard variable for subreddit selection
- Enable multi-select functionality
- Set default values
- **[USER TASK]** Configure variable in Grafana UI

**Acceptance Criteria:**
- Subreddit variable works
- Multi-select enabled
- Default selection set

**Variable Configuration:**
```
Name: subreddit
Type: Custom
Values: anxiety,depression,stress,mentalhealth
Multi-value: Enabled
Include All option: Enabled
Default: All
```

**CQL Query Alternative (if using query):**
```sql
SELECT DISTINCT subreddit FROM reddit_rt.classified_posts_by_hour;
```

---

### Subtask 016.4: Stress Percentage Timeline Panel

**Estimate:** 1 hour

**Description:**
- Create multi-line chart showing stress % over time by subreddit
- Configure legend and tooltips
- Add threshold markers
- **[USER TASK]** Create and configure panel in Grafana

**Acceptance Criteria:**
- Chart displays stress trends
- One line per subreddit
- Legend shows subreddit names
- Interactive tooltips

**Panel Configuration:**
```
Panel Type: Time series
Title: "Stress Percentage Over Time by Subreddit"
```

**Query:**
```sql
SELECT
  hour_bucket,
  subreddit,
  (stress_count * 100.0 / total_count) as stress_percentage
FROM reddit_rt.agg_subreddit_hour
WHERE subreddit IN ($subreddit)
  AND hour_bucket >= $__timeFrom
  AND hour_bucket <= $__timeTo
ORDER BY hour_bucket ASC
```

**Panel Options:**
- Y-axis: 0-100 (percentage)
- Legend placement: Bottom
- Tooltip mode: All series
- Line width: 2
- Fill opacity: 10

---

### Subtask 016.5: Post Volume Bar Chart Panel

**Estimate:** 45 minutes

**Description:**
- Create bar chart showing hourly post volume by subreddit
- Configure stacking options
- Add color coding
- **[USER TASK]** Create and configure panel

**Acceptance Criteria:**
- Bar chart displays post volumes
- Bars grouped/stacked by subreddit
- Colors distinguish subreddits

**Query:**
```sql
SELECT
  hour_bucket,
  subreddit,
  total_count as post_count
FROM reddit_rt.agg_subreddit_hour
WHERE subreddit IN ($subreddit)
  AND hour_bucket >= $__timeFrom
  AND hour_bucket <= $__timeTo
ORDER BY hour_bucket ASC
```

**Panel Options:**
- Panel Type: Bar chart
- Orientation: Horizontal
- Stacking: Normal
- Show values: On hover

---

### Subtask 016.6: Stress Distribution Histogram Panel

**Estimate:** 1 hour

**Description:**
- Create histogram showing distribution of stress scores
- Configure buckets/bins
- Add statistical overlays (mean, median)
- **[USER TASK]** Create and configure panel

**Acceptance Criteria:**
- Histogram shows stress distribution
- Bins properly configured
- Statistics displayed

**Query (requires aggregation):**
```sql
SELECT
  subreddit,
  stress_count,
  non_stress_count
FROM reddit_rt.agg_subreddit_hour
WHERE subreddit IN ($subreddit)
  AND hour_bucket >= $__timeFrom
  AND hour_bucket <= $__timeTo
```

**Panel Type:** Bar gauge or Histogram
**Calculation:** Client-side transformation to create bins

---

### Subtask 016.7: Time Range Filter Configuration

**Estimate:** 30 minutes

**Description:**
- Add quick time range buttons (1h, 6h, 24h, 7d, 30d)
- Configure custom time range picker
- Test time range filtering
- **[USER TASK]** Configure time picker options

**Acceptance Criteria:**
- Quick range buttons work
- Custom range selection works
- All panels update correctly

**Time Range Configuration:**
```json
{
  "timepicker": {
    "refresh_intervals": ["30s", "1m", "5m", "15m", "30m", "1h"],
    "time_options": ["5m", "15m", "1h", "6h", "12h", "24h", "7d", "30d"]
  }
}
```

---

### Subtask 016.8: Create System Health Dashboard

**Estimate:** 30 minutes

**Description:**
- Create new System Health dashboard
- Set up layout structure
- Configure refresh interval
- **[USER TASK]** Create dashboard via Grafana UI

**Acceptance Criteria:**
- Dashboard created
- Auto-refresh enabled (30s)
- Layout configured

**Dashboard Settings:**
```json
{
  "title": "System Health Monitoring",
  "tags": ["system", "health", "monitoring", "infrastructure"],
  "refresh": "30s",
  "timezone": "utc"
}
```

---

### Subtask 016.9: Pipeline Status Overview Panels

**Estimate:** 1 hour

**Description:**
- Create 4 stat panels showing key metrics:
  - Total posts processed (24h)
  - Current pipeline uptime %
  - Error rate %
  - Average end-to-end latency
- **[USER TASK]** Create stat panels

**Acceptance Criteria:**
- All 4 stat panels created
- Values update in real-time
- Color thresholds configured

**Panel 1: Total Posts (24h)**
```sql
SELECT SUM(total_count) as total_posts
FROM reddit_rt.agg_global_hour
WHERE hour_bucket >= now() - 24h
```

**Panel 2: Uptime %**
```
Source: Prometheus metrics
Query: up{job="reddit-producer"} * 100
```

**Panel 3: Error Rate %**
```sql
SELECT
  (SUM(error_count) * 100.0 / SUM(total_count)) as error_rate
FROM reddit_rt.system_metrics
WHERE hour_bucket >= now() - 1h
```

**Panel 4: Avg Latency**
```sql
SELECT AVG(processing_latency_ms) as avg_latency
FROM reddit_rt.system_metrics
WHERE hour_bucket >= now() - 1h
```

---

### Subtask 016.10: Kafka Metrics Panels

**Estimate:** 1.5 hours

**Description:**
- Create panels for Kafka consumer lag
- Add Kafka throughput metrics
- Configure Prometheus data source for Kafka JMX metrics
- **[USER TASK]** Create and configure Kafka panels

**Acceptance Criteria:**
- Consumer lag displayed
- Throughput chart working
- Alerts configured for high lag

**Consumer Lag Panel:**
```
Data Source: Prometheus
Query: kafka_consumergroup_lag{topic="reddit.posts.raw.v1"}
Panel Type: Time series
Threshold: Warning at 1000, Critical at 5000
```

**Throughput Panel:**
```
Query: rate(kafka_topic_partition_current_offset{topic="reddit.posts.raw.v1"}[5m])
Panel Type: Time series
Unit: messages/sec
```

---

### Subtask 016.11: Spark Metrics Panels

**Estimate:** 1.5 hours

**Description:**
- Create panel for Spark batch processing time
- Add streaming query metrics
- Show records processed per second
- **[USER TASK]** Create and configure Spark panels

**Acceptance Criteria:**
- Batch processing time displayed
- Processing rate visible
- Memory usage tracked

**Batch Processing Time:**
```
Data Source: Prometheus
Query: spark_streaming_batch_duration_milliseconds
Panel Type: Time series
Threshold: Warning at 10000ms, Critical at 30000ms
```

**Processing Rate:**
```
Query: spark_streaming_records_processed_per_second
Panel Type: Gauge
Unit: records/s
```

**Memory Usage:**
```
Query: spark_executor_memory_used_bytes / spark_executor_memory_total_bytes * 100
Panel Type: Gauge
Unit: percent
```

---

### Subtask 016.12: Cassandra Metrics Panels

**Estimate:** 1.5 hours

**Description:**
- Create panels for Cassandra read/write latency
- Add operations per second metrics
- Show disk usage and compaction status
- **[USER TASK]** Create and configure Cassandra panels

**Acceptance Criteria:**
- Read/write latency displayed
- Operations/sec visible
- Disk usage tracked

**Read Latency:**
```
Data Source: Prometheus
Query: cassandra_table_read_latency_seconds{keyspace="reddit_rt"}
Panel Type: Time series
Unit: milliseconds
Threshold: Warning at 50ms, Critical at 100ms
```

**Write Latency:**
```
Query: cassandra_table_write_latency_seconds{keyspace="reddit_rt"}
Panel Type: Time series
Unit: milliseconds
Threshold: Warning at 50ms, Critical at 100ms
```

**Operations/Second:**
```
Query: rate(cassandra_table_operations_total[5m])
Panel Type: Time series
Legend: {{operation_type}}
```

---

### Subtask 016.13: Model Inference Latency Panel

**Estimate:** 45 minutes

**Description:**
- Create panel for ML model inference latency
- Add inference throughput metrics
- Show model version currently deployed
- **[USER TASK]** Create and configure model panels

**Acceptance Criteria:**
- Inference latency displayed
- Current model version shown
- Throughput tracked

**Inference Latency:**
```
Data Source: Prometheus
Query: model_inference_duration_milliseconds
Panel Type: Time series
Threshold: Warning at 100ms, Critical at 200ms
```

**Model Version Stat:**
```
Data Source: Cassandra
Query: SELECT model_version FROM reddit_rt.classified_posts_by_hour
       ORDER BY hour_bucket DESC LIMIT 1
Panel Type: Stat
```

---

### Subtask 016.14: Dashboard Annotations

**Estimate:** 30 minutes

**Description:**
- Add annotations for deployments
- Mark model version changes
- Highlight system incidents
- **[USER TASK]** Configure annotation queries

**Acceptance Criteria:**
- Annotations appear on timelines
- Deployment markers visible
- Incident markers configured

**Annotation Configuration:**
```json
{
  "annotations": {
    "list": [
      {
        "name": "Deployments",
        "datasource": "-- Grafana --",
        "enable": true,
        "iconColor": "green",
        "tags": ["deployment"]
      },
      {
        "name": "Incidents",
        "datasource": "-- Grafana --",
        "enable": true,
        "iconColor": "red",
        "tags": ["incident"]
      }
    ]
  }
}
```

---

### Subtask 016.15: Mobile Responsiveness Testing

**Estimate:** 30 minutes

**Description:**
- Test dashboards on mobile devices
- Adjust panel sizes for mobile view
- Verify readability and usability
- **[USER TASK]** Test on mobile devices

**Acceptance Criteria:**
- Dashboards render correctly on mobile
- All panels readable
- Interactions work on touch devices

**Testing checklist:**
- [ ] iPhone/iOS Safari
- [ ] Android Chrome
- [ ] Tablet (iPad)
- [ ] Portrait and landscape orientations

---

### Subtask 016.16: Dashboard Links and Navigation

**Estimate:** 30 minutes

**Description:**
- Add navigation links between dashboards
- Create dashboard list/home page
- Configure breadcrumbs
- **[USER TASK]** Configure navigation in Grafana UI

**Acceptance Criteria:**
- Navigation links work
- Dashboard list accessible
- Breadcrumbs configured

**Link Configuration:**
Add to each dashboard's settings:
```json
{
  "links": [
    {
      "title": "Main Dashboard",
      "url": "/d/main-dashboard"
    },
    {
      "title": "Subreddit Analysis",
      "url": "/d/subreddit-analysis"
    },
    {
      "title": "System Health",
      "url": "/d/system-health"
    }
  ]
}
```

---

### Subtask 016.17: Export Dashboard JSON

**Estimate:** 15 minutes

**Description:**
- Export dashboard configurations as JSON
- Save to version control
- Document dashboard structure
- **[USER TASK]** Export dashboards via Grafana UI

**Acceptance Criteria:**
- JSON files exported
- Files saved in repository
- Structure documented

**Export Steps:**
1. Navigate to Dashboard Settings → JSON Model
2. Copy JSON
3. Save to `monitoring/grafana/dashboards/`

**Files to create:**
- `monitoring/grafana/dashboards/subreddit-analysis.json`
- `monitoring/grafana/dashboards/system-health.json`

---

### Subtask 016.18: Dashboard Provisioning Configuration

**Estimate:** 1 hour

**Description:**
- Create provisioning configuration files
- Set up automatic dashboard deployment
- Test provisioning in fresh Grafana instance

**Acceptance Criteria:**
- Dashboards auto-provision on startup
- Provisioning tested successfully
- Configuration documented

**Files to Create:**
`monitoring/grafana/provisioning/dashboards/dashboards.yaml`

```yaml
apiVersion: 1

providers:
  - name: 'Reddit Dashboards'
    orgId: 1
    folder: 'Reddit Stress Detection'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
      foldersFromFilesStructure: true
```

**Update docker-compose.yml:**
```yaml
grafana:
  volumes:
    - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
    - ./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro
```

---

### Subtask 016.19: Performance Testing

**Estimate:** 1 hour

**Description:**
- Test dashboard query performance
- Optimize slow queries
- Configure query caching
- **[USER TASK]** Monitor dashboard load times

**Acceptance Criteria:**
- All panels load within 5 seconds
- No query timeouts
- Cache hit rate >50%

**Performance Checklist:**
- [ ] All panels load <5s
- [ ] Time series queries optimized
- [ ] Appropriate aggregation intervals used
- [ ] Query inspector shows no errors
- [ ] Cache configured properly

**Optimization Tips:**
```sql
-- Use appropriate time bucketing
-- Instead of: SELECT * FROM table WHERE hour_bucket > ...
-- Use: SELECT hour_bucket, AVG(value) FROM table
--      WHERE hour_bucket > ...
--      GROUP BY hour_bucket

-- Limit result sets
SELECT * FROM table LIMIT 1000

-- Use time range variables
WHERE hour_bucket >= $__timeFrom AND hour_bucket <= $__timeTo
```

---

### Subtask 016.20: Documentation

**Estimate:** 1 hour

**Description:**
- Document dashboard purpose and usage
- Create dashboard user guide
- Document query explanations

**Acceptance Criteria:**
- Dashboard documentation complete
- User guide created
- Query reference documented

**Files to Create:**
`monitoring/grafana/README.md`

```markdown
# Grafana Dashboards

## Available Dashboards

### 1. Real-Time Stress Overview (Main Dashboard)
- Purpose: Monitor current stress levels across Reddit
- Key Metrics: Stress %, total posts, top subreddits
- Refresh: 30-60s

### 2. Subreddit Analysis
- Purpose: Compare stress patterns across subreddits
- Features:
  - Multi-subreddit comparison
  - Time-based filtering
  - Stress distribution analysis
- Use Cases:
  - Identify high-stress subreddits
  - Analyze temporal patterns
  - Compare community behaviors

### 3. System Health Monitoring
- Purpose: Monitor pipeline infrastructure
- Components:
  - Kafka metrics (lag, throughput)
  - Spark metrics (processing time, memory)
  - Cassandra metrics (latency, operations)
  - Model metrics (inference time, version)
- Alerts:
  - Consumer lag >5000
  - Batch processing >30s
  - Error rate >5%

## Usage Guide

### Filtering Data
1. Use time range picker (top right)
2. Select subreddit from dropdown (Subreddit Analysis)
3. Use quick range buttons (1h, 6h, 24h, 7d, 30d)

### Interpreting Metrics
- **Stress Percentage**: % of posts classified as stress-related
- **Consumer Lag**: Number of messages behind real-time
- **Batch Processing Time**: Time to process one micro-batch

### Troubleshooting
- **Panel shows "No Data"**: Check Cassandra connection
- **Slow loading**: Reduce time range or increase refresh interval
- **Wrong values**: Verify time zone settings (should be UTC)
```

---

## Rollback Plan

If dashboards cause issues:

1. **Remove problematic dashboards:**
   - Delete via Grafana UI: Dashboard Settings → Delete
   - Or remove JSON files and restart Grafana

2. **Revert to previous version:**
   ```bash
   cd monitoring/grafana/dashboards
   git checkout HEAD~1 .
   docker-compose restart grafana
   ```

3. **Disable auto-provisioning:**
   - Comment out provisioning volumes in docker-compose.yml
   - Restart Grafana

---

## Testing Checklist

- [ ] Subreddit Analysis dashboard created
- [ ] System Health dashboard created
- [ ] Subreddit variable works (multi-select)
- [ ] Time range filters functional (1h, 6h, 24h, 7d, 30d)
- [ ] Stress percentage timeline displays correctly
- [ ] Post volume bar chart shows data
- [ ] Stress distribution histogram works
- [ ] Pipeline status stat panels show metrics
- [ ] Kafka metrics panels functional
- [ ] Spark metrics panels functional
- [ ] Cassandra metrics panels functional
- [ ] Model inference latency displayed
- [ ] All queries execute within 5 seconds
- [ ] Dashboards mobile-responsive
- [ ] Navigation links work
- [ ] Dashboards exported as JSON
- [ ] Auto-provisioning tested
- [ ] Documentation complete

---

## Dependencies

**Required before starting:**
- TASK-015: Grafana Live Data Connection
- Prometheus exporters configured
- Cassandra data populated

**Blocks:**
- TASK-017: Configure Dashboard Refresh Intervals
- TASK-026: Alerting Rules Configuration
- TASK-036: Comprehensive Monitoring Setup

---

## Notes

- Use consistent color schemes across dashboards
- Keep panel titles clear and descriptive
- Add help tooltips where needed
- Consider color-blind friendly palettes
- Test with actual production data volumes
- Document any custom transformations or calculations
- Keep dashboard JSON in version control
- Use dashboard folders to organize related dashboards

---

## Estimated Completion

**Total Time:** 14-16 hours (2 days)

**Breakdown:**
- Planning & Design: 1 hour
- Subreddit Analysis Dashboard: 5 hours
- System Health Dashboard: 6 hours
- Testing & Optimization: 2 hours
- Documentation: 2 hours
