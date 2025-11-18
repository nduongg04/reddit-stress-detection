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
echo "  v4 Model + Kafka + Spark + Cassandra + Grafana"
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

# Step 3: Check v4 model
print_status "Step 3: Checking v4 model..."
if [ -d "ml/models/reddit_stress_v4" ]; then
    if [ -f "ml/models/reddit_stress_v4/model.safetensors" ] || [ -f "ml/models/reddit_stress_v4/pytorch_model.bin" ]; then
        print_success "v4 model found"
    else
        print_error "Model weights not found"
        print_status "Please train the model first: ./train_reddit_stress_v4.sh"
        exit 1
    fi
else
    print_error "v4 model directory not found"
    print_status "Please train the model first: ./train_reddit_stress_v4.sh"
    exit 1
fi
echo ""

# Step 4: Check Docker services
print_status "Step 4: Checking Docker services..."
if ! docker ps &> /dev/null; then
    print_error "Docker is not running"
    exit 1
fi

# Check if containers are running
if ! docker ps | grep -q "reddit-kafka"; then
    print_warning "Docker containers not running"
    print_status "Starting Docker services..."
    docker-compose up -d

    print_status "Waiting 30 seconds for services to be ready..."
    sleep 30
fi

# Verify services
services=("reddit-kafka" "reddit-cassandra" "reddit-grafana")
for service in "${services[@]}"; do
    if docker ps | grep -q "$service"; then
        print_success "$service is running"
    else
        print_error "$service is not running"
        exit 1
    fi
done
echo ""

# Step 5: Initialize Cassandra schema
print_status "Step 5: Initializing Cassandra schema..."
if docker exec reddit-cassandra cqlsh -e "DESCRIBE KEYSPACE reddit_rt;" &> /dev/null; then
    print_success "Cassandra schema already exists"
else
    print_status "Creating Cassandra schema..."
    docker exec -i reddit-cassandra cqlsh < cassandra/schema/01_keyspace.cql
    docker exec -i reddit-cassandra cqlsh < cassandra/schema/02_raw_posts_by_day.cql
    docker exec -i reddit-cassandra cqlsh < cassandra/schema/03_classified_posts_by_hour.cql
    docker exec -i reddit-cassandra cqlsh < cassandra/schema/04_agg_subreddit_hour.cql
    docker exec -i reddit-cassandra cqlsh < cassandra/schema/05_agg_global_hour.cql
    print_success "Cassandra schema created"
fi
echo ""

# Step 6: Check Kafka topics
print_status "Step 6: Checking Kafka topics..."
if docker exec reddit-kafka kafka-topics --list --bootstrap-server localhost:9092 | grep -q "reddit.posts.raw.v1"; then
    print_success "Kafka topics exist"
else
    print_status "Creating Kafka topics..."
    ./scripts/init-kafka-topics.sh
    sleep 5
    print_success "Kafka topics created"
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

# Step 8: Start Spark Streaming with ML (Docker with Custom Image)
print_status "Step 8: Starting Spark Streaming with v4 Model (Docker)..."

# Submit Spark job to Docker Spark master (which has ML libraries built in)
docker exec -d reddit-spark-master /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --packages com.datastax.spark:spark-cassandra-connector_2.12:3.5.0,org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
  --conf spark.cassandra.connection.host=cassandra \
  --conf spark.cassandra.connection.port=9042 \
  /opt/spark-apps/kafka_to_cassandra_with_ml.py

print_success "Spark ML Pipeline submitted to Docker"
print_status "Logs: docker logs -f reddit-spark-master"
echo ""

# Wait for Spark to initialize
print_status "Waiting 15 seconds for Spark to initialize..."
sleep 15

print_success "Spark ML Pipeline is running in Docker"
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
echo "  • Grafana:     http://localhost:3000 (admin/admin)"
echo "  • Kafka UI:    http://localhost:8080"
echo "  • Airflow:     http://localhost:8082"
echo ""
echo "Real-Time Data Flow:"
echo "  Reddit → Kafka → Spark+ML(v4) → Cassandra → Grafana"
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
            print_success "Spark ML: Running ($CLASSIFIED_COUNT posts classified)"
        else
            print_error "Spark ML: Stopped"
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
        echo "Spark ML: $LAST_SPARK"

        echo ""
    fi

    sleep 5
done

# If we get here, something stopped
print_error "Pipeline stopped unexpectedly"
cleanup
