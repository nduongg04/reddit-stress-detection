#!/bin/bash
set -e

echo "========================================================================"
echo "  VOZ Stress Classifier - Spark Streaming Pipeline"
echo "========================================================================"

# Use SPARK_HOME from Dockerfile env
SPARK_HOME=${SPARK_HOME:-/opt/spark}

# Check if running as master or worker
if [ "$SPARK_MODE" = "master" ]; then
    echo "Starting Spark Master..."

    # Start Spark Master in background
    ${SPARK_HOME}/bin/spark-class org.apache.spark.deploy.master.Master &
    MASTER_PID=$!

    echo "✓ Spark Master started (PID: $MASTER_PID)"

    # Wait for Spark Master to be ready
    echo "Waiting for Spark Master to be ready..."
    sleep 10

    # Clean checkpoint for fresh start
    echo ""
    echo "========================================================================"
    echo "  Auto-submitting VOZ Stress Classifier Streaming Job"
    echo "========================================================================"

    echo "Cleaning checkpoint directory..."
    rm -rf /tmp/spark_checkpoints_voz
    echo "✓ Checkpoint deleted - will read from latest offset"

    # Submit streaming job
    ${SPARK_HOME}/bin/spark-submit \
        --master local[2] \
        --py-files /opt/spark-apps/model_inference.py \
        --packages com.datastax.spark:spark-cassandra-connector_2.12:3.5.0,org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
        --conf spark.cassandra.connection.host=${CASSANDRA_HOST:-cassandra} \
        --conf spark.cassandra.connection.port=9042 \
        --conf spark.driver.memory=2g \
        --conf spark.executor.memory=2g \
        /opt/spark-apps/kafka_to_cassandra_with_ml.py &

    JOB_PID=$!
    echo "✓ Streaming job submitted (PID: $JOB_PID)"

    # Keep container running
    wait $MASTER_PID

elif [ "$SPARK_MODE" = "worker" ]; then
    echo "Starting Spark Worker..."
    echo "Master URL: $SPARK_MASTER_URL"

    # Start Spark Worker
    ${SPARK_HOME}/bin/spark-class org.apache.spark.deploy.worker.Worker $SPARK_MASTER_URL
else
    echo "Error: SPARK_MODE not set. Use 'master' or 'worker'"
    exit 1
fi
