#!/bin/bash
# ============================================================================
# VOZ Real-Time Stress Detection Pipeline
# ============================================================================
# Flow: VOZ.vn → Kafka → Spark (LLM) → Cassandra → Streamlit
# ============================================================================

set -e

echo "=============================================="
echo "VOZ Real-Time Stress Detection Pipeline"
echo "=============================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check prerequisites
check_prereqs() {
    echo "Checking prerequisites..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Error: Docker not found${NC}"
        exit 1
    fi

    # Check Ollama
    if ! command -v ollama &> /dev/null; then
        echo -e "${YELLOW}Warning: Ollama not found. Install from https://ollama.com${NC}"
    else
        echo -e "${GREEN}✓ Ollama found${NC}"
    fi

    # Check Python venv
    if [ -d ".venv" ]; then
        source .venv/bin/activate
        echo -e "${GREEN}✓ Virtual environment activated${NC}"
    else
        echo -e "${YELLOW}Warning: No .venv found, using system Python${NC}"
    fi
}

# Start Docker services
start_docker() {
    echo ""
    echo "Starting Docker services..."
    docker-compose up -d zookeeper kafka cassandra kafka-ui

    echo "Waiting for services to be healthy..."
    sleep 15

    # Check Kafka
    if docker exec reddit-kafka kafka-broker-api-versions --bootstrap-server localhost:9092 &>/dev/null; then
        echo -e "${GREEN}✓ Kafka is ready${NC}"
    else
        echo -e "${RED}✗ Kafka not ready${NC}"
        exit 1
    fi

    # Check Cassandra
    if docker exec reddit-cassandra cqlsh -e "describe cluster" &>/dev/null; then
        echo -e "${GREEN}✓ Cassandra is ready${NC}"
    else
        echo -e "${RED}✗ Cassandra not ready${NC}"
        exit 1
    fi
}

# Initialize schemas and topics
init_schemas() {
    echo ""
    echo "Initializing Kafka topics..."
    ./scripts/init-kafka-topics.sh 2>/dev/null || true

    echo ""
    echo "Initializing Cassandra schemas..."
    for schema in cassandra/schema/*.cql; do
        echo "  Applying $schema..."
        docker exec -i reddit-cassandra cqlsh < "$schema" 2>/dev/null || true
    done
    echo -e "${GREEN}✓ Schemas initialized${NC}"
}

# Check Ollama model
check_ollama() {
    echo ""
    echo "Checking Ollama model..."

    if curl -s http://localhost:11434/api/tags | grep -q "llama3.1:8b"; then
        echo -e "${GREEN}✓ llama3.1:8b model ready${NC}"
    else
        echo -e "${YELLOW}Pulling llama3.1:8b model (this may take a while)...${NC}"
        ollama pull llama3.1:8b
    fi
}

# Start VOZ producer
start_producer() {
    echo ""
    echo "Starting VOZ producer..."

    # Default target posts
    TARGET=${1:-50}

    python producers/voz_kafka_producer.py --target "$TARGET" --delay 1.0 &
    PRODUCER_PID=$!
    echo -e "${GREEN}✓ VOZ producer started (PID: $PRODUCER_PID, target: $TARGET posts)${NC}"
    echo $PRODUCER_PID > /tmp/voz_producer.pid
}

# Start Streamlit
start_streamlit() {
    echo ""
    echo "Starting Streamlit dashboard..."

    cd streamlit_app
    streamlit run app.py --server.port 8501 &
    STREAMLIT_PID=$!
    cd ..

    echo -e "${GREEN}✓ Streamlit started (PID: $STREAMLIT_PID)${NC}"
    echo $STREAMLIT_PID > /tmp/streamlit.pid
}

# Print status
print_status() {
    echo ""
    echo "=============================================="
    echo -e "${GREEN}Pipeline Started!${NC}"
    echo "=============================================="
    echo ""
    echo "Access points:"
    echo "  - Streamlit Dashboard: http://localhost:8501"
    echo "  - Kafka UI:            http://localhost:8080"
    echo ""
    echo "Pipeline flow:"
    echo "  VOZ.vn → Kafka (voz.posts.raw.v1) → Spark → Cassandra → Streamlit"
    echo ""
    echo "To start Spark streaming (in another terminal):"
    echo "  docker exec -it reddit-spark-master spark-submit \\"
    echo "    --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,com.datastax.spark:spark-cassandra-connector_2.12:3.5.0 \\"
    echo "    /opt/spark-apps/voz_streaming_pipeline.py"
    echo ""
    echo "To stop: ./run_voz_pipeline.sh stop"
    echo "=============================================="
}

# Stop pipeline
stop_pipeline() {
    echo "Stopping pipeline..."

    if [ -f /tmp/voz_producer.pid ]; then
        kill $(cat /tmp/voz_producer.pid) 2>/dev/null || true
        rm /tmp/voz_producer.pid
    fi

    if [ -f /tmp/streamlit.pid ]; then
        kill $(cat /tmp/streamlit.pid) 2>/dev/null || true
        rm /tmp/streamlit.pid
    fi

    echo -e "${GREEN}✓ Pipeline stopped${NC}"
}

# Main
case "${1:-start}" in
    start)
        check_prereqs
        start_docker
        init_schemas
        check_ollama
        start_producer "${2:-50}"
        start_streamlit
        print_status
        ;;
    stop)
        stop_pipeline
        ;;
    producer)
        start_producer "${2:-50}"
        ;;
    streamlit)
        start_streamlit
        ;;
    *)
        echo "Usage: $0 {start|stop|producer [count]|streamlit}"
        exit 1
        ;;
esac
