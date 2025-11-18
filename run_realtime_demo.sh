#!/bin/bash

echo "╔════════════════════════════════════════════════════════════╗"
echo "║   Real-Time Reddit Stress Detection - Live Monitoring      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Function to get count
get_count() {
    docker exec reddit-cassandra cqlsh -e "SELECT COUNT(*) FROM reddit_rt.classified_posts_by_hour;" 2>/dev/null | grep -E "^[[:space:]]*[0-9]+" | tr -d ' '
}

# Function to get latest post
get_latest() {
    docker exec reddit-cassandra cqlsh -e "SELECT subreddit, stress_score, stress_label FROM reddit_rt.classified_posts_by_hour LIMIT 1;" 2>/dev/null | tail -3 | head -1
}

echo "📊 Starting Count: $(get_count)"
echo ""
echo "⏳ Monitoring every 10 seconds (Press Ctrl+C to stop)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

PREV=$(get_count)

while true; do
    sleep 10
    
    CURR=$(get_count)
    TIME=$(date '+%H:%M:%S')
    DIFF=$((CURR - PREV))
    
    if [ $DIFF -gt 0 ]; then
        echo "[$TIME] ✅ NEW: $DIFF post(s) classified | Total: $CURR"
        echo "           Latest: $(get_latest)"
    else
        echo "[$TIME] ⏸️  Waiting for new Reddit posts..."
    fi
    
    PREV=$CURR
done
