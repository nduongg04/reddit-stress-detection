# TASK-015: Grafana Live Data Connection

**Owner:** DataOps/Viz Engineer
**Priority:** High
**Dependencies:** TASK-012 (Spark-Cassandra Integration)
**Estimate:** 1 day

---

## Overview

Connect Grafana to the production Cassandra instance to visualize real-time Reddit stress detection data. Configure Cassandra datasource, update dashboard queries to use live data, configure auto-refresh intervals, and test query performance with large datasets.

---

## Subtasks

### Subtask 015.1: Cassandra Datasource Configuration

**Estimate:** 30 minutes

**Description:**
- Install Cassandra datasource plugin in Grafana
- Configure connection to Cassandra cluster
- Test connectivity

**Acceptance Criteria:**
- Datasource installed
- Connection successful
- Test queries work

**Configuration:**
```yaml
datasource:
  name: Cassandra-Production
  type: cassandra
  url: localhost:9042
  database: reddit_rt
  access: proxy
  basicAuth: false
  jsonData:
    keyspace: reddit_rt
    consistency: LOCAL_QUORUM
    timeout: 30s
```

---

### Subtask 015.2: Dashboard Query Migration

**Estimate:** 2 hours

**Description:**
- Update prototype dashboard queries to use real Cassandra tables
- Test each panel with live data
- Optimize query performance

**Acceptance Criteria:**
- All panels show live data
- Queries optimized
- No timeout errors

**Example Queries:**
```sql
-- Global stress percentage over time
SELECT hour_bucket, stress_percentage
FROM agg_global_hour
WHERE hour_bucket >= $__timeFrom() AND hour_bucket <= $__timeTo()
ORDER BY hour_bucket ASC;

-- Top subreddits by stress
SELECT subreddit, stress_percentage, total_posts
FROM agg_subreddit_hour
WHERE hour_bucket >= now() - interval '24 hours'
ORDER BY stress_percentage DESC
LIMIT 10;
```

---

### Subtask 015.3: Auto-Refresh Configuration

**Estimate:** 30 minutes

**Description:**
- Configure dashboard auto-refresh intervals
- Test refresh performance
- Set appropriate intervals (30-60s)

**Acceptance Criteria:**
- Auto-refresh working
- No performance degradation
- Configurable intervals

---

### Subtask 015.4: Query Performance Testing

**Estimate:** 2 hours

**Description:**
- Test query performance with large datasets
- Identify slow queries
- Optimize using indexes and query rewriting
- **[USER TASK]** Verify query performance acceptable

**Acceptance Criteria:**
- All queries complete in <5s
- No timeouts
- Performance documented

**Performance Targets:**
- Simple queries: <1s
- Aggregation queries: <3s
- Complex queries: <5s

---

### Subtask 015.5: Query Caching Implementation

**Estimate:** 1 hour

**Description:**
- Configure query result caching
- Set cache TTL appropriately
- Monitor cache hit rates

**Acceptance Criteria:**
- Caching configured
- Cache hit rate >70%
- Dashboard performance improved

---

### Subtask 015.6: Time Range Controls

**Estimate:** 1 hour

**Description:**
- Add time range picker to dashboard
- Configure preset time ranges (1h, 6h, 24h, 7d, 30d)
- Test with different time ranges

**Acceptance Criteria:**
- Time picker working
- All presets functional
- Data filters correctly

---

### Subtask 015.7: Variables and Filters

**Estimate:** 1.5 hours

**Description:**
- Add dashboard variables (subreddit selector, time granularity)
- Implement filter cascading
- Test variable interactions

**Acceptance Criteria:**
- Variables working
- Filters applied correctly
- Interactive filtering smooth

---

### Subtask 015.8: Real-Time Validation

**Estimate:** 1 hour

**Description:**
- Verify dashboard updates with new data
- Test refresh within 60s of data arrival
- Validate data accuracy

**Acceptance Criteria:**
- Dashboard updates timely
- Data matches source
- Refresh interval appropriate

---

### Subtask 015.9: Error Handling

**Estimate:** 45 minutes

**Description:**
- Handle Cassandra connection failures
- Display meaningful error messages
- Implement retry logic

**Acceptance Criteria:**
- Errors displayed clearly
- Retry logic works
- Dashboard recovers automatically

---

### Subtask 015.10: Documentation

**Estimate:** 1 hour

**Description:**
- Document dashboard queries
- Create user guide
- Document troubleshooting steps

**Acceptance Criteria:**
- Queries documented
- User guide complete
- Troubleshooting guide available

---

### Subtask 015.11: Performance Monitoring

**Estimate:** 1 hour

**Description:**
- Monitor query execution times
- Set up alerts for slow queries
- Track Cassandra resource usage

**Acceptance Criteria:**
- Query metrics collected
- Alerts configured
- Resource usage monitored

---

### Subtask 015.12: Final Verification

**Estimate:** 1 hour

**Description:**
- Test all dashboard panels with live data
- Verify auto-refresh working
- **[USER TASK]** Approve dashboard for production

**Acceptance Criteria:**
- All panels functional
- Performance acceptable
- Stakeholder approval obtained

---

## Rollback Plan

If Grafana connection fails:
1. Revert to mock datasource
2. Check Cassandra connectivity
3. Review datasource configuration
4. Restart Grafana if needed

---

## Testing Checklist

- [ ] Datasource connected to Cassandra
- [ ] All queries return data
- [ ] Query performance <5s
- [ ] Auto-refresh working (30-60s)
- [ ] Time range controls functional
- [ ] Variables and filters working
- [ ] Error handling tested
- [ ] Caching improving performance
- [ ] Documentation complete

---

## Dependencies

**Required before starting:**
- TASK-012: Cassandra tables populated with data
- TASK-007: Grafana prototype dashboard
- Cassandra cluster operational

**Blocks:**
- TASK-016: Build Additional Dashboards
- TASK-017: Configure Dashboard Refresh Intervals
- TASK-026: Alerting Rules Configuration

---

## Notes

- Use Cassandra datasource plugin (community or HadesArchitect)
- Query optimization critical for performance
- Consider materialized views for complex queries
- Test with production data volumes
- Monitor Cassandra query performance

---

## Estimated Completion

**Total Time:** 12-14 hours (1 day)

**Breakdown:**
- Configuration & Setup: 3 hours
- Query Migration & Optimization: 5 hours
- Testing & Validation: 3 hours
- Documentation: 2 hours
