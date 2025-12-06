#!/bin/bash
# Script to apply confidence_scores field to Cassandra schema

echo "=========================================="
echo "Applying Confidence Score Schema Update"
echo "=========================================="
echo ""

# Check if Cassandra is running
echo "1. Checking Cassandra container..."
if ! docker ps | grep -q reddit-cassandra; then
    echo "❌ Cassandra container is not running!"
    echo "   Please start Cassandra first: docker-compose up -d cassandra"
    exit 1
fi
echo "✓ Cassandra is running"
echo ""

# Wait for Cassandra to be ready
echo "2. Waiting for Cassandra to be ready..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if docker exec reddit-cassandra cqlsh -e "DESCRIBE KEYSPACES" > /dev/null 2>&1; then
        echo "✓ Cassandra is ready"
        break
    fi
    attempt=$((attempt + 1))
    echo "   Waiting... ($attempt/$max_attempts)"
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "❌ Cassandra is not responding after $max_attempts attempts"
    exit 1
fi
echo ""

# Apply schema change
echo "3. Adding confidence_scores field to classified_posts_by_hour..."
docker exec reddit-cassandra cqlsh -e "
USE reddit_rt;
ALTER TABLE classified_posts_by_hour 
ADD confidence_scores map<text, double>;
" 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Schema updated successfully"
else
    echo "❌ Failed to update schema (field might already exist)"
fi
echo ""

# Verify schema
echo "4. Verifying schema..."
docker exec reddit-cassandra cqlsh -e "
USE reddit_rt;
DESCRIBE TABLE classified_posts_by_hour;
" | grep -A 2 "confidence_scores"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ confidence_scores field is present in schema"
else
    echo "❌ confidence_scores field not found in schema"
    exit 1
fi
echo ""

echo "=========================================="
echo "Schema Update Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Restart Spark containers:"
echo "   docker-compose restart spark-master spark-worker"
echo ""
echo "2. Restart Airflow containers:"
echo "   docker-compose restart airflow-webserver airflow-scheduler"
echo ""
echo "3. Enable DAG in Airflow UI:"
echo "   http://localhost:8082 (airflow/airflow)"
echo "   Toggle ON: vietnamese_absa_daily_retrain"
echo ""
