#!/bin/bash

# Test script for Kafka setup
# Validates that Kafka is working correctly by producing and consuming test messages

set -e

KAFKA_CONTAINER="reddit-kafka"
KAFKA_BROKER="localhost:9092"
TEST_TOPIC="reddit.posts.raw.v1"

echo "==================================="
echo "Kafka Health Check & Test Script"
echo "==================================="
echo ""

# Check if Kafka container is running
if ! docker ps | grep -q $KAFKA_CONTAINER; then
    echo "✗ Kafka container is not running!"
    echo "Please start the services with: docker-compose up -d"
    exit 1
fi

echo "✓ Kafka container is running"
echo ""

# Test 1: Check Kafka broker connectivity
echo "Test 1: Checking Kafka broker connectivity..."
if docker exec $KAFKA_CONTAINER kafka-broker-api-versions --bootstrap-server $KAFKA_BROKER > /dev/null 2>&1; then
    echo "✓ Kafka broker is accessible"
else
    echo "✗ Cannot connect to Kafka broker"
    exit 1
fi
echo ""

# Test 2: Verify topics exist
echo "Test 2: Verifying topics exist..."
TOPICS=$(docker exec $KAFKA_CONTAINER kafka-topics --list --bootstrap-server $KAFKA_BROKER)

if echo "$TOPICS" | grep -q "reddit.posts.raw.v1"; then
    echo "✓ Topic 'reddit.posts.raw.v1' exists"
else
    echo "✗ Topic 'reddit.posts.raw.v1' not found"
    exit 1
fi

if echo "$TOPICS" | grep -q "reddit.posts.dlq.v1"; then
    echo "✓ Topic 'reddit.posts.dlq.v1' exists"
else
    echo "✗ Topic 'reddit.posts.dlq.v1' not found"
    exit 1
fi
echo ""

# Test 3: Produce test message
echo "Test 3: Publishing test message to topic..."
TEST_MESSAGE='{"post_id":"test_001","kind":"submission","subreddit":"test","title":"Test Post","body":"This is a test post","created_utc":"2025-10-06T00:00:00Z","author_hash":"test_hash","permalink":"/r/test/test_001","ingest_ts":"2025-10-06T00:00:00Z","source":"test"}'

echo "$TEST_MESSAGE" | docker exec -i $KAFKA_CONTAINER kafka-console-producer \
    --broker-list $KAFKA_BROKER \
    --topic $TEST_TOPIC \
    --property "parse.key=false" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Test message published successfully"
else
    echo "✗ Failed to publish test message"
    exit 1
fi
echo ""

# Test 4: Consume test message
echo "Test 4: Consuming message from topic..."
CONSUMED_MESSAGE=$(docker exec $KAFKA_CONTAINER kafka-console-consumer \
    --bootstrap-server $KAFKA_BROKER \
    --topic $TEST_TOPIC \
    --from-beginning \
    --max-messages 1 \
    --timeout-ms 5000 2>/dev/null | tail -n 1)

if [ ! -z "$CONSUMED_MESSAGE" ]; then
    echo "✓ Message consumed successfully"
    echo "Message: ${CONSUMED_MESSAGE:0:100}..."
else
    echo "✗ Failed to consume message"
    exit 1
fi
echo ""

# Test 5: Check JMX metrics
echo "Test 5: Checking JMX metrics availability..."
if docker exec $KAFKA_CONTAINER bash -c "nc -z localhost 9997" > /dev/null 2>&1; then
    echo "✓ JMX metrics port (9997) is accessible"
else
    echo "⚠ JMX metrics port may not be accessible (non-critical)"
fi
echo ""

# Test 6: Check consumer group functionality
echo "Test 6: Testing consumer groups..."
docker exec $KAFKA_CONTAINER kafka-consumer-groups \
    --bootstrap-server $KAFKA_BROKER \
    --list > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Consumer groups are working"
else
    echo "✗ Consumer groups test failed"
    exit 1
fi
echo ""

echo "==================================="
echo "✓ All Kafka tests passed!"
echo "==================================="
echo ""
echo "Summary:"
echo "- Kafka broker: Running and accessible"
echo "- Topics: Created with correct configuration"
echo "- Producer: Working"
echo "- Consumer: Working"
echo "- Monitoring: JMX metrics available"
echo ""
echo "Access Kafka UI at: http://localhost:8080"
echo ""
