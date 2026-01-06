#!/bin/bash

# Script to initialize Kafka topics for Reddit Stress Detection System
# This script creates the required topics with appropriate configurations

set -e

KAFKA_CONTAINER="reddit-kafka"
KAFKA_BROKER="localhost:9092"

echo "==================================="
echo "Kafka Topic Initialization Script"
echo "==================================="
echo ""

# Wait for Kafka to be ready
echo "Waiting for Kafka to be ready..."
sleep 10

# Function to create topic
create_topic() {
    local topic_name=$1
    local partitions=$2
    local replication_factor=$3
    local retention_ms=$4

    echo "Creating topic: $topic_name"
    docker exec $KAFKA_CONTAINER kafka-topics \
        --create \
        --bootstrap-server $KAFKA_BROKER \
        --topic $topic_name \
        --partitions $partitions \
        --replication-factor $replication_factor \
        --config retention.ms=$retention_ms \
        --if-not-exists

    if [ $? -eq 0 ]; then
        echo "✓ Topic '$topic_name' created successfully"
    else
        echo "✗ Failed to create topic '$topic_name'"
        return 1
    fi
    echo ""
}

# Create raw posts topic
# Partitions: 6 for parallel processing
# Retention: 7 days (604800000 ms)
create_topic "reddit.posts.raw.v1" 6 1 604800000

# Create dead letter queue topic
# Partitions: 3 (lower traffic expected)
# Retention: 7 days (604800000 ms)
create_topic "reddit.posts.dlq.v1" 3 1 604800000

# Create VOZ posts topic for Vietnamese stress detection
# Partitions: 4 for parallel LLM inference
# Retention: 7 days (604800000 ms)
create_topic "voz.posts.raw.v1" 4 1 604800000

echo "==================================="
echo "Listing all topics:"
echo "==================================="
docker exec $KAFKA_CONTAINER kafka-topics \
    --list \
    --bootstrap-server $KAFKA_BROKER

echo ""
echo "==================================="
echo "Topic Details:"
echo "==================================="

# Show details for raw posts topic
echo "Topic: reddit.posts.raw.v1"
docker exec $KAFKA_CONTAINER kafka-topics \
    --describe \
    --bootstrap-server $KAFKA_BROKER \
    --topic reddit.posts.raw.v1

echo ""

# Show details for DLQ topic
echo "Topic: reddit.posts.dlq.v1"
docker exec $KAFKA_CONTAINER kafka-topics \
    --describe \
    --bootstrap-server $KAFKA_BROKER \
    --topic reddit.posts.dlq.v1

echo ""
echo "==================================="
echo "Kafka topics initialized successfully!"
echo "==================================="
echo ""
echo "Access Kafka UI at: http://localhost:8080"
