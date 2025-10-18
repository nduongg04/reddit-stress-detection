#!/bin/bash

# Submit Spark Streaming Application with pre-downloaded JARs
# Usage: ./submit_with_jars.sh [env] [mode]

set -e

ENV=${1:-dev}
MODE=${2:-console}

echo "=========================================="
echo "Submitting Reddit Stream Processor"
echo "=========================================="
echo "Environment: $ENV"
echo "Mode: $MODE"
echo ""

# Define required JARs
SPARK_VERSION="3.5.0"
SCALA_VERSION="2.12"
KAFKA_VERSION="3.4.0"

JAR_DIR="/opt/spark/jars"

# Check if JARs exist, if not download them
echo "Checking for required JARs..."

KAFKA_JAR="spark-sql-kafka-0-10_${SCALA_VERSION}-${SPARK_VERSION}.jar"
KAFKA_CLIENTS_JAR="kafka-clients-${KAFKA_VERSION}.jar"
SPARK_TOKEN_JAR="spark-token-provider-kafka-0-10_${SCALA_VERSION}-${SPARK_VERSION}.jar"
COMMONS_POOL_JAR="commons-pool2-2.11.1.jar"

# Function to download JAR if it doesn't exist
download_jar() {
    local jar_name=$1
    local group_id=$2
    local artifact_id=$3
    local version=$4

    if docker exec reddit-spark-master test -f "${JAR_DIR}/${jar_name}"; then
        echo "  ✓ ${jar_name} exists"
    else
        echo "  → Downloading ${jar_name}..."
        local maven_url="https://repo1.maven.org/maven2/${group_id}/${artifact_id}/${version}/${jar_name}"
        docker exec -u root reddit-spark-master bash -c "cd ${JAR_DIR} && wget -q ${maven_url} || curl -O ${maven_url}"
        if docker exec reddit-spark-master test -f "${JAR_DIR}/${jar_name}"; then
            echo "  ✓ Downloaded ${jar_name}"
        else
            echo "  ✗ Failed to download ${jar_name}"
        fi
    fi
}

# Download required JARs
download_jar "${KAFKA_JAR}" "org/apache/spark" "spark-sql-kafka-0-10_${SCALA_VERSION}" "${SPARK_VERSION}"
download_jar "${KAFKA_CLIENTS_JAR}" "org/apache/kafka" "kafka-clients" "${KAFKA_VERSION}"
download_jar "${SPARK_TOKEN_JAR}" "org/apache/spark" "spark-token-provider-kafka-0-10_${SCALA_VERSION}" "${SPARK_VERSION}"
download_jar "${COMMONS_POOL_JAR}" "org/apache/commons" "commons-pool2" "2.11.1"

echo ""
echo "Starting Spark job..."
echo ""

# Submit job with explicit jars (no package resolution needed)
docker exec reddit-spark-master \
  /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --jars "${JAR_DIR}/${KAFKA_JAR},${JAR_DIR}/${KAFKA_CLIENTS_JAR},${JAR_DIR}/${SPARK_TOKEN_JAR},${JAR_DIR}/${COMMONS_POOL_JAR}" \
  --conf spark.sql.shuffle.partitions=6 \
  --conf spark.executor.memory=2g \
  --conf spark.driver.memory=1g \
  --conf spark.executor.cores=2 \
  /opt/spark-apps/spark/apps/streaming/reddit_stream_processor.py \
  --env $ENV \
  --mode $MODE

echo ""
echo "=========================================="
echo "Spark job completed"
echo "=========================================="
