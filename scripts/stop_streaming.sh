#!/bin/bash
# Stop VOZ Stress Classification Streaming Pipeline

echo "Stopping VOZ Stress Classification Pipeline..."

# Stop Spark first
docker-compose stop spark-master
docker-compose rm -f spark-master

echo "✓ Spark stopped"

# Optionally stop all
if [ "$1" = "--all" ]; then
    echo "Stopping all infrastructure..."
    docker-compose down
    echo "✓ All services stopped"
else
    echo ""
    echo "Kafka and Cassandra still running."
    echo "To stop all: ./scripts/stop_streaming.sh --all"
fi
