#!/usr/bin/env python3
"""
Streamlit Dashboard for Vietnamese Stress Detection
Real-time visualization of VOZ posts with stress aspects and demographics
"""
import streamlit as st
import pandas as pd
from cassandra.cluster import Cluster
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np
from streamlit_autorefresh import st_autorefresh

# Page configuration
st.set_page_config(
    page_title="Vietnamese Stress Detection Dashboard",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Aspect definitions
ASPECTS = [
    {"id": 0, "name_en": "Occupational", "name_vi": "Công việc", "color": "#3498db"},
    {"id": 1, "name_en": "Financial", "name_vi": "Tài chính", "color": "#2ecc71"},
    {"id": 2, "name_en": "Academic", "name_vi": "Học tập", "color": "#e74c3c"},
    {"id": 3, "name_en": "Familial", "name_vi": "Gia đình", "color": "#9b59b6"},
    {"id": 4, "name_en": "Health", "name_vi": "Sức khỏe", "color": "#e67e22"},
    {"id": 5, "name_en": "Romantic", "name_vi": "Tình cảm", "color": "#1abc9c"},
    {"id": 6, "name_en": "Existential", "name_vi": "Hiện sinh", "color": "#34495e"},
    {"id": 7, "name_en": "Social", "name_vi": "Xã hội", "color": "#f39c12"},
    {"id": 8, "name_en": "Life Events", "name_vi": "Sự kiện", "color": "#d35400"},
    {"id": 9, "name_en": "Self Image", "name_vi": "Hình ảnh bản thân", "color": "#c0392b"},
]

ASPECT_COLORS = {a["id"]: a["color"] for a in ASPECTS}
ASPECT_NAMES = {a["id"]: f"{a['name_vi']} ({a['name_en']})" for a in ASPECTS}

# Demographics labels - Note: Current PhoBERT model only predicts stress aspects, not demographics
# Demographics will show as "unknown" until LLM inference is added
GENDER_LABELS = {"nam": "Nam", "nữ": "Nữ", "unknown": "Không rõ", None: "Không rõ", "": "Không rõ"}
AGE_LABELS = {
    "teen": "13-17 tuổi",
    "young_adult": "18-25 tuổi",
    "adult": "26-40 tuổi",
    "middle_aged": "41-60 tuổi",
    "senior": "60+ tuổi",
    "unknown": "Không rõ",
    None: "Không rõ",
    "": "Không rõ"
}
OCCUPATION_LABELS = {
    "student": "Học sinh/Sinh viên",
    "office_worker": "Nhân viên văn phòng",
    "it_engineer": "IT/Kỹ sư",
    "healthcare": "Y tế",
    "teacher": "Giáo viên",
    "blue_collar": "Công nhân",
    "freelance": "Tự do",
    "unemployed": "Thất nghiệp",
    "unknown": "Không rõ",
    None: "Không rõ",
    "": "Không rõ"
}
RELATIONSHIP_LABELS = {
    "single": "Độc thân",
    "dating": "Đang hẹn hò",
    "married": "Đã kết hôn",
    "divorced": "Ly hôn",
    "unknown": "Không rõ",
    None: "Không rõ",
    "": "Không rõ"
}


@st.cache_resource
def get_cassandra_session():
    """Connect to Cassandra cluster"""
    try:
        # Try Docker network first, then localhost
        hosts = ["cassandra", "localhost"]
        for host in hosts:
            try:
                cluster = Cluster([host], port=9042)
                session = cluster.connect("reddit_rt")
                return session
            except Exception:
                continue
        st.error("Cannot connect to Cassandra")
        return None
    except Exception as e:
        st.error(f"Cassandra connection error: {e}")
        return None


@st.cache_data(ttl=10)
def fetch_recent_posts(_session, limit=50, hours_back=24):
    """Fetch recent classified VOZ posts by scanning recent hour buckets"""
    posts = []
    now = datetime.utcnow()

    # Query each hour bucket for the last N hours
    for i in range(hours_back):
        hour_bucket = (now - timedelta(hours=i)).strftime("%Y-%m-%d-%H")
        query = """
        SELECT hour_bucket, classified_at, post_id, text, url, source,
               aspects, aspect_probs, confidence, stress_label, reasoning,
               gender, age_group, occupation, relationship,
               model_version, processing_time_ms
        FROM voz_classified_posts
        WHERE hour_bucket = %s
        LIMIT %s
        """
        try:
            rows = _session.execute(query, [hour_bucket, limit])
            for r in rows:
                posts.append({
                    "hour_bucket": r.hour_bucket,
                    "classified_at": r.classified_at,
                    "post_id": r.post_id,
                    "text": r.text,
                    "url": r.url,
                    "aspects": list(r.aspects) if r.aspects else [],
                    "confidence": r.confidence or 0.0,
                    "stress_label": r.stress_label,
                    "reasoning": r.reasoning,
                    "gender": r.gender or "unknown",
                    "age_group": r.age_group or "unknown",
                    "occupation": r.occupation or "unknown",
                    "relationship": r.relationship or "unknown",
                    "model_version": r.model_version,
                    "processing_time_ms": r.processing_time_ms or 0,
                })
            if len(posts) >= limit:
                break
        except Exception as e:
            continue

    return sorted(posts, key=lambda x: x["classified_at"] or datetime.min, reverse=True)[:limit]


def compute_aspect_stats(posts):
    """Compute aspect distribution statistics"""
    aspect_counts = defaultdict(int)
    for post in posts:
        for aspect_id in post.get("aspects", []):
            aspect_counts[aspect_id] += 1
    return aspect_counts


def compute_demographic_stats(posts, field):
    """Compute demographic distribution"""
    counts = defaultdict(int)
    for post in posts:
        value = post.get(field, "unknown")
        counts[value] += 1
    return counts


def compute_demographic_stress_stats(posts, field):
    """Compute demographic distribution with stress breakdown"""
    stats = defaultdict(lambda: {"total": 0, "stress": 0, "non_stress": 0})
    for post in posts:
        value = post.get(field, "unknown")
        stats[value]["total"] += 1
        if post.get("stress_label"):
            stats[value]["stress"] += 1
        else:
            stats[value]["non_stress"] += 1
    return stats


def compute_demographic_aspect_stats(posts, field):
    """Compute which aspects each demographic group stresses about (only stressed posts)"""
    stats = defaultdict(lambda: defaultdict(int))
    totals = defaultdict(int)
    for post in posts:
        if post.get("stress_label"):  # Only count stressed posts
            value = post.get(field, "unknown")
            totals[value] += 1
            for aspect_id in post.get("aspects", []):
                if 0 <= aspect_id < 10:
                    stats[value][aspect_id] += 1
    return stats, totals


def compute_cooccurrence_matrix(posts):
    """Compute 10x10 aspect co-occurrence matrix"""
    matrix = np.zeros((10, 10))
    for post in posts:
        aspects = post.get("aspects", [])
        for i in aspects:
            for j in aspects:
                if 0 <= i < 10 and 0 <= j < 10:
                    matrix[i][j] += 1
    return matrix


def render_post_card(post, idx):
    """Render a single post card with collapsible full content"""
    # Build header with stress badge and time
    stress_badge = "🔴" if post["stress_label"] else "🟢"
    time_str = post["classified_at"].strftime("%H:%M") if post["classified_at"] else ""

    # Aspect chips for header
    aspects = post.get("aspects", [])
    aspect_names = [ASPECTS[a]["name_vi"] for a in aspects if 0 <= a < 10]
    aspects_str = ", ".join(aspect_names[:3]) if aspect_names else "No stress detected"
    if len(aspect_names) > 3:
        aspects_str += f" +{len(aspect_names) - 3}"

    # Text preview (first 100 chars)
    full_text = post.get("text", "")
    preview_text = full_text[:100] + "..." if len(full_text) > 100 else full_text

    # Create expander with summary as header
    header = f"{stress_badge} **#{idx + 1}** {preview_text}"

    with st.expander(header, expanded=False):
        # Full text
        st.markdown("**Full Text:**")
        st.markdown(f"_{full_text}_")

        st.markdown("---")

        # Aspect chips with colors
        if aspects:
            st.markdown("**Stress Aspects:**")
            chips_html = " ".join([
                f'<span style="background-color:{ASPECT_COLORS.get(a, "#999")};color:white;padding:4px 12px;border-radius:12px;margin:2px;font-size:13px;">{ASPECT_NAMES.get(a, f"Aspect {a}")}</span>'
                for a in aspects if 0 <= a < 10
            ])
            st.markdown(chips_html, unsafe_allow_html=True)
        else:
            st.markdown("**Stress Aspects:** None detected")

        # Confidence
        conf = post.get("confidence", 0)
        if conf > 0:
            st.markdown(f"**Confidence:** {conf*100:.1f}%")

        # Metadata
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.caption(f"Post ID: {post['post_id']}")
            st.caption(f"Model: {post.get('model_version', 'N/A')}")
        with col2:
            st.caption(f"Time: {time_str}")
            if post.get("url"):
                st.caption(f"[View on VOZ]({post['url']})")


def main():
    st.title("🧠 Vietnamese Stress Detection Dashboard")
    st.markdown("Real-time analysis of VOZ.vn posts with LLM-based stress detection and demographics")

    # Sidebar
    st.sidebar.header("⚙️ Settings")

    # Auto-refresh interval selection
    refresh_interval = st.sidebar.selectbox(
        "Auto-refresh",
        options=[0, 5, 10, 30],
        index=2,
        format_func=lambda x: "Off" if x == 0 else f"Every {x}s"
    )

    # Auto-refresh component (smooth, no gray overlay)
    if refresh_interval > 0:
        st_autorefresh(interval=refresh_interval * 1000, limit=None, key="data_refresh")

    # Manual refresh
    if st.sidebar.button("🔄 Refresh Now"):
        st.cache_data.clear()
        st.rerun()

    # Filters
    st.sidebar.header("🔍 Filters")

    filter_stress = st.sidebar.selectbox(
        "Stress Status",
        ["All", "Stress Only", "Non-Stress Only"]
    )

    filter_aspects = st.sidebar.multiselect(
        "Aspects",
        options=list(range(10)),
        format_func=lambda x: ASPECT_NAMES.get(x, f"Aspect {x}")
    )

    filter_gender = st.sidebar.selectbox(
        "Gender",
        ["All", "nam", "nữ", "unknown"],
        format_func=lambda x: GENDER_LABELS.get(x, x) if x != "All" else "All"
    )

    filter_occupation = st.sidebar.selectbox(
        "Occupation",
        ["All"] + list(OCCUPATION_LABELS.keys()),
        format_func=lambda x: OCCUPATION_LABELS.get(x, x) if x != "All" else "All"
    )

    # Connect to Cassandra
    session = get_cassandra_session()
    if not session:
        st.error("Cannot connect to database. Please check Cassandra is running.")
        st.info("Run: `docker-compose up -d cassandra`")
        return

    # Fetch data
    with st.spinner("Loading data..."):
        posts = fetch_recent_posts(session, limit=200)

    if not posts:
        st.warning("No data yet. Start the pipeline:")
        st.code("""
# 1. Initialize Kafka topic
./scripts/init-kafka-topics.sh

# 2. Start VOZ producer
python producers/voz_kafka_producer.py --target 50

# 3. Start Spark streaming (in Docker)
docker exec -it reddit-spark-master spark-submit /opt/spark-apps/voz_streaming_pipeline.py
        """)
        return

    # Apply filters
    filtered_posts = posts.copy()

    if filter_stress == "Stress Only":
        filtered_posts = [p for p in filtered_posts if p["stress_label"]]
    elif filter_stress == "Non-Stress Only":
        filtered_posts = [p for p in filtered_posts if not p["stress_label"]]

    if filter_aspects:
        filtered_posts = [p for p in filtered_posts if any(a in p["aspects"] for a in filter_aspects)]

    if filter_gender != "All":
        filtered_posts = [p for p in filtered_posts if p["gender"] == filter_gender]

    if filter_occupation != "All":
        filtered_posts = [p for p in filtered_posts if p["occupation"] == filter_occupation]

    # Metrics row
    st.header("📊 Overview")
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total Posts", len(posts))
    with col2:
        stress_count = sum(1 for p in posts if p["stress_label"])
        st.metric("Stress Posts", stress_count, delta=f"{stress_count/len(posts)*100:.1f}%" if posts else "0%")
    with col3:
        known_gender = sum(1 for p in posts if p["gender"] != "unknown")
        st.metric("Known Gender", known_gender)
    with col4:
        avg_time = sum(p["processing_time_ms"] for p in posts) / len(posts) if posts else 0
        st.metric("Avg LLM Time", f"{avg_time:.0f}ms")
    with col5:
        st.metric("Filtered", len(filtered_posts))

    # Charts
    st.header("📈 Analytics")

    tab1, tab2, tab3, tab4 = st.tabs(["Aspects", "Demographics", "Co-occurrence", "Timeline"])

    with tab1:
        col1, col2 = st.columns(2)

        # Aspect distribution bar chart
        aspect_stats = compute_aspect_stats(posts)
        with col1:
            st.subheader("Aspect Distribution")
            if aspect_stats:
                df = pd.DataFrame([
                    {"Aspect": ASPECT_NAMES[i], "Count": aspect_stats.get(i, 0), "Color": ASPECT_COLORS[i]}
                    for i in range(10)
                ])
                fig = px.bar(df, x="Aspect", y="Count", color="Aspect",
                             color_discrete_map={ASPECT_NAMES[i]: ASPECT_COLORS[i] for i in range(10)})
                fig.update_layout(showlegend=False, xaxis_tickangle=-45, height=400)
                st.plotly_chart(fig, use_container_width=True)

        # Aspect pie chart
        with col2:
            st.subheader("Aspect Share")
            if aspect_stats:
                df = pd.DataFrame([
                    {"Aspect": ASPECT_NAMES[i], "Count": aspect_stats.get(i, 0)}
                    for i in range(10) if aspect_stats.get(i, 0) > 0
                ])
                fig = px.pie(df, values="Count", names="Aspect", hole=0.4,
                             color="Aspect",
                             color_discrete_map={ASPECT_NAMES[i]: ASPECT_COLORS[i] for i in range(10)})
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)

    with tab2:
        # What each group stresses about - Main focus of Demographics tab
        st.subheader("🎯 What Each Group Stresses About")
        st.caption("Shows the top stress aspects for each demographic group (% of stressed posts mentioning each aspect)")

        demo_tab1, demo_tab2, demo_tab3, demo_tab4 = st.tabs(["By Gender", "By Age", "By Occupation", "By Relationship"])

        with demo_tab1:
            gender_aspects, gender_totals = compute_demographic_aspect_stats(posts, "gender")
            if gender_aspects:
                rows = []
                for group, aspects in gender_aspects.items():
                    total = gender_totals[group]
                    if total > 0:
                        for asp_id, count in aspects.items():
                            rows.append({
                                "Group": GENDER_LABELS.get(group, group),
                                "Aspect": ASPECT_NAMES[asp_id],
                                "Percentage": count / total * 100,
                                "Count": count
                            })
                if rows:
                    df = pd.DataFrame(rows)
                    fig = px.bar(df, x="Group", y="Percentage", color="Aspect",
                                 color_discrete_map={ASPECT_NAMES[i]: ASPECT_COLORS[i] for i in range(10)},
                                 text=df["Percentage"].apply(lambda x: f"{x:.1f}%"),
                                 barmode="group")
                    fig.update_layout(height=400, title="Stress Aspects by Gender", yaxis_title="% of Stressed Posts")
                    fig.update_traces(textposition="outside")
                    st.plotly_chart(fig, use_container_width=True)

        with demo_tab2:
            age_aspects, age_totals = compute_demographic_aspect_stats(posts, "age_group")
            if age_aspects:
                rows = []
                for group, aspects in age_aspects.items():
                    total = age_totals[group]
                    if total > 0:
                        for asp_id, count in aspects.items():
                            rows.append({
                                "Group": AGE_LABELS.get(group, group),
                                "Aspect": ASPECT_NAMES[asp_id],
                                "Percentage": count / total * 100,
                                "Count": count
                            })
                if rows:
                    df = pd.DataFrame(rows)
                    fig = px.bar(df, x="Group", y="Percentage", color="Aspect",
                                 color_discrete_map={ASPECT_NAMES[i]: ASPECT_COLORS[i] for i in range(10)},
                                 text=df["Percentage"].apply(lambda x: f"{x:.1f}%"),
                                 barmode="group")
                    fig.update_layout(height=400, title="Stress Aspects by Age Group", yaxis_title="% of Stressed Posts")
                    fig.update_traces(textposition="outside")
                    st.plotly_chart(fig, use_container_width=True)

        with demo_tab3:
            occ_aspects, occ_totals = compute_demographic_aspect_stats(posts, "occupation")
            if occ_aspects:
                rows = []
                for group, aspects in occ_aspects.items():
                    total = occ_totals[group]
                    if total > 0:
                        for asp_id, count in aspects.items():
                            rows.append({
                                "Group": OCCUPATION_LABELS.get(group, group),
                                "Aspect": ASPECT_NAMES[asp_id],
                                "Percentage": count / total * 100,
                                "Count": count
                            })
                if rows:
                    df = pd.DataFrame(rows)
                    fig = px.bar(df, x="Group", y="Percentage", color="Aspect",
                                 color_discrete_map={ASPECT_NAMES[i]: ASPECT_COLORS[i] for i in range(10)},
                                 text=df["Percentage"].apply(lambda x: f"{x:.1f}%"),
                                 barmode="group")
                    fig.update_layout(height=400, xaxis_tickangle=-45, title="Stress Aspects by Occupation", yaxis_title="% of Stressed Posts")
                    fig.update_traces(textposition="outside")
                    st.plotly_chart(fig, use_container_width=True)

        with demo_tab4:
            rel_aspects, rel_totals = compute_demographic_aspect_stats(posts, "relationship")
            if rel_aspects:
                rows = []
                for group, aspects in rel_aspects.items():
                    total = rel_totals[group]
                    if total > 0:
                        for asp_id, count in aspects.items():
                            rows.append({
                                "Group": RELATIONSHIP_LABELS.get(group, group),
                                "Aspect": ASPECT_NAMES[asp_id],
                                "Percentage": count / total * 100,
                                "Count": count
                            })
                if rows:
                    df = pd.DataFrame(rows)
                    fig = px.bar(df, x="Group", y="Percentage", color="Aspect",
                                 color_discrete_map={ASPECT_NAMES[i]: ASPECT_COLORS[i] for i in range(10)},
                                 text=df["Percentage"].apply(lambda x: f"{x:.1f}%"),
                                 barmode="group")
                    fig.update_layout(height=400, title="Stress Aspects by Relationship Status", yaxis_title="% of Stressed Posts")
                    fig.update_traces(textposition="outside")
                    st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.subheader("Aspect Co-occurrence Heatmap")
        matrix = compute_cooccurrence_matrix(posts)
        if matrix.sum() > 0:
            labels = [ASPECTS[i]["name_vi"] for i in range(10)]
            fig = go.Figure(data=go.Heatmap(
                z=matrix,
                x=labels,
                y=labels,
                colorscale="RdBu",
                text=matrix.astype(int),
                texttemplate="%{text}",
                textfont={"size": 10},
            ))
            fig.update_layout(height=500, xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Not enough data for co-occurrence analysis")

    with tab4:
        st.subheader("Posts Timeline (by hour)")
        if posts:
            # Group by hour
            hour_counts = defaultdict(lambda: {"total": 0, "stress": 0})
            for p in posts:
                if p["classified_at"]:
                    hour = p["classified_at"].strftime("%Y-%m-%d %H:00")
                    hour_counts[hour]["total"] += 1
                    if p["stress_label"]:
                        hour_counts[hour]["stress"] += 1

            if hour_counts:
                df = pd.DataFrame([
                    {"Hour": k, "Total": v["total"], "Stress": v["stress"]}
                    for k, v in sorted(hour_counts.items())
                ])
                fig = go.Figure()
                fig.add_trace(go.Bar(x=df["Hour"], y=df["Total"], name="Total", marker_color="#3498db"))
                fig.add_trace(go.Bar(x=df["Hour"], y=df["Stress"], name="Stress", marker_color="#e74c3c"))
                fig.update_layout(barmode="overlay", height=400)
                st.plotly_chart(fig, use_container_width=True)

    # Post feed
    st.header(f"📝 Recent Posts ({len(filtered_posts)} shown)")

    for idx, post in enumerate(filtered_posts[:30]):
        render_post_card(post, idx)

    # Footer
    st.markdown("---")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Data source: Cassandra `reddit_rt.voz_classified_posts`")


if __name__ == "__main__":
    main()
