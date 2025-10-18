# Grafana Live Data Queries - Updated for TASK-015

**Last Updated**: 2025-10-11 17:26 UTC
**Current Hour**: 2025-10-11-17

This document contains production-ready queries for Grafana dashboards using live Cassandra data.

---

## Quick Reference

**Generate Current Queries**:
```bash
python3 grafana/scripts/generate_partitions.py --dashboard-update --hours 24
```

**Current Hour Partition**:
```bash
python3 grafana/scripts/generate_partitions.py --current
```

---

## Panel 1: Global Stress Trend (Time Series) - Last 24 Hours

**Purpose**: Show stress percentage trend over the last 24 hours

**Query**:
```sql
SELECT
  toTimestamp(hour_start) as time,
  pct_stress as "Stress %"
FROM reddit_rt.agg_global_hour
WHERE hour_partition IN (
  '2025-10-10-18',
  '2025-10-10-19',
  '2025-10-10-20',
  '2025-10-10-21',
  '2025-10-10-22',
  '2025-10-10-23',
  '2025-10-11-00',
  '2025-10-11-01',
  '2025-10-11-02',
  '2025-10-11-03',
  '2025-10-11-04',
  '2025-10-11-05',
  '2025-10-11-06',
  '2025-10-11-07',
  '2025-10-11-08',
  '2025-10-11-09',
  '2025-10-11-10',
  '2025-10-11-11',
  '2025-10-11-12',
  '2025-10-11-13',
  '2025-10-11-14',
  '2025-10-11-15',
  '2025-10-11-16',
  '2025-10-11-17'
)
ORDER BY hour_start ASC
```

**Panel Settings**:
- Visualization: Time series
- Unit: Percent (0-100)
- Legend: Bottom
- Tooltip: All series
- Fill opacity: 20%
- Line width: 2
- Gradient mode: Opacity

**Thresholds**:
- 0-40%: Green (Base)
- 40-60%: Yellow
- 60-100%: Red

**Query Options**:
- Max data points: 1000
- Min interval: 1h
- Cache timeout: 60s

---

## Panel 2: Current Stress Percentage (Stat Panel)

**Purpose**: Show current hour's stress percentage as big number

**Query**:
```sql
SELECT
  pct_stress as value
FROM reddit_rt.agg_global_hour
WHERE hour_partition = '2025-10-11-17'
ORDER BY hour_start DESC
LIMIT 1
```

**Panel Settings**:
- Visualization: Stat
- Calc: Last (not null)
- Unit: Percent (0-100)
- Color mode: Value
- Graph mode: None
- Text mode: Value and name

**Thresholds**:
- 0-40%: Green (#73BF69)
- 40-60%: Yellow (#FF9830)
- 60-100%: Red (#F2495C)

---

## Panel 3: Total Posts Processed (Stat Panel)

**Purpose**: Show total posts in current hour

**Query**:
```sql
SELECT
  total_cnt as value
FROM reddit_rt.agg_global_hour
WHERE hour_partition = '2025-10-11-17'
ORDER BY hour_start DESC
LIMIT 1
```

**Panel Settings**:
- Visualization: Stat
- Unit: Short (1000 = 1K)
- Color mode: None
- Graph mode: Area
- Sparkline: Show

---

## Panel 4: Average Stress Score (Gauge)

**Purpose**: Show average stress score (0.0-1.0)

**Query**:
```sql
SELECT
  avg_score as value
FROM reddit_rt.agg_global_hour
WHERE hour_partition = '2025-10-11-17'
ORDER BY hour_start DESC
LIMIT 1
```

**Panel Settings**:
- Visualization: Gauge
- Min: 0
- Max: 1.0
- Unit: None (decimal)
- Show threshold labels: Yes
- Show threshold markers: Yes

**Thresholds**:
- 0.0-0.4: Green
- 0.4-0.7: Yellow
- 0.7-1.0: Red

---

## Panel 5: Top 10 Subreddits by Stress (Bar Chart)

**Purpose**: Show which subreddits have highest stress levels

**Query**:
```sql
SELECT
  subreddit as metric,
  pct_stress as value
FROM reddit_rt.agg_subreddit_hour
WHERE hour_partition = '2025-10-11-17'
ORDER BY pct_stress DESC
LIMIT 10
ALLOW FILTERING
```

**Panel Settings**:
- Visualization: Bar chart
- Orientation: Horizontal
- Unit: Percent (0-100)
- Color scheme: By value (green-yellow-red)
- Show values: On hover
- Legend: Hide

**Note**: `ALLOW FILTERING` is required for ORDER BY on non-clustering column. Monitor performance.

---

## Panel 6: Hourly Post Volume (Time Series)

**Purpose**: Show how post volume changes throughout the day

**Query**:
```sql
SELECT
  toTimestamp(hour_start) as time,
  total_cnt as "Total Posts"
FROM reddit_rt.agg_global_hour
WHERE hour_partition IN (
  '2025-10-10-18',
  '2025-10-10-19',
  '2025-10-10-20',
  '2025-10-10-21',
  '2025-10-10-22',
  '2025-10-10-23',
  '2025-10-11-00',
  '2025-10-11-01',
  '2025-10-11-02',
  '2025-10-11-03',
  '2025-10-11-04',
  '2025-10-11-05',
  '2025-10-11-06',
  '2025-10-11-07',
  '2025-10-11-08',
  '2025-10-11-09',
  '2025-10-11-10',
  '2025-10-11-11',
  '2025-10-11-12',
  '2025-10-11-13',
  '2025-10-11-14',
  '2025-10-11-15',
  '2025-10-11-16',
  '2025-10-11-17'
)
ORDER BY hour_start ASC
```

**Panel Settings**:
- Visualization: Time series
- Style: Bars
- Unit: Short (count)
- Color: Single color (blue)
- Fill opacity: 80%

---

## Panel 7: Stressed vs Non-Stressed Posts (Stacked Area)

**Purpose**: Show breakdown of stressed vs non-stressed posts

**Query A - Stressed Posts**:
```sql
SELECT
  toTimestamp(hour_start) as time,
  stress_cnt as "Stressed Posts"
FROM reddit_rt.agg_global_hour
WHERE hour_partition IN (
  '2025-10-10-18',
  '2025-10-10-19',
  '2025-10-10-20',
  '2025-10-10-21',
  '2025-10-10-22',
  '2025-10-10-23',
  '2025-10-11-00',
  '2025-10-11-01',
  '2025-10-11-02',
  '2025-10-11-03',
  '2025-10-11-04',
  '2025-10-11-05',
  '2025-10-11-06',
  '2025-10-11-07',
  '2025-10-11-08',
  '2025-10-11-09',
  '2025-10-11-10',
  '2025-10-11-11',
  '2025-10-11-12',
  '2025-10-11-13',
  '2025-10-11-14',
  '2025-10-11-15',
  '2025-10-11-16',
  '2025-10-11-17'
)
ORDER BY hour_start ASC
```

**Query B - Non-Stressed Posts**:
```sql
SELECT
  toTimestamp(hour_start) as time,
  (total_cnt - stress_cnt) as "Non-Stressed Posts"
FROM reddit_rt.agg_global_hour
WHERE hour_partition IN (
  '2025-10-10-18',
  '2025-10-10-19',
  '2025-10-10-20',
  '2025-10-10-21',
  '2025-10-10-22',
  '2025-10-10-23',
  '2025-10-11-00',
  '2025-10-11-01',
  '2025-10-11-02',
  '2025-10-11-03',
  '2025-10-11-04',
  '2025-10-11-05',
  '2025-10-11-06',
  '2025-10-11-07',
  '2025-10-11-08',
  '2025-10-11-09',
  '2025-10-11-10',
  '2025-10-11-11',
  '2025-10-11-12',
  '2025-10-11-13',
  '2025-10-11-14',
  '2025-10-11-15',
  '2025-10-11-16',
  '2025-10-11-17'
)
ORDER BY hour_start ASC
```

**Panel Settings**:
- Visualization: Time series
- Style: Area
- Stacking: Normal
- Fill opacity: 50%
- Colors: Red (stressed), Green (non-stressed)

---

## Panel 8: Subreddit Post Volume (Table)

**Purpose**: Show detailed breakdown by subreddit

**Query**:
```sql
SELECT
  subreddit as "Subreddit",
  total_cnt as "Total",
  stress_cnt as "Stressed",
  pct_stress as "Stress %"
FROM reddit_rt.agg_subreddit_hour
WHERE hour_partition = '2025-10-11-17'
ORDER BY total_cnt DESC
LIMIT 20
ALLOW FILTERING
```

**Panel Settings**:
- Visualization: Table
- Column width: Auto
- Cell display mode: Color background (for Stress %)
- Pagination: 10 rows per page

**Column Overrides**:
- Stress %: Color mode = Cell, Thresholds = 0/40/60

---

## Panel 9: Subreddit Stress Comparison (Multi-line Chart)

**Purpose**: Compare stress trends across key subreddits

**Query for Depression**:
```sql
SELECT
  toTimestamp(hour_start) as time,
  pct_stress as "r/depression"
FROM reddit_rt.agg_subreddit_hour
WHERE subreddit = 'depression'
  AND hour_partition IN (
    '2025-10-11-12',
    '2025-10-11-13',
    '2025-10-11-14',
    '2025-10-11-15',
    '2025-10-11-16',
    '2025-10-11-17'
  )
ORDER BY hour_start ASC
```

**Query for Anxiety**:
```sql
SELECT
  toTimestamp(hour_start) as time,
  pct_stress as "r/anxiety"
FROM reddit_rt.agg_subreddit_hour
WHERE subreddit = 'anxiety'
  AND hour_partition IN (
    '2025-10-11-12',
    '2025-10-11-13',
    '2025-10-11-14',
    '2025-10-11-15',
    '2025-10-11-16',
    '2025-10-11-17'
  )
ORDER BY hour_start ASC
```

**Note**: Add separate query for each subreddit you want to compare

---

## Dashboard Variables (Optional)

### Variable: current_hour

**Type**: Query
**Query**:
```sql
SELECT hour_partition
FROM reddit_rt.agg_global_hour
LIMIT 1
```

**Settings**:
- Refresh: On time range change
- Sort: None
- Selection: Single value
- Include: None

### Variable: subreddit_filter

**Type**: Query
**Query**:
```sql
SELECT DISTINCT subreddit
FROM reddit_rt.agg_subreddit_hour
WHERE hour_partition = '2025-10-11-17'
LIMIT 50
```

**Settings**:
- Refresh: On dashboard load
- Sort: Alphabetical (asc)
- Selection: Multi-value
- Include: All option

**Usage in Query**:
```sql
SELECT ...
FROM reddit_rt.agg_subreddit_hour
WHERE subreddit IN ($subreddit_filter)
  AND hour_partition = ...
```

---

## Performance Optimization

### Query Caching

Configure in each panel's Query Options:
- **Cache timeout**: 60 seconds
- **Max data points**: 1000
- **Min interval**: 1h (for hourly data)

### Cassandra Datasource Settings

Update in `grafana/provisioning/datasources/cassandra.yml`:
```yaml
jsonData:
  consistency: ONE          # Fastest for read-heavy workloads
  timeout: 30               # Increase if queries timeout
  maxConnections: 10        # Connection pooling
```

### Query Best Practices

1. **Always specify partition keys**: Include hour_partition in WHERE clause
2. **Limit time range**: Query max 48-72 hours for dashboards
3. **Use LIMIT**: Always add LIMIT to prevent full table scans
4. **Avoid ALLOW FILTERING when possible**: Pre-aggregate data instead
5. **Use aggregate tables**: Query agg_* tables, not raw tables

---

## Auto-Refresh Configuration

**Dashboard Settings** → **Time Picker**:
- Auto refresh: Enabled
- Refresh intervals: `30s, 1m, 5m, 15m, 30m, 1h`
- Default: `1m`

**Recommended Refresh Rates**:
- Real-time panels (current stats): 30s - 1m
- Trend charts (24h history): 5m
- Summary tables: 5m - 15m
- Weekly/monthly views: 1h

---

## Updating Queries Daily

### Manual Update

1. Run script to generate new partition list:
   ```bash
   python3 grafana/scripts/generate_partitions.py --dashboard-update --hours 24
   ```

2. Copy partition list from output

3. Update each panel query in Grafana UI

4. Save dashboard

### Automated Update (Future Enhancement)

Create Airflow DAG to:
1. Generate current partition list
2. Update dashboard JSON via Grafana API
3. Schedule to run daily at 00:00 UTC

---

## Testing Queries

### Test in cqlsh First

```bash
docker exec -it reddit-cassandra cqlsh

# Test global trend query
cqlsh> SELECT hour_start, pct_stress, total_cnt
       FROM reddit_rt.agg_global_hour
       WHERE hour_partition = '2025-10-11-17';

# Test performance with TRACING
cqlsh> TRACING ON;
cqlsh> SELECT * FROM reddit_rt.agg_global_hour
       WHERE hour_partition IN ('2025-10-11-17', '2025-10-11-16');
```

### Check Query Performance in Grafana

1. Open panel in edit mode
2. Click **Query Inspector** (icon in top right)
3. View **Stats** tab
4. Check query execution time
5. Target: < 1s for most queries

---

## Troubleshooting

### Query Returns No Data

**Possible Causes**:
- Hour partitions don't match actual data
- Cassandra connection lost
- No data for time range

**Solutions**:
```bash
# Check what partitions exist
docker exec -it reddit-cassandra cqlsh -e "
SELECT DISTINCT hour_partition
FROM reddit_rt.agg_global_hour
LIMIT 50;
"

# Update partition list in queries
python3 grafana/scripts/generate_partitions.py --current
```

### Query Timeout

**Possible Causes**:
- Too many partitions in WHERE clause
- Missing LIMIT clause
- Using ALLOW FILTERING on large dataset

**Solutions**:
- Reduce time range (fewer partitions)
- Add/lower LIMIT value
- Increase timeout in datasource config
- Pre-aggregate data

### Dashboard Doesn't Auto-Refresh

**Check**:
1. Auto-refresh enabled in dashboard settings?
2. Refresh interval selected in dropdown?
3. Browser tab active? (some browsers pause inactive tabs)

---

## Monitoring

### Check Cassandra Performance

```bash
# Check query latency
docker exec -it reddit-cassandra nodetool cfstats reddit_rt.agg_global_hour

# Check read load
docker exec -it reddit-cassandra nodetool tablestats reddit_rt.agg_global_hour
```

### Check Grafana Logs

```bash
# Watch for query errors
docker logs reddit-grafana --tail 100 -f | grep -i error
```

---

## Next Steps

1. **Implement all panel queries** in Grafana UI
2. **Test auto-refresh** with 1-minute interval
3. **Verify query performance** (< 5s target)
4. **Set up daily update process** for partition lists
5. **Create additional dashboards** (TASK-016)
6. **Configure alerting** (TASK-026)

---

**Last Generated**: 2025-10-11 17:26 UTC
**Script**: `grafana/scripts/generate_partitions.py`
**Guide**: `grafana/LIVE_DATA_CONNECTION_GUIDE.md`
