#!/bin/bash
set -e

echo "========================================================================"
echo "  VOZ Producer - Crawl VOZ.vn to Kafka"
echo "========================================================================"
echo "Kafka: ${KAFKA_BOOTSTRAP_SERVERS}"
echo "Topic: ${KAFKA_TOPIC}"
echo "Target: ${TARGET_POSTS} posts"
echo "Delay: ${DELAY}s"
echo "========================================================================"

# Wait for Kafka to be ready
echo "Waiting for Kafka to be ready..."
MAX_RETRIES=30
RETRY=0

while [ $RETRY -lt $MAX_RETRIES ]; do
    if python -c "from confluent_kafka import Producer; p=Producer({'bootstrap.servers':'${KAFKA_BOOTSTRAP_SERVERS}'}); p.flush(1)" 2>/dev/null; then
        echo "✓ Kafka is ready"
        break
    fi
    echo "Waiting for Kafka... (${RETRY}/${MAX_RETRIES})"
    sleep 2
    RETRY=$((RETRY + 1))
done

if [ $RETRY -eq $MAX_RETRIES ]; then
    echo "ERROR: Kafka not available after ${MAX_RETRIES} attempts"
    exit 1
fi

# Build command arguments
ARGS="--target ${TARGET_POSTS} --delay ${DELAY}"

if [ "${CONTINUOUS}" = "true" ]; then
    ARGS="--continuous --delay ${DELAY}"
fi

if [ "${RESET}" = "true" ]; then
    ARGS="${ARGS} --reset"
fi

echo ""
echo "Starting VOZ crawler..."
exec python voz_kafka_producer.py ${ARGS}
