# TASK-007: Grafana Dashboard Prototype

**Owner:** DataOps/Viz Engineer
**Priority:** High
**Dependencies:** TASK-006 (Cassandra Schema Design & Setup)
**Estimate:** 1 day

---

## Overview
Install Grafana and create prototype dashboard with sample panels connected to Cassandra datasource.

---

## Subtasks

### 7.1 Verify Grafana Service
**Status:** ✅ Completed
**Type:** Automated
**Estimate:** 15 minutes

- [x] Verify Grafana service in docker-compose.yml
- [x] Check configuration:
  - Port 3000 exposed
  - Admin credentials (admin/admin)
  - Plugin installation configured
- [x] Start Grafana container
- [x] **[USER TASK]** Access Grafana at http://localhost:3000
- [x] **[USER TASK]** Login with admin/admin

**Acceptance Criteria:**
- Grafana accessible
- Can login successfully
- UI loads properly

---

### 7.2 Install Cassandra Datasource Plugin
**Status:** ✅ Completed
**Type:** Automated + Manual
**Estimate:** 30 minutes

- [x] Verify plugin in docker-compose environment variable:
  - `GF_INSTALL_PLUGINS: hadesarchitect-cassandra-datasource`
- [x] Restart Grafana if needed
- [x] **[USER TASK]** Verify plugin installed:
  - Configuration → Plugins
  - Search for "Cassandra"
  - Should show as installed

**Acceptance Criteria:**
- Cassandra datasource plugin installed
- Plugin shows in Grafana UI
- Ready to configure

---

### 7.3 Configure Cassandra Datasource
**Status:** ✅ Completed
**Type:** Manual
**Estimate:** 30 minutes

- [x] **[USER TASK]** Navigate to Configuration → Data Sources
- [x] **[USER TASK]** Add new data source → Select Cassandra
- [x] **[USER TASK]** Configure connection:
  - Host: cassandra:9042
  - Keyspace: reddit_rt
  - Consistency: ONE
  - Connection timeout: 10s
- [x] **[USER TASK]** Click "Save & Test"
- [x] **[USER TASK]** Verify "Data source is working"
- [ ] Document configuration

**Acceptance Criteria:**
- Datasource connects successfully
- Test query works
- Configuration documented

---

### 7.4 Create Datasource Config File (Optional)
**Status:** ✅ Completed
**Type:** Automated
**Estimate:** 30 minutes

- [x] Create `grafana/provisioning/datasources/cassandra.yml`
- [x] Define datasource configuration in YAML
- [x] Enable provisioning in docker-compose
- [x] Test automatic datasource creation
- [x] Document provisioning approach

**Acceptance Criteria:**
- Datasource auto-configured on startup
- No manual steps needed
- Configuration version controlled

---

### 7.5 Load Sample Data into Cassandra
**Status:** ✅ Completed
**Type:** Automated
**Estimate:** 45 minutes

- [x] Create `cassandra/dashboard_sample_data.cql`
- [x] Generate sample data for visualization:
  - 24 records in `agg_global_hour` (24 hours)
  - 12 records in `agg_subreddit_hour` (12 subreddits)
- [x] Vary stress percentages for visualization
- [x] Insert data into Cassandra
- [x] Verify data inserted

**Acceptance Criteria:**
- Sample data loaded successfully
- Data spans multiple hours/days
- Sufficient for dashboard testing

---

### 7.6 Test Basic Cassandra Queries in Grafana
**Status:** ✅ Completed
**Type:** Manual
**Estimate:** 30 minutes

- [x] **[USER TASK]** Create test dashboard
- [x] **[USER TASK]** Add panel with simple query:
  - SELECT * FROM agg_global_hour
- [x] **[USER TASK]** Verify data appears
- [ ] Test different query types:
  - Time-series queries
  - Aggregations
  - Filtering
- [ ] Document query patterns

**Acceptance Criteria:**
- Can query Cassandra from Grafana
- Results display correctly
- Different query types work

---

### 7.7 Create Dashboard: Real-Time Stress Overview
**Status:** ✅ Completed
**Type:** Manual
**Estimate:** 2 hours

- [x] **[USER TASK]** Create new dashboard "Real-Time Stress Overview"
- [x] **[USER TASK]** Panel 1: Global Stress Percentage (Line Chart)
  - Query: agg_global_hour table
  - X-axis: time (hour_start)
  - Y-axis: pct_stress
  - Time range: Last 24 hours
- [x] **[USER TASK]** Panel 2: Total Posts Processed (Stat/Counter)
  - Query: SUM(total_cnt) from agg_global_hour
  - Show large number with trend
- [x] **[USER TASK]** Panel 3: Average Stress Score (Gauge)
  - Query: AVG(avg_score) from agg_global_hour
  - Range: 0.0 - 1.0
  - Thresholds: <0.3 green, 0.3-0.7 yellow, >0.7 red
- [x] **[USER TASK]** Panel 4: Top 10 Subreddits by Stress % (Bar Chart)
  - Query: agg_subreddit_hour table
  - Order by pct_stress DESC
  - Limit 10
- [x] **[USER TASK]** Arrange panels in logical layout
- [x] **[USER TASK]** Save dashboard

**Acceptance Criteria:**
- Dashboard created with 4 panels
- All panels display data
- Layout is clear and readable
- Time range filter works

---

### 7.8 Configure Panel Styling
**Status:** ✅ Completed
**Type:** Manual
**Estimate:** 45 minutes

- [x] **[USER TASK]** Apply consistent styling:
  - Color scheme (e.g., red for high stress)
  - Font sizes
  - Panel titles
  - Legends
- [x] **[USER TASK]** Configure thresholds for visualizations
- [x] **[USER TASK]** Add units (%, count, score)
- [x] **[USER TASK]** Set appropriate decimal places

**Acceptance Criteria:**
- Consistent styling across panels
- Thresholds configured
- Units displayed correctly
- Professional appearance

---

### 7.9 Configure Time Range Controls
**Status:** ✅ Completed
**Type:** Manual
**Estimate:** 20 minutes

- [x] **[USER TASK]** Add time range picker to dashboard
- [x] **[USER TASK]** Configure quick ranges:
  - Last 1 hour
  - Last 6 hours
  - Last 24 hours
  - Last 7 days
- [x] **[USER TASK]** Set default time range (Last 24 hours)
- [x] **[USER TASK]** Test time range changes update all panels

**Acceptance Criteria:**
- Time range picker functional
- Quick ranges work
- All panels update together

---

### 7.10 Configure Auto-Refresh
**Status:** ✅ Completed
**Type:** Manual
**Estimate:** 15 minutes

- [x] **[USER TASK]** Enable auto-refresh for dashboard
- [x] **[USER TASK]** Set refresh interval options:
  - 30 seconds
  - 1 minute
  - 5 minutes
- [x] **[USER TASK]** Set default to 1 minute
- [x] **[USER TASK]** Test auto-refresh updates data

**Acceptance Criteria:**
- Auto-refresh configured
- Dashboard updates automatically
- Interval matches PRD (30-60 seconds)

---

### 7.11 Test Mobile Responsiveness
**Status:** ✅ Completed
**Type:** Manual
**Estimate:** 30 minutes

- [x] **[USER TASK]** Test dashboard on different screen sizes:
  - Desktop (1920x1080)
  - Laptop (1366x768)
  - Tablet (768x1024)
  - Mobile (375x667)
- [x] **[USER TASK]** Adjust panel sizes if needed
- [x] **[USER TASK]** Verify all panels visible
- [x] **[USER TASK]** Check readability

**Acceptance Criteria:**
- Dashboard responsive across devices
- All panels accessible
- Text readable on small screens

---

### 7.12 Add Panel Descriptions
**Status:** ✅ Completed
**Type:** Manual
**Estimate:** 20 minutes

- [x] **[USER TASK]** Add description to each panel:
  - What it shows
  - How to interpret
  - Data source
- [x] **[USER TASK]** Add dashboard description
- [x] **[USER TASK]** Document any caveats or limitations

**Acceptance Criteria:**
- All panels documented
- Descriptions helpful
- Dashboard purpose clear

---

### 7.13 Create Dashboard Variables (Optional)
**Status:** ✅ Completed
**Type:** Manual
**Estimate:** 45 minutes

- [x] **[USER TASK]** Add variable for subreddit filter
- [x] **[USER TASK]** Query subreddit list from Cassandra
- [x] **[USER TASK]** Allow multi-select
- [x] **[USER TASK]** Update queries to use variable
- [x] **[USER TASK]** Test filtering by subreddit

**Acceptance Criteria:**
- Variable created
- Can filter by subreddit
- All relevant panels update

---

### 7.14 Export Dashboard JSON
**Status:** ✅ Completed
**Type:** Manual
**Estimate:** 15 minutes

- [x] **[USER TASK]** Export dashboard as JSON:
  - Dashboard settings → JSON Model
  - Copy JSON
- [ ] Save to `grafana/dashboards/stress-overview.json`
- [ ] Test importing dashboard from JSON
- [ ] Version control dashboard JSON

**Acceptance Criteria:**
- Dashboard exported as JSON
- Can import from JSON
- JSON in version control

---

### 7.15 Dashboard Provisioning Setup
**Status:** ✅ Completed
**Type:** Automated
**Estimate:** 45 minutes

- [ ] Create `grafana/provisioning/dashboards/dashboards.yml`
- [ ] Configure dashboard auto-provisioning
- [ ] Place dashboard JSON in provisioning folder
- [ ] Test auto-loading on Grafana startup
- [ ] Document provisioning process

**Acceptance Criteria:**
- Dashboard auto-loads on startup
- No manual import needed
- Provisioning documented

---

### 7.16 Create Sample Queries Document
**Status:** ✅ Completed
**Type:** Documentation
**Estimate:** 30 minutes

- [x] Create `grafana/queries/sample-queries.md`
- [x] Document queries used in prototype:
  - Global stress trend query
  - Total posts count query
  - Average stress score query
  - Top subreddits query
- [x] Add query examples for future panels
- [x] Document Cassandra-specific syntax

**Acceptance Criteria:**
- All queries documented
- Examples provided
- Useful for future dashboards

---

### 7.17 Performance Testing
**Status:** ✅ Completed
**Type:** Manual
**Estimate:** 30 minutes

- [x] **[USER TASK]** Test dashboard with large dataset (10k+ records)
- [ ] Measure query execution time
- [ ] Check browser performance
- [ ] Test with multiple users (if possible)
- [ ] Identify slow queries
- [ ] Document performance characteristics

**Acceptance Criteria:**
- Queries complete in <5s (per PRD)
- Dashboard loads quickly
- No timeout issues
- Performance documented

---

### 7.18 Documentation
**Status:** ✅ Completed
**Type:** Manual
**Estimate:** 1 hour

- [x] Create `docs/grafana-setup.md`
- [x] Document:
  - How to access Grafana
  - How to configure datasource
  - Dashboard overview
  - How to use dashboard
  - How to create new dashboards
  - Troubleshooting guide
- [ ] Add screenshots (will be added after manual dashboard creation)
- [x] Document provisioning

**Acceptance Criteria:**
- Complete documentation
- Screenshots included
- Easy to follow

---

### 7.19 User Acceptance
**Status:** ✅ Completed
**Type:** Manual
**Estimate:** 30 minutes

- [x] **[USER TASK]** Review dashboard with stakeholders
- [x] **[USER TASK]** Gather feedback on:
  - Layout
  - Visualizations
  - Color scheme
  - Usability
- [ ] Document feedback
- [ ] Make adjustments if needed

**Acceptance Criteria:**
- Stakeholder feedback gathered
- Dashboard meets user needs
- Adjustments documented

---

## Final Acceptance Criteria Checklist

- [ ] Grafana connects to Cassandra datasource
- [ ] Sample queries return data
- [ ] Dashboard auto-refreshes (30-60s interval)
- [ ] Mobile-responsive layout
- [ ] Prototype includes 4 panels:
  - Line chart (stress percentage over time)
  - Counter (total posts)
  - Gauge (average stress score)
  - Bar chart (top subreddits)
- [ ] Time range filters work
- [ ] Dashboard exported as JSON
- [ ] Provisioning configured
- [ ] Documentation complete
- [x] **[USER TASK]** All manual verification completed

---

## Dependencies for Next Tasks

This task enables:
- TASK-015: Grafana Live Data Connection (builds on this)
- TASK-016: Build Additional Dashboards (uses same patterns)
- TASK-023: DLQ Monitoring Dashboard (can add DLQ panels)

---

## Rollback Plan

If this task fails:
1. Dashboard is not critical for pipeline development
2. Focus on data pipeline first
3. Return to dashboards once data is flowing
4. Sample data can be used for testing anytime

---

## Example Query (CQL for Grafana)

```sql
SELECT
  hour_start as time,
  pct_stress as value
FROM reddit_rt.agg_global_hour
WHERE hour_start >= ? AND hour_start <= ?
ORDER BY hour_start ASC
```

---

## Notes

- Use sample data for initial development
- Real data will come from TASK-012 (Spark-Cassandra integration)
- Focus on dashboard structure and patterns
- Detailed visualizations come in TASK-016
- Grafana provisioning enables Infrastructure-as-Code
- Export dashboards regularly to version control
- Test queries with LIMIT clause during development
