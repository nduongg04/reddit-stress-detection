# Phase 5: Dashboard

## Goal
Build real-time Streamlit dashboard visualizing stress detection results from Cassandra.

## Architecture
```
Cassandra (voz_classified_posts) → Streamlit → Browser (localhost:8501)
```

## Tasks

### 5.1 Streamlit Setup
- [ ] Dockerfile with streamlit + cassandra-driver
- [ ] Docker Compose service
- [ ] Health check endpoint

### 5.2 Cassandra Connection
- [ ] Connection pooling
- [ ] Query functions
- [ ] Caching (TTL 30s)

### 5.3 Dashboard Pages
- [ ] Overview (real-time stats)
- [ ] Aspect Trends (time-series)
- [ ] Post Explorer (search/filter)
- [ ] Demographics (charts)

### 5.4 Visualizations
- [ ] Real-time post counter
- [ ] Aspect distribution pie chart
- [ ] Hourly trend line chart
- [ ] Aspect co-occurrence heatmap
- [ ] Recent posts table

### 5.5 Interactivity
- [ ] Time range selector
- [ ] Aspect filter
- [ ] Post search
- [ ] Auto-refresh (30s)

## Dashboard Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Vietnamese Stress Detection Dashboard                       │
├─────────────────────────────────────────────────────────────┤
│  [Overview] [Trends] [Posts] [Demographics]                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │ Total Posts  │ │ Stress Posts │ │  Avg Aspects │        │
│  │    12,345    │ │    8,901     │ │     1.8      │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
│                                                              │
│  ┌─────────────────────────┐ ┌─────────────────────────┐    │
│  │   Aspect Distribution   │ │    Hourly Trend        │    │
│  │      [Pie Chart]        │ │    [Line Chart]        │    │
│  │                         │ │                         │    │
│  └─────────────────────────┘ └─────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Recent Posts                            │    │
│  │  ┌────┬─────────────┬──────────┬─────────────────┐  │    │
│  │  │ ID │ Text        │ Aspects  │ Time            │  │    │
│  │  ├────┼─────────────┼──────────┼─────────────────┤  │    │
│  │  │... │ ...         │ ...      │ ...             │  │    │
│  │  └────┴─────────────┴──────────┴─────────────────┘  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Files Structure

```
streamlit_app/
  app.py                    # Main Streamlit app
  pages/
    1_overview.py           # Real-time overview
    2_trends.py             # Time-series analysis
    3_posts.py              # Post explorer
    4_demographics.py       # Demographic charts
  components/
    metrics.py              # Metric cards
    charts.py               # Chart components
    tables.py               # Data tables
  utils/
    cassandra_client.py     # DB connection
    queries.py              # CQL queries
    cache.py                # Caching layer
  config.py                 # App configuration
  Dockerfile                # Container setup
  requirements.txt          # Dependencies
```

## Cassandra Queries

```python
# utils/queries.py

# Total posts count (last 24h)
TOTAL_POSTS = """
    SELECT COUNT(*) FROM voz_classified_posts
    WHERE hour_bucket IN ?
"""

# Stress posts count
STRESS_POSTS = """
    SELECT COUNT(*) FROM voz_classified_posts
    WHERE hour_bucket IN ? AND stress_label = true
    ALLOW FILTERING
"""

# Aspect distribution (from counter table)
ASPECT_COUNTS = """
    SELECT aspect_id, count FROM voz_aspect_hourly
    WHERE hour_bucket IN ?
"""

# Recent posts
RECENT_POSTS = """
    SELECT post_id, text, aspects, confidence, classified_at
    FROM voz_classified_posts
    WHERE hour_bucket = ?
    ORDER BY classified_at DESC
    LIMIT ?
"""

# Hourly trend
HOURLY_TREND = """
    SELECT hour_bucket, aspect_id, count
    FROM voz_aspect_hourly
    WHERE hour_bucket IN ?
"""

# Demographics
DEMOGRAPHICS = """
    SELECT demographic_type, value, count
    FROM voz_demographics_daily
    WHERE day_bucket = ? AND demographic_type = ?
"""
```

## Streamlit App Structure

```python
# streamlit_app/app.py
import streamlit as st
from utils.cassandra_client import get_session
from utils.queries import *

st.set_page_config(
    page_title="VOZ Stress Detection",
    page_icon="🧠",
    layout="wide"
)

# Sidebar
st.sidebar.title("Filters")
time_range = st.sidebar.selectbox(
    "Time Range",
    ["Last Hour", "Last 24 Hours", "Last 7 Days"]
)
aspects = st.sidebar.multiselect(
    "Aspects",
    ASPECT_NAMES,
    default=ASPECT_NAMES
)

# Main content
st.title("Vietnamese Stress Detection Dashboard")

# Metrics row
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Posts", total_posts, delta=delta_1h)
with col2:
    st.metric("Stress Detected", stress_posts, delta=stress_delta)
with col3:
    st.metric("Avg Aspects/Post", avg_aspects)

# Charts row
col1, col2 = st.columns(2)
with col1:
    st.subheader("Aspect Distribution")
    fig = px.pie(aspect_df, values='count', names='aspect')
    st.plotly_chart(fig)
with col2:
    st.subheader("Hourly Trend")
    fig = px.line(trend_df, x='hour', y='count', color='aspect')
    st.plotly_chart(fig)

# Recent posts table
st.subheader("Recent Posts")
st.dataframe(
    posts_df[['text', 'aspects', 'confidence', 'classified_at']],
    use_container_width=True
)

# Auto-refresh
st.empty()
time.sleep(30)
st.rerun()
```

## Visualization Components

### Aspect Names Mapping

```python
ASPECT_NAMES = {
    0: "Work Stress",
    1: "Financial Anxiety",
    2: "Relationship Issues",
    3: "Academic Pressure",
    4: "Exhaustion",
    5: "Depression",
    6: "Loneliness",
    7: "Health Concerns",
    8: "Family Conflict",
    9: "Future Uncertainty"
}

ASPECT_COLORS = {
    0: "#FF6B6B",  # Red
    1: "#4ECDC4",  # Teal
    2: "#FF69B4",  # Pink
    3: "#45B7D1",  # Blue
    4: "#96CEB4",  # Green
    5: "#2C3E50",  # Dark
    6: "#9B59B6",  # Purple
    7: "#F39C12",  # Orange
    8: "#E74C3C",  # Dark Red
    9: "#3498DB"   # Light Blue
}
```

### Chart Examples

```python
# Pie chart - Aspect distribution
import plotly.express as px

fig = px.pie(
    df,
    values='count',
    names='aspect_name',
    color='aspect_name',
    color_discrete_map=ASPECT_COLORS,
    title='Stress Aspect Distribution'
)
st.plotly_chart(fig, use_container_width=True)

# Line chart - Hourly trend
fig = px.line(
    df,
    x='hour',
    y='count',
    color='aspect_name',
    title='Stress Trends (Last 24 Hours)'
)
fig.update_layout(xaxis_title='Hour', yaxis_title='Post Count')
st.plotly_chart(fig, use_container_width=True)

# Heatmap - Aspect co-occurrence
fig = px.imshow(
    cooccurrence_matrix,
    labels=dict(x="Aspect", y="Aspect", color="Co-occurrence"),
    x=ASPECT_NAMES.values(),
    y=ASPECT_NAMES.values(),
    title='Aspect Co-occurrence Matrix'
)
st.plotly_chart(fig, use_container_width=True)
```

## Docker Configuration

```dockerfile
# streamlit_app/Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

```txt
# streamlit_app/requirements.txt
streamlit==1.29.0
cassandra-driver==3.28.0
plotly==5.18.0
pandas==2.1.0
python-dateutil==2.8.2
```

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| Cassandra unavailable | Show error banner, retry connection |
| No data in time range | Show "No data" message |
| Empty hour bucket | Skip in aggregation |
| Very long post text | Truncate to 200 chars in table |
| Browser refresh | Maintain filter state in session |
| Slow query | Show loading spinner, cache results |
| Many concurrent users | Connection pooling, caching |
| Timezone issues | Display in user's local timezone |
| Chart overflow | Limit data points, paginate |
| Mobile view | Responsive layout, collapse sidebar |

## Caching Strategy

```python
# utils/cache.py
import streamlit as st
from datetime import datetime, timedelta

@st.cache_data(ttl=30)  # Cache for 30 seconds
def get_total_posts(hour_buckets):
    return execute_query(TOTAL_POSTS, hour_buckets)

@st.cache_data(ttl=60)  # Cache for 1 minute
def get_aspect_distribution(hour_buckets):
    return execute_query(ASPECT_COUNTS, hour_buckets)

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_demographics(day_bucket):
    return execute_query(DEMOGRAPHICS, day_bucket)
```

## Validation Criteria

- [ ] Dashboard loads in < 3 seconds
- [ ] All charts render correctly
- [ ] Real-time data updates every 30s
- [ ] Filters work as expected
- [ ] Post search returns results
- [ ] Mobile-responsive layout
- [ ] Handles Cassandra connection loss gracefully
- [ ] No JavaScript errors in console
- [ ] Health check endpoint responds

## Performance Targets

| Metric | Target |
|--------|--------|
| Initial load | < 3 seconds |
| Chart render | < 1 second |
| Query response | < 500ms |
| Auto-refresh | 30 seconds |
| Memory usage | < 512MB |
| Concurrent users | > 10 |

## Access URLs

| Service | URL |
|---------|-----|
| Streamlit Dashboard | http://localhost:8501 |
| Kafka UI | http://localhost:8080 |
| Grafana | http://localhost:3000 |
| Spark UI | http://localhost:4040 |
