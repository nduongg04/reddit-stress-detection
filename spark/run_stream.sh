#!/bin/bash

# Submit Spark Streaming Application (JARs pre-installed)
# Usage: ./run_stream.sh [env] [mode]

ENV=${1:-dev}
MODE=${2:-console}

echo "=========================================="
echo "Reddit Stream Processor"
echo "=========================================="
echo "Environment: $ENV"
echo "Mode: $MODE"
echo ""

# Check if Kafka is running and has data
echo "Pre-flight checks..."
echo -n "  Kafka running: "
if docker ps | grep -q reddit-kafka; then
    echo "✓"
else
    echo "✗ (Start with: docker-compose up -d)"
    exit 1
fi

echo -n "  Spark running: "
if docker ps | grep -q reddit-spark-master; then
    echo "✓"
else
    echo "✗ (Start with: docker-compose up -d)"
    exit 1
fi

if [ "$MODE" = "cassandra" ]; then
    echo -n "  Cassandra running: "
    if docker ps | grep -q reddit-cassandra; then
        echo "✓"
    else
        echo "✗ (Start with: docker-compose up -d)"
        exit 1
    fi
fi

echo ""
echo "Starting Spark Streaming job..."
echo "  → Reading from Kafka topic: reddit-posts"
if [ "$MODE" = "cassandra" ]; then
    echo "  → Writing to: Cassandra (raw_posts_by_day)"
else
    echo "  → Writing to: Console (testing)"
fi
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Submit job (JARs already in /opt/spark/jars, no need for --packages)
docker exec reddit-spark-master \
  /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --conf spark.sql.shuffle.partitions=6 \
  --conf spark.executor.memory=2g \
  --conf spark.driver.memory=1g \
  --conf spark.executor.cores=2 \
  --conf spark.sql.streaming.checkpointLocation=/tmp/spark_checkpoints \
  /opt/spark-apps/streaming/reddit_stream_processor.py \
  --env $ENV \
  --mode $MODE

EXIT_CODE=$?

echo ""
echo "=========================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ Spark job completed successfully"
else
    echo "✗ Spark job failed (exit code: $EXIT_CODE)"
fi
echo "=========================================="

exit $EXIT_CODE
