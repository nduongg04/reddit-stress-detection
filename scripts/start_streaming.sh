#!/bin/bash
# Start VOZ Stress Classification Streaming Pipeline

set -e

echo "=========================================="
echo "  VOZ Stress Classification Pipeline"
echo "=========================================="

# Check if ONNX model exists
if [ ! -f "ml/exports/phobert_stress.onnx" ]; then
    echo "ERROR: ONNX model not found at ml/exports/phobert_stress.onnx"
    echo "Run Phase 3 training first: python ml/training/train_phobert.py"
    echo "Then export: python ml/training/export_onnx.py"
    exit 1
fi

# Check if tokenizer exists
if [ ! -d "ml/checkpoints/phobert_stress_v1/tokenizer" ]; then
    echo "ERROR: Tokenizer not found at ml/checkpoints/phobert_stress_v1/tokenizer"
    echo "Run Phase 3 training first"
    exit 1
fi

echo "✓ Model and tokenizer found"

# Start infrastructure
echo ""
echo "1. Starting infrastructure (Kafka, Cassandra)..."
docker-compose up -d zookeeper kafka cassandra

# Wait for Kafka
echo "2. Waiting for Kafka to be ready..."
until docker exec reddit-kafka kafka-broker-api-versions --bootstrap-server localhost:9092 > /dev/null 2>&1; do
    echo "   Waiting for Kafka..."
    sleep 5
done
echo "✓ Kafka is ready"

# Wait for Cassandra
echo "3. Waiting for Cassandra to be ready..."
until docker exec reddit-cassandra cqlsh -e "describe cluster" > /dev/null 2>&1; do
    echo "   Waiting for Cassandra..."
    sleep 5
done
echo "✓ Cassandra is ready"

# Create Kafka topic if not exists
echo "4. Creating Kafka topic..."
docker exec reddit-kafka kafka-topics --bootstrap-server localhost:9092 \
    --create --if-not-exists \
    --topic voz.posts.raw.v1 \
    --partitions 3 \
    --replication-factor 1
echo "✓ Topic voz.posts.raw.v1 ready"

# Apply Cassandra schema
echo "5. Applying Cassandra schema..."
docker exec -i reddit-cassandra cqlsh < cassandra/schema/01_keyspace.cql
docker exec -i reddit-cassandra cqlsh < cassandra/schema/05_voz_classified_posts.cql
echo "✓ Cassandra schema applied"

# Start Spark
echo "6. Starting Spark streaming pipeline..."
docker-compose up -d spark-master

echo ""
echo "=========================================="
echo "  Pipeline Started!"
echo "=========================================="
echo ""
echo "Monitor logs: docker logs -f voz-spark-master"
echo "Kafka UI:     http://localhost:8080"
echo "Spark UI:     http://localhost:8081"
echo ""
echo "To send test data:"
echo "  python producers/voz_producer.py"
echo ""
