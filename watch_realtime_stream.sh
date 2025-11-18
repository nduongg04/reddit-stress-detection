#!/bin/bash

echo "╔════════════════════════════════════════════════════════════╗"
echo "║   Real-Time Reddit → Kafka → Spark → Cassandra Stream     ║"
echo "╚════════════════════════════════════════════════════════════╗"
echo ""
echo "📊 Flow: Reddit → Kafka → Spark (ML v4) → Cassandra"
echo ""
echo "Watching Spark process posts in real-time..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Watch Spark stream log for batch processing
docker exec reddit-spark-master tail -f /tmp/spark_stream.log 2>/dev/null | grep --line-buffered -E "\[Batch [0-9]+\]|Processing [0-9]+ records|Stress detected|Written to|✓ Batch|stress_score"
