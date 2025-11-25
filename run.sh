#!/bin/bash

# Real-Time Stress Detection Pipeline Runner
# This script starts all components of the real-time stress detection system
#
# Key Features:
# - Automatically configures Kafka connection for local producer execution
# - Producer runs locally (uses localhost:29092), Spark runs in Docker (uses kafka:9092)
# - Creates necessary directories and checks all prerequisites
# - Monitors pipeline health in real-time
#
# First-time setup is fully automated - just run: ./run.sh

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
print_status() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Function to cleanup on exit
cleanup() {
    echo ""
    print_status "Stopping all processes..."

    # Kill background jobs (macOS compatible)
    JOBS=$(jobs -p)
    if [ -n "$JOBS" ]; then
        echo "$JOBS" | xargs kill 2>/dev/null || true
    fi

    print_success "Cleanup complete"
    exit 0
}

# Trap Ctrl+C and other termination signals
trap cleanup SIGINT SIGTERM

# Banner
echo ""
echo "======================================================================"
echo "  Real-Time Reddit Stress Detection Pipeline"
echo "  Vietnamese PhoBERT + Kafka + Spark + Cassandra + Grafana"
echo "======================================================================"
echo ""

# Step 1: Check virtual environment
print_status "Step 1: Checking virtual environment..."
if [[ -z "$VIRTUAL_ENV" ]]; then
    print_warning "Virtual environment not activated"
    print_status "Activating .venv..."
    source .venv/bin/activate
    if [[ $? -eq 0 ]]; then
        print_success "Virtual environment activated"
    else
        print_error "Failed to activate virtual environment"
        exit 1
    fi
else
    print_success "Virtual environment already activated: $VIRTUAL_ENV"
fi
echo ""

# Step 2: Check and install dependencies
print_status "Step 2: Checking Python dependencies..."
pip install -q praw prawcore tenacity kafka-python pyyaml python-dotenv > /dev/null 2>&1
if [[ $? -eq 0 ]]; then
    print_success "Python dependencies installed"
else
    print_warning "Some dependencies may already be installed"
fi
echo ""

# Step 3: Check Vietnamese ABSA PhoBERT model
print_status "Step 3: Checking Vietnamese ABSA PhoBERT model..."
if [ -d "ml/models/vietnamese_absa_sentiment_phobert_v1" ]; then
    if [ -f "ml/models/vietnamese_absa_sentiment_phobert_v1/model.pt" ]; then
        print_success "Vietnamese ABSA PhoBERT model found"
    else
        print_error "Model weights not found (model.pt)"
        print_status "Please train the ABSA model first"
        exit 1
    fi
else
    print_error "Vietnamese ABSA model directory not found"
    print_status "Expected: ml/models/vietnamese_absa_sentiment_phobert_v1/"
    print_status "Please train the ABSA model first"
    exit 1
fi
echo ""

# Step 4: Start Docker services (fresh or existing)
print_status "Step 4: Starting Docker services..."
if ! docker ps &> /dev/null; then
    print_error "Docker is not running. Please start Docker Desktop."
    exit 1
fi

# Always start services (docker-compose handles existing containers gracefully)
print_status "Starting/Restarting Docker Compose stack..."
docker-compose up -d

# Wait for services to be ready
print_status "Waiting 45 seconds for services to initialize..."
sleep 45

# Verify critical services
services=("reddit-kafka" "reddit-cassandra" "reddit-spark-master")
all_running=true
for service in "${services[@]}"; do
    if docker ps | grep -q "$service"; then
        print_success "$service is running"
    else
        print_error "$service failed to start"
        all_running=false
    fi
done

if [ "$all_running" = false ]; then
    print_error "Some services failed to start. Check: docker-compose logs"
    exit 1
fi
echo ""

# Step 5: Initialize Cassandra schema
print_status "Step 5: Initializing Cassandra schema..."

# Wait for Cassandra to be fully ready
print_status "Waiting for Cassandra to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0
while ! docker exec reddit-cassandra cqlsh -e "DESCRIBE KEYSPACES;" &> /dev/null; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        print_error "Cassandra failed to start after ${MAX_RETRIES} retries"
        exit 1
    fi
    echo -n "."
    sleep 2
done
echo ""
print_success "Cassandra is ready"

# Check if schema exists
if docker exec reddit-cassandra cqlsh -e "DESCRIBE KEYSPACE reddit_rt;" &> /dev/null; then
    print_success "Cassandra schema already exists (using existing schema)"
else
    print_status "Creating fresh Cassandra schema..."

    # Apply schema files in order
    for schema_file in cassandra/schema/*.cql; do
        if [ -f "$schema_file" ]; then
            print_status "Applying $(basename $schema_file)..."
            docker exec -i reddit-cassandra cqlsh < "$schema_file"
        fi
    done

    print_success "Cassandra schema created successfully"
fi
echo ""

# Step 6: Initialize Kafka topics
print_status "Step 6: Initializing Kafka topics..."

# Wait for Kafka to be ready
print_status "Waiting for Kafka to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0
while ! docker exec reddit-kafka kafka-broker-api-versions --bootstrap-server localhost:9092 &> /dev/null; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        print_error "Kafka failed to start after ${MAX_RETRIES} retries"
        exit 1
    fi
    echo -n "."
    sleep 2
done
echo ""
print_success "Kafka is ready"

# Create topics if they don't exist
if docker exec reddit-kafka kafka-topics --list --bootstrap-server localhost:9092 2>/dev/null | grep -q "reddit.posts.raw.v1"; then
    print_success "Kafka topics already exist"
else
    print_status "Creating Kafka topics..."

    # Create topic directly (more reliable than script)
    docker exec reddit-kafka kafka-topics --create \
        --bootstrap-server localhost:9092 \
        --topic reddit.posts.raw.v1 \
        --partitions 3 \
        --replication-factor 1 \
        --config retention.ms=86400000 \
        2>/dev/null || print_warning "Topic may already exist"

    print_success "Kafka topics initialized"
fi
echo ""

# Step 6.5: Configure producer for local execution
print_status "Step 6.5: Configuring producer Kafka connection..."
# Producer runs locally (not in Docker), so it needs localhost:29092
CONFIG_FILE="producers/reddit_producer/config/config.yaml"
if grep -q "kafka:9092" "$CONFIG_FILE"; then
    print_warning "Producer config has 'kafka:9092' but producer runs locally"
    print_status "Updating to 'localhost:29092' for local execution..."
    # Use temporary file for cross-platform compatibility
    sed 's/- kafka:9092/- localhost:29092/' "$CONFIG_FILE" > "$CONFIG_FILE.tmp"
    mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"
    print_success "Producer config updated"
elif grep -q "localhost:29092" "$CONFIG_FILE"; then
    print_success "Producer already configured for local execution"
else
    print_warning "Unknown Kafka config in producer config file"
fi
echo ""

# Step 7: Start Reddit Producer (background)
print_status "Step 7: Starting Reddit Producer..."
# Create logs directory if it doesn't exist
mkdir -p logs
cd producers/reddit_producer
python main.py > ../../logs/reddit_producer.log 2>&1 &
PRODUCER_PID=$!
cd ../..
print_success "Reddit Producer started (PID: $PRODUCER_PID)"
print_status "Logs: logs/reddit_producer.log"
echo ""

# Wait for producer to initialize
print_status "Waiting 5 seconds for producer to initialize..."
sleep 5

# Check if producer is still running
if ! ps -p $PRODUCER_PID > /dev/null 2>&1; then
    print_error "Producer failed to start. Check logs/reddit_producer.log"
    tail -20 logs/reddit_producer.log
    exit 1
fi
print_success "Producer is running"
echo ""

# Step 8: Start Spark Streaming with ABSA Model (Docker)
print_status "Step 8: Starting Spark Streaming with ABSA Model (Docker)..."

# Check if Spark job is already running
if docker exec reddit-spark-master /opt/spark/bin/spark-submit --status 2>/dev/null | grep -q "RUNNING"; then
    print_warning "Spark job may already be running"
    print_status "Stopping existing Spark applications..."
    # Kill any existing Spark applications
    docker exec reddit-spark-master pkill -f "spark-submit" || true
    sleep 5
fi

# Submit Spark ABSA job to Docker Spark master
print_status "Submitting Spark ABSA pipeline..."
docker exec -d reddit-spark-master /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --packages com.datastax.spark:spark-cassandra-connector_2.12:3.5.0,org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
  --conf spark.cassandra.connection.host=cassandra \
  --conf spark.cassandra.connection.port=9042 \
  /opt/spark-apps/kafka_to_cassandra_with_absa.py

print_success "Spark ABSA Pipeline submitted to Docker"
print_status "Logs: docker logs -f reddit-spark-master"
echo ""

# Wait for Spark to initialize
print_status "Waiting 20 seconds for Spark ABSA pipeline to initialize..."
sleep 20

print_success "Spark ABSA Pipeline is running in Docker"
echo ""

# Step 9: Display status
echo "======================================================================"
echo -e "${GREEN}✓ All Components Running!${NC}"
echo "======================================================================"
echo ""
echo "Running Components:"
echo "  • Reddit Producer    (PID: $PRODUCER_PID) → logs/reddit_producer.log"
echo "  • Spark ML Pipeline  (Docker: reddit-spark-master)"
echo "  • Kafka              (Docker: reddit-kafka)"
echo "  • Cassandra          (Docker: reddit-cassandra)"
echo "  • Grafana            (Docker: reddit-grafana)"
echo ""
echo "Dashboards:"
echo "  • Streamlit:   http://localhost:8501 (ABSA Dashboard)"
echo "  • Grafana:     http://localhost:3000 (admin/admin)"
echo "  • Kafka UI:    http://localhost:8080"
echo "  • Spark UI:    http://localhost:8081"
echo "  • Airflow:     http://localhost:8082 (airflow/airflow)"
echo ""
echo "Real-Time Data Flow:"
echo "  Reddit → Kafka → Spark+ABSA → Cassandra → Streamlit/Grafana"
echo "  Model: Vietnamese PhoBERT ABSA (Multi-label)"
echo "  Latency: ~30-60 seconds from post to dashboard"
echo ""
echo "Monitoring Commands:"
echo "  • Producer logs:  tail -f logs/reddit_producer.log"
echo "  • Spark logs:     docker logs -f reddit-spark-master"
echo "  • Kafka messages: docker exec reddit-kafka kafka-console-consumer \\"
echo "                      --bootstrap-server localhost:9092 \\"
echo "                      --topic reddit.posts.raw.v1 --from-beginning --max-messages 5"
echo "  • Cassandra data: docker exec -it reddit-cassandra cqlsh -e \\"
echo "                      \"SELECT * FROM reddit_rt.classified_posts_by_hour LIMIT 10;\""
echo ""
echo "======================================================================"
echo -e "${YELLOW}Press Ctrl+C to stop all components${NC}"
echo "======================================================================"
echo ""

# Monitor logs in real-time
print_status "Monitoring pipeline (showing recent activity)..."
echo ""

# Create a monitoring loop
SECONDS=0
while true; do
    # Show producer activity every 30 seconds
    if (( SECONDS % 30 == 0 )); then
        echo ""
        print_status "Pipeline Status ($(date +'%H:%M:%S')):"

        # Check producer
        if ps -p $PRODUCER_PID > /dev/null 2>&1; then
            PRODUCER_COUNT=$(grep -c "Published submission" logs/reddit_producer.log 2>/dev/null || echo "0")
            print_success "Producer: Running ($PRODUCER_COUNT posts published)"
        else
            print_error "Producer: Stopped"
            break
        fi

        # Check Spark
        if docker ps | grep -q "reddit-spark-master"; then
            # Check Cassandra for processed records
            CLASSIFIED_COUNT=$(docker exec reddit-cassandra cqlsh -e "SELECT COUNT(*) FROM reddit_rt.classified_posts_by_hour;" 2>/dev/null | grep -E "^\s*\d+" | tr -d ' ' || echo "0")
            print_success "Spark ABSA: Running ($CLASSIFIED_COUNT posts classified)"
        else
            print_error "Spark ABSA: Stopped"
            break
        fi

        # Show recent activity
        echo ""
        echo "Recent Activity:"
        echo "----------------"

        # Last producer message
        if [ -f logs/reddit_producer.log ]; then
            LAST_PRODUCER=$(tail -n 1 logs/reddit_producer.log 2>/dev/null | cut -c 1-100)
            echo "Producer: $LAST_PRODUCER"
        fi

        # Last Spark message (from Docker logs)
        LAST_SPARK=$(docker logs reddit-spark-master 2>&1 | tail -n 1 | cut -c 1-100)
        echo "Spark ABSA: $LAST_SPARK"

        echo ""
    fi

    sleep 5
done

# If we get here, something stopped
print_error "Pipeline stopped unexpectedly"
cleanup
