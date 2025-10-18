# TASK-017: Configure Dashboard Refresh Intervals

**Owner:** DataOps/Viz Engineer
**Priority:** Low
**Dependencies:** TASK-016 (Build Additional Dashboards)
**Estimate:** 0.5 days

---

## Overview

Optimize dashboard refresh intervals and query caching to ensure smooth performance while maintaining data freshness. Configure appropriate refresh rates for different dashboard types and implement query caching strategies.

---

## Subtasks

### Subtask 017.1: Analyze Dashboard Query Performance

**Estimate:** 1 hour

**Description:**
- Review all dashboard queries using Grafana Query Inspector
- Identify slow queries (>2s execution time)
- Document query execution times
- **[USER TASK]** Use Query Inspector to analyze each panel

**Acceptance Criteria:**
- All queries analyzed and documented
- Slow queries identified
- Baseline metrics recorded

**Steps:**
1. Open each dashboard
2. For each panel: Edit → Query Inspector
3. Record execution times

**Create Performance Log:**
`monitoring/grafana/performance_baseline.md`

```markdown
# Dashboard Query Performance Baseline

## Main Dashboard - Real-Time Stress Overview
| Panel | Query Time | Result Rows | Notes |
|-------|------------|-------------|-------|
| Stress % Gauge | 45ms | 1 | Fast |
| Total Posts Counter | 120ms | 1 | Acceptable |
| Top Subreddits | 890ms | 10 | Needs optimization |
| Stress Timeline | 1.2s | 168 | Acceptable (24h hourly) |

## Subreddit Analysis Dashboard
| Panel | Query Time | Result Rows | Notes |
|-------|------------|-------------|-------|
| Multi-line Stress % | 2.3s | 672 | SLOW - needs optimization |
| Post Volume Bar Chart | 1.8s | 672 | Borderline |
| Stress Distribution | 450ms | 48 | Good |

## System Health Dashboard
| Panel | Query Time | Result Rows | Notes |
|-------|------------|-------------|-------|
| Kafka Consumer Lag | 80ms | 12 | Fast (Prometheus) |
| Spark Batch Time | 95ms | 24 | Fast (Prometheus) |
| Cassandra Latency | 150ms | 48 | Good |
```

---

### Subtask 017.2: Optimize Slow Queries

**Estimate:** 2 hours

**Description:**
- Rewrite slow queries with better filtering
- Add appropriate indexes (if missing)
- Use materialized views where beneficial
- Reduce result set sizes

**Acceptance Criteria:**
- All queries execute in <2 seconds
- Query optimization documented
- No functionality lost

**Query Optimization Examples:**

**Before (Slow - 2.3s):**
```sql
SELECT hour_bucket, subreddit,
       (stress_count * 100.0 / total_count) as stress_percentage
FROM reddit_rt.agg_subreddit_hour
WHERE subreddit IN ('anxiety','depression','stress','mentalhealth')
  AND hour_bucket >= now() - 7d
ORDER BY hour_bucket ASC
```

**After (Optimized - <1s):**
```sql
-- Use time bucketing and limit results
SELECT hour_bucket, subreddit,
       (stress_count * 100.0 / total_count) as stress_percentage
FROM reddit_rt.agg_subreddit_hour
WHERE subreddit IN ('anxiety','depression','stress','mentalhealth')
  AND hour_bucket >= $__timeFrom
  AND hour_bucket <= $__timeTo
ORDER BY hour_bucket ASC
LIMIT 1000
```

**Additional Optimizations:**
- Use Grafana's `$__timeFilter` macro
- Apply `ALLOW FILTERING` only when necessary (Cassandra)
- Reduce time range for detailed queries
- Pre-aggregate data where possible

---

### Subtask 017.3: Configure Refresh Intervals by Dashboard Type

**Estimate:** 30 minutes

**Description:**
- Set appropriate refresh intervals based on dashboard purpose
- Configure auto-refresh options
- Test refresh behavior
- **[USER TASK]** Configure refresh settings in each dashboard

**Acceptance Criteria:**
- Refresh intervals configured appropriately
- Auto-refresh enabled
- Settings documented

**Recommended Refresh Intervals:**

| Dashboard | Refresh Interval | Rationale |
|-----------|------------------|-----------|
| Real-Time Stress Overview | 30s | Real-time monitoring, frequent updates needed |
| Subreddit Analysis | 1m | Analysis dashboard, less time-sensitive |
| System Health | 30s | Infrastructure monitoring, quick issue detection |

**Configuration Steps:**
1. Open Dashboard Settings → Time Options
2. Set default refresh interval
3. Configure available intervals in dropdown

**Grafana Configuration:**
```json
{
  "refresh": "30s",
  "timepicker": {
    "refresh_intervals": [
      "10s",
      "30s",
      "1m",
      "5m",
      "15m",
      "30m",
      "1h"
    ]
  }
}
```

---

### Subtask 017.4: Implement Query Caching

**Estimate:** 1.5 hours

**Description:**
- Configure Grafana query caching
- Set appropriate TTL for different query types
- Enable caching in datasource settings
- Test cache effectiveness

**Acceptance Criteria:**
- Query caching enabled
- Cache TTL configured
- Cache hit rate >70%

**Files to Create/Modify:**
`monitoring/grafana/grafana.ini`

```ini
[caching]
enabled = true
backend = memory

[query_cache]
enabled = true
# Cache TTL in seconds
ttl = 60

[dataproxy]
# Enable response caching
timeout = 30
keep_alive_seconds = 30
```

**Datasource-Specific Caching:**

For Cassandra datasource, configure caching per query:
```json
{
  "cacheTimeout": "60s",
  "queryCachingTTL": 60000
}
```

For Prometheus:
```
Query Options:
- Type: Range
- Min step: 15s (reduces data points)
- Cache: Enabled
```

---

### Subtask 017.5: Configure Browser Caching

**Estimate:** 30 minutes

**Description:**
- Enable browser caching for static assets
- Configure cache headers
- Test browser cache behavior

**Acceptance Criteria:**
- Browser caching enabled
- Assets cached properly
- Page load time improved

**Update nginx configuration (if using reverse proxy):**
`monitoring/nginx/grafana.conf`

```nginx
location /grafana/ {
    proxy_pass http://grafana:3000/;

    # Enable browser caching for static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1d;
        add_header Cache-Control "public, immutable";
    }

    # Disable caching for API calls
    location ~* /api/ {
        expires -1;
        add_header Cache-Control "no-store, no-cache, must-revalidate";
    }
}
```

---

### Subtask 017.6: Optimize Panel Settings

**Estimate:** 1 hour

**Description:**
- Configure appropriate data point limits
- Set decimals and units correctly
- Enable/disable unnecessary features
- **[USER TASK]** Review and optimize each panel

**Acceptance Criteria:**
- Panel settings optimized
- No unnecessary data fetched
- Display remains clear and useful

**Panel Optimization Checklist:**

**For Time Series Panels:**
```
Max data points: 1000 (default is good)
Min interval: 1m (prevents excessive granularity)
Relative time: Use dashboard time range
Transform: Only if necessary (expensive operation)
```

**For Stat/Gauge Panels:**
```
Calculation: Last (most efficient)
Reduce data: True
Show thresholds: Only if needed
```

**For Table Panels:**
```
Data: Current (not All)
Max rows: 100 (or as needed)
Pagination: Enabled if >20 rows
```

---

### Subtask 017.7: Configure Concurrent Query Limits

**Estimate:** 30 minutes

**Description:**
- Set limits on concurrent queries to Cassandra
- Configure connection pooling
- Prevent resource exhaustion

**Acceptance Criteria:**
- Query concurrency limited
- Connection pooling configured
- No database overload

**Grafana Configuration:**
`monitoring/grafana/grafana.ini`

```ini
[dataproxy]
max_conns_per_host = 100
max_idle_connections = 10
max_idle_connections_per_host = 2

[database]
max_open_conn = 100
max_idle_conn = 10
conn_max_lifetime = 14400
```

**Cassandra Connection Pool:**
```yaml
# In datasource settings
jsonData:
  maxConcurrentQueries: 10
  queryTimeout: 30s
  connectTimeout: 10s
```

---

### Subtask 017.8: Load Testing Setup

**Estimate:** 1 hour

**Description:**
- Create load testing script to simulate multiple users
- Test dashboard performance under load
- Measure response times and resource usage

**Acceptance Criteria:**
- Load test script created
- Performance under load measured
- Bottlenecks identified

**Files to Create:**
`monitoring/grafana/load_test.sh`

```bash
#!/bin/bash

# Load test Grafana dashboards
# Simulates multiple concurrent users

GRAFANA_URL="http://localhost:3000"
API_KEY="your_api_key_here"
CONCURRENT_USERS=20
DURATION_SECONDS=300

echo "Starting Grafana load test"
echo "Concurrent users: $CONCURRENT_USERS"
echo "Duration: ${DURATION_SECONDS}s"

# Function to simulate user browsing dashboards
simulate_user() {
    local user_id=$1
    local end_time=$((SECONDS + DURATION_SECONDS))

    while [ $SECONDS -lt $end_time ]; do
        # Request main dashboard
        curl -s -H "Authorization: Bearer $API_KEY" \
            "$GRAFANA_URL/api/dashboards/uid/main-dashboard" > /dev/null

        sleep 2

        # Request subreddit analysis
        curl -s -H "Authorization: Bearer $API_KEY" \
            "$GRAFANA_URL/api/dashboards/uid/subreddit-analysis" > /dev/null

        sleep 3

        # Request system health
        curl -s -H "Authorization: Bearer $API_KEY" \
            "$GRAFANA_URL/api/dashboards/uid/system-health" > /dev/null

        sleep 5
    done

    echo "User $user_id completed"
}

# Start concurrent users
for i in $(seq 1 $CONCURRENT_USERS); do
    simulate_user $i &
done

# Wait for all users to complete
wait

echo "Load test completed"
```

**Monitor during test:**
```bash
# Monitor Grafana resource usage
docker stats grafana

# Monitor Cassandra query load
nodetool tpstats

# Monitor cache hit rate
# Check Grafana logs for cache statistics
```

---

### Subtask 017.9: Performance Testing and Validation

**Estimate:** 1.5 hours

**Description:**
- Run load tests with different user counts
- Measure dashboard load times
- Validate cache hit rates
- **[USER TASK]** Monitor performance during tests

**Acceptance Criteria:**
- All dashboards load within 5 seconds under normal load
- Cache hit rate >70%
- No errors during load test

**Performance Test Scenarios:**

```bash
# Scenario 1: Low load (5 users)
./load_test.sh 5 300

# Scenario 2: Normal load (20 users)
./load_test.sh 20 300

# Scenario 3: High load (50 users)
./load_test.sh 50 300
```

**Performance Validation Checklist:**
- [ ] Main dashboard loads <3s (p95)
- [ ] Subreddit analysis loads <5s (p95)
- [ ] System health loads <3s (p95)
- [ ] No query timeouts
- [ ] Cache hit rate >70%
- [ ] CPU usage <80% during peak
- [ ] Memory usage stable
- [ ] No connection pool exhaustion

---

### Subtask 017.10: Configure Query Timeout Settings

**Estimate:** 30 minutes

**Description:**
- Set appropriate query timeouts
- Configure timeout alerts
- Test timeout behavior

**Acceptance Criteria:**
- Timeouts configured appropriately
- Long-running queries terminated
- Users notified of timeouts

**Datasource Configuration:**
```json
{
  "timeout": 30,
  "queryTimeout": "30s"
}
```

**Panel-Level Timeouts:**
```json
{
  "maxDataPoints": 1000,
  "interval": "1m",
  "timeout": 30000
}
```

---

### Subtask 017.11: Dashboard Performance Monitoring

**Estimate:** 1 hour

**Description:**
- Set up monitoring for dashboard performance
- Create alerts for slow queries
- Track cache hit rates over time

**Acceptance Criteria:**
- Performance metrics tracked
- Alerts configured
- Trends visible

**Metrics to Track:**
- Dashboard load time
- Query execution time
- Cache hit/miss ratio
- Concurrent users
- Error rates

**Create Monitoring Panel:**
Add to System Health Dashboard:

```
Panel: "Grafana Performance"
Metrics:
- grafana_api_dashboard_get_duration_seconds
- grafana_database_query_duration_seconds
- grafana_cache_hit_ratio
- grafana_active_users

Alert: Query time >5s for 5 minutes
```

---

### Subtask 017.12: Documentation and Best Practices

**Estimate:** 1 hour

**Description:**
- Document refresh interval configurations
- Create performance tuning guide
- Document query optimization techniques

**Acceptance Criteria:**
- Configuration documented
- Best practices documented
- Examples provided

**Files to Create:**
`monitoring/grafana/PERFORMANCE_TUNING.md`

```markdown
# Grafana Performance Tuning Guide

## Refresh Interval Configuration

### Guidelines
- Real-time dashboards: 30s
- Analysis dashboards: 1-5m
- Historical dashboards: 5-15m

### Configuration
Dashboard Settings → Time Options → Refresh

## Query Optimization

### Best Practices
1. Always use time range variables (`$__timeFrom`, `$__timeTo`)
2. Limit result sets (use `LIMIT` clause)
3. Use appropriate time bucketing (hourly for 7d+, daily for 30d+)
4. Avoid `ALLOW FILTERING` in Cassandra queries
5. Use materialized views for complex aggregations

### Example Optimizations

**Before:**
```sql
SELECT * FROM table WHERE created_at > 0
```

**After:**
```sql
SELECT hour_bucket, metric_value
FROM table
WHERE hour_bucket >= $__timeFrom
  AND hour_bucket <= $__timeTo
LIMIT 1000
```

## Caching Strategy

### Cache TTL Guidelines
- Real-time data: 30-60s
- Hourly aggregations: 5-10m
- Daily aggregations: 1h
- Static data: 24h

### Monitoring Cache Performance
Check cache hit rate in Grafana logs:
```
grep "cache" /var/log/grafana/grafana.log
```

Target: >70% hit rate

## Performance Targets

| Metric | Target |
|--------|--------|
| Dashboard load time | <5s (p95) |
| Query execution time | <2s |
| Cache hit rate | >70% |
| Concurrent users supported | 50+ |

## Troubleshooting

### Slow Dashboard Loading
1. Check query execution times (Query Inspector)
2. Review cache configuration
3. Optimize queries
4. Reduce time range or data points

### Low Cache Hit Rate
1. Increase cache TTL
2. Ensure caching is enabled in datasource
3. Check cache backend configuration
4. Review query patterns

### High Resource Usage
1. Reduce concurrent query limits
2. Increase cache usage
3. Optimize expensive queries
4. Consider query result limits
```

---

## Rollback Plan

If performance issues occur:

1. **Revert refresh intervals:**
   ```bash
   # Edit dashboard JSON and increase intervals
   # Or use Grafana UI to change settings
   ```

2. **Disable caching:**
   ```ini
   # In grafana.ini
   [caching]
   enabled = false
   ```

3. **Restore previous configuration:**
   ```bash
   cd monitoring/grafana
   git checkout HEAD~1 grafana.ini
   docker-compose restart grafana
   ```

---

## Testing Checklist

- [ ] All queries analyzed and documented
- [ ] Slow queries optimized (<2s execution)
- [ ] Refresh intervals configured per dashboard
- [ ] Query caching enabled and configured
- [ ] Cache TTL set appropriately
- [ ] Browser caching configured
- [ ] Panel settings optimized
- [ ] Concurrent query limits set
- [ ] Load testing completed
- [ ] Performance under load validated
- [ ] Cache hit rate >70%
- [ ] Query timeouts configured
- [ ] Performance monitoring enabled
- [ ] Documentation complete
- [ ] Best practices documented

---

## Dependencies

**Required before starting:**
- TASK-016: Build Additional Dashboards
- All dashboards operational

**Blocks:**
- TASK-026: Alerting Rules Configuration (benefits from optimized queries)

---

## Notes

- Refresh intervals can be user-configurable, but set good defaults
- Caching is most effective for queries with consistent results
- Monitor cache memory usage to prevent overflow
- Different datasources may have different caching mechanisms
- Test performance changes in staging before production
- Document any performance issues and resolutions
- Keep performance baseline metrics for comparison
- Review and adjust settings periodically based on usage patterns

---

## Estimated Completion

**Total Time:** 10-12 hours (0.5 days, allowing for testing iterations)

**Breakdown:**
- Analysis & Optimization: 4 hours
- Configuration: 3 hours
- Testing & Validation: 3 hours
- Documentation: 2 hours
