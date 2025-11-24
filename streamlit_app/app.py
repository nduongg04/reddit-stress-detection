#!/usr/bin/env python3
"""
Streamlit Dashboard for Vietnamese ABSA Mental Health Detection
Real-time visualization of aspect-based sentiment analysis results
"""
import streamlit as st
import pandas as pd
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
from collections import Counter, defaultdict
import time

# Page configuration
st.set_page_config(
    page_title="Vietnamese Mental Health ABSA Dashboard",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Cassandra connection
@st.cache_resource
def get_cassandra_session():
    """Connect to Cassandra cluster"""
    try:
        cluster = Cluster(['cassandra'], port=9042)
        session = cluster.connect('reddit_rt')
        return session
    except Exception as e:
        st.error(f"Failed to connect to Cassandra: {e}")
        return None

# Load ABSA aspects definition
@st.cache_data
def load_aspects():
    """Load aspect definitions"""
    try:
        with open('/opt/ml/lda/absa_mental_health_aspects.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data['aspects']
    except:
        # Fallback aspect names
        return [
            {'aspect_name': 'công_việc', 'keywords': ['work', 'job']},
            {'aspect_name': 'học_tập', 'keywords': ['study', 'school']},
            {'aspect_name': 'tình_yêu', 'keywords': ['love', 'relationship']},
            {'aspect_name': 'gia_đình', 'keywords': ['family']},
            {'aspect_name': 'sức_khỏe', 'keywords': ['health']},
            {'aspect_name': 'tài_chính', 'keywords': ['money', 'finance']},
            {'aspect_name': 'xã_hội', 'keywords': ['social']},
            {'aspect_name': 'tự_suy_ngẫm', 'keywords': ['self-reflection']},
            {'aspect_name': 'căng_thẳng_tài_chính', 'keywords': ['financial stress']},
            {'aspect_name': 'cô_đơn', 'keywords': ['loneliness']}
        ]

# Fetch data from Cassandra
@st.cache_data(ttl=30)
def fetch_recent_posts(_session, limit=100):
    """Fetch recent classified posts"""
    query = """
    SELECT subreddit, hour_partition, created_utc, post_id, title, body,
           aspect_sentiments, model_version, processed_ts
    FROM classified_posts_by_hour
    LIMIT %s
    """
    try:
        rows = _session.execute(query, [limit])
        # Convert Cassandra Row objects to dictionaries for serialization
        return [
            {
                'subreddit': r.subreddit,
                'hour_partition': r.hour_partition,
                'created_utc': r.created_utc,
                'post_id': r.post_id,
                'title': r.title,
                'body': r.body,
                'aspect_sentiments': dict(r.aspect_sentiments) if r.aspect_sentiments else None,
                'model_version': r.model_version,
                'processed_ts': r.processed_ts
            }
            for r in rows
        ]
    except Exception as e:
        st.error(f"Error fetching posts: {e}")
        return []

@st.cache_data(ttl=60)
def fetch_posts_by_timerange(_session, hours_back=24):
    """Fetch posts from last N hours"""
    # Note: This is a simplified query. In production, you'd filter by partition
    query = """
    SELECT subreddit, hour_partition, created_utc, post_id, title, body,
           aspect_sentiments, model_version, processed_ts
    FROM classified_posts_by_hour
    LIMIT 1000
    """
    try:
        rows = _session.execute(query)

        # Filter by time in Python (since we can't efficiently filter in CQL without partition key)
        cutoff = datetime.utcnow() - timedelta(hours=hours_back)
        filtered = [r for r in rows if r.processed_ts and r.processed_ts >= cutoff]

        # Convert Cassandra Row objects to dictionaries for serialization
        return [
            {
                'subreddit': r.subreddit,
                'hour_partition': r.hour_partition,
                'created_utc': r.created_utc,
                'post_id': r.post_id,
                'title': r.title,
                'body': r.body,
                'aspect_sentiments': dict(r.aspect_sentiments) if r.aspect_sentiments else None,
                'model_version': r.model_version,
                'processed_ts': r.processed_ts
            }
            for r in filtered
        ]
    except Exception as e:
        st.error(f"Error fetching posts: {e}")
        return []

def process_aspect_statistics(posts):
    """Calculate aspect sentiment statistics"""
    aspect_counts = defaultdict(lambda: {'positive': 0, 'negative': 0, 'total': 0})

    for post in posts:
        if post['aspect_sentiments']:
            for aspect, sentiment in post['aspect_sentiments'].items():
                aspect_counts[aspect]['total'] += 1
                if sentiment > 0:
                    aspect_counts[aspect]['positive'] += 1
                elif sentiment < 0:
                    aspect_counts[aspect]['negative'] += 1

    return aspect_counts

# Main app
def main():
    st.title("🧠 Vietnamese Mental Health ABSA Dashboard")
    st.markdown("Real-time Aspect-Based Sentiment Analysis for Reddit Posts")

    # Sidebar
    st.sidebar.header("Configuration")

    # Time range selector
    time_range = st.sidebar.selectbox(
        "Time Range",
        ["Last Hour", "Last 6 Hours", "Last 24 Hours", "Last 100 Posts"],
        index=2
    )

    # Refresh rate
    auto_refresh = st.sidebar.checkbox("Auto-refresh (30s)", value=False)

    if auto_refresh:
        st.sidebar.info("Auto-refreshing every 30 seconds...")
        time.sleep(30)
        st.rerun()

    # Manual refresh button
    if st.sidebar.button("🔄 Refresh Now"):
        st.cache_data.clear()
        st.rerun()

    # Connect to Cassandra
    session = get_cassandra_session()
    if not session:
        st.error("Cannot connect to Cassandra. Please check the connection.")
        return

    aspects = load_aspects()

    # Fetch data based on time range
    with st.spinner("Loading data..."):
        if time_range == "Last 100 Posts":
            posts = fetch_recent_posts(session, limit=100)
        else:
            hours = {
                "Last Hour": 1,
                "Last 6 Hours": 6,
                "Last 24 Hours": 24
            }[time_range]
            posts = fetch_posts_by_timerange(session, hours_back=hours)

    if not posts:
        st.warning("No data available yet. Please wait for posts to be processed.")
        return

    # Calculate statistics
    aspect_stats = process_aspect_statistics(posts)

    # Display metrics
    st.header("📊 Overview")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Posts", len(posts))

    with col2:
        posts_with_sentiments = sum(1 for p in posts if p['aspect_sentiments'])
        st.metric("Posts with Sentiments", posts_with_sentiments)

    with col3:
        total_aspects = sum(len(p['aspect_sentiments']) for p in posts if p['aspect_sentiments'])
        st.metric("Total Aspects Detected", total_aspects)

    with col4:
        negative_posts = sum(
            1 for p in posts
            if p['aspect_sentiments'] and any(s < 0 for s in p['aspect_sentiments'].values())
        )
        st.metric("Posts with Stress", negative_posts)

    # Aspect Statistics Charts
    st.header("📈 Aspect-Based Sentiment Statistics")

    if aspect_stats:
        # Prepare data for charts
        aspect_names = list(aspect_stats.keys())
        positive_counts = [aspect_stats[a]['positive'] for a in aspect_names]
        negative_counts = [aspect_stats[a]['negative'] for a in aspect_names]
        total_counts = [aspect_stats[a]['total'] for a in aspect_names]

        # Chart 1: Stacked Bar Chart (Positive vs Negative)
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Sentiment Distribution by Aspect")
            fig1 = go.Figure(data=[
                go.Bar(name='Negative', x=aspect_names, y=negative_counts, marker_color='#ff4b4b'),
                go.Bar(name='Positive', x=aspect_names, y=positive_counts, marker_color='#00cc66')
            ])
            fig1.update_layout(
                barmode='stack',
                xaxis_tickangle=-45,
                height=400,
                xaxis_title="Aspect",
                yaxis_title="Count"
            )
            st.plotly_chart(fig1, use_container_width=True)

        with col2:
            st.subheader("Total Mentions per Aspect")
            fig2 = px.bar(
                x=aspect_names,
                y=total_counts,
                labels={'x': 'Aspect', 'y': 'Total Mentions'},
                color=total_counts,
                color_continuous_scale='Blues'
            )
            fig2.update_layout(
                xaxis_tickangle=-45,
                height=400,
                showlegend=False
            )
            st.plotly_chart(fig2, use_container_width=True)

        # Chart 2: Sentiment Ratio
        st.subheader("Negative Sentiment Ratio by Aspect")

        ratios = []
        for aspect in aspect_names:
            total = aspect_stats[aspect]['total']
            neg = aspect_stats[aspect]['negative']
            ratio = (neg / total * 100) if total > 0 else 0
            ratios.append(ratio)

        fig3 = px.bar(
            x=aspect_names,
            y=ratios,
            labels={'x': 'Aspect', 'y': 'Negative Sentiment (%)'},
            color=ratios,
            color_continuous_scale='Reds'
        )
        fig3.update_layout(
            xaxis_tickangle=-45,
            height=400
        )
        st.plotly_chart(fig3, use_container_width=True)

        # Chart 3: Pie chart of total aspect distribution
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Aspect Distribution")
            fig4 = px.pie(
                values=total_counts,
                names=aspect_names,
                hole=0.3
            )
            st.plotly_chart(fig4, use_container_width=True)

        with col2:
            st.subheader("Sentiment Balance")
            total_positive = sum(positive_counts)
            total_negative = sum(negative_counts)
            fig5 = px.pie(
                values=[total_positive, total_negative],
                names=['Positive', 'Negative'],
                color=['Positive', 'Negative'],
                color_discrete_map={'Positive': '#00cc66', 'Negative': '#ff4b4b'}
            )
            st.plotly_chart(fig5, use_container_width=True)

    else:
        st.info("No aspect sentiments detected yet.")

    # Recent Posts Table
    st.header("📝 Recent Processed Posts")

    # Filter options
    col1, col2, col3 = st.columns(3)

    with col1:
        filter_sentiment = st.selectbox(
            "Filter by Sentiment",
            ["All", "Negative Only", "Positive Only", "Neutral Only"]
        )

    with col2:
        filter_aspect = st.selectbox(
            "Filter by Aspect",
            ["All"] + [a['aspect_name'] for a in aspects]
        )

    with col3:
        show_body = st.checkbox("Show Post Body", value=False)

    # Apply filters
    filtered_posts = posts.copy()

    if filter_sentiment == "Negative Only":
        filtered_posts = [
            p for p in filtered_posts
            if p['aspect_sentiments'] and any(s < 0 for s in p['aspect_sentiments'].values())
        ]
    elif filter_sentiment == "Positive Only":
        filtered_posts = [
            p for p in filtered_posts
            if p['aspect_sentiments'] and any(s > 0 for s in p['aspect_sentiments'].values())
        ]
    elif filter_sentiment == "Neutral Only":
        filtered_posts = [p for p in filtered_posts if not p['aspect_sentiments']]

    if filter_aspect != "All":
        filtered_posts = [
            p for p in filtered_posts
            if p['aspect_sentiments'] and filter_aspect in p['aspect_sentiments']
        ]

    # Display posts
    st.write(f"Showing {len(filtered_posts)} posts")

    for i, post in enumerate(filtered_posts[:50]):  # Limit to 50 for performance
        with st.expander(f"**{post['subreddit']}** - {post['title'] or '(No title)'}"):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.write(f"**Post ID:** {post['post_id']}")
                st.write(f"**Created:** {post['created_utc']}")
                st.write(f"**Processed:** {post['processed_ts']}")

                if post['aspect_sentiments']:
                    st.write("**Detected Aspects:**")
                    for aspect, sentiment in post['aspect_sentiments'].items():
                        sentiment_emoji = "😟" if sentiment < 0 else "😊" if sentiment > 0 else "😐"
                        sentiment_text = "Negative" if sentiment < 0 else "Positive" if sentiment > 0 else "Neutral"
                        st.write(f"  - {aspect}: {sentiment_emoji} {sentiment_text}")
                else:
                    st.write("**No aspects detected** (neutral post)")

                if show_body and post['body']:
                    st.write("---")
                    st.write(f"**Body:** {post['body'][:500]}{'...' if len(post['body']) > 500 else ''}")

            with col2:
                st.write(f"**Model:** {post['model_version'] or 'N/A'}")
                st.write(f"**Hour:** {post['hour_partition']}")

    # Footer
    st.markdown("---")
    st.markdown(f"**Last updated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    st.markdown("**Data source:** Cassandra `reddit_rt.classified_posts_by_hour`")

if __name__ == "__main__":
    main()
