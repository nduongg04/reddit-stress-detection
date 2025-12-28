#!/bin/bash
# Run Vozforums.com Scraper (Linux/Mac)
# 
# Usage:
#   ./run_voz_scraper.sh                    # Scrape to file only
#   ./run_voz_scraper.sh --kafka            # Scrape and send to Kafka
#   ./run_voz_scraper.sh --target 5000      # Custom target

set -e

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

TARGET_POSTS=10000
MAX_WORKERS=5
DELAY=1.0
KAFKA_MODE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --target)
            TARGET_POSTS="$2"
            shift 2
            ;;
        --kafka)
            KAFKA_MODE="--kafka"
            shift
            ;;
        --workers)
            MAX_WORKERS="$2"
            shift 2
            ;;
        --delay)
            DELAY="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}  Vozforums.com Scraper${NC}"
echo -e "${CYAN}  Target: $TARGET_POSTS posts${NC}"
echo -e "${CYAN}============================================================${NC}"
echo ""

# Check if virtual environment exists
if [ -f ".venv/bin/activate" ]; then
    echo -e "${GREEN}[1/4] Activating virtual environment...${NC}"
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    echo -e "${GREEN}[1/4] Activating virtual environment...${NC}"
    source venv/bin/activate
else
    echo -e "${RED}[!] Virtual environment not found${NC}"
    echo -e "${YELLOW}    Creating virtual environment...${NC}"
    python3 -m venv .venv
    source .venv/bin/activate
fi

# Install dependencies
echo -e "${GREEN}[2/4] Installing dependencies...${NC}"
pip install -q -r producers/voz_scraper/requirements.txt
pip install -q -r producers/reddit_producer/requirements.txt

# Create data directory
echo -e "${GREEN}[3/4] Creating data directory...${NC}"
mkdir -p data

# Build command
CMD="python producers/voz_scraper/main.py --target-posts $TARGET_POSTS --max-workers $MAX_WORKERS --delay $DELAY"

if [ -n "$KAFKA_MODE" ]; then
    echo -e "${YELLOW}[*] Kafka mode enabled - checking services...${NC}"
    
    # Check if Kafka is running
    if docker ps --filter "name=reddit-kafka" --format "{{.Names}}" | grep -q "reddit-kafka"; then
        echo -e "${GREEN}    ✓ Kafka is running${NC}"
        CMD="$CMD --kafka"
    else
        echo -e "${RED}    ✗ Kafka is not running!${NC}"
        echo -e "${YELLOW}    Starting Kafka services...${NC}"
        docker-compose up -d zookeeper kafka cassandra
        echo -e "${YELLOW}    Waiting 30s for Kafka to be ready...${NC}"
        sleep 30
        CMD="$CMD --kafka"
    fi
fi

# Run scraper
echo -e "${GREEN}[4/4] Starting scraper...${NC}"
echo ""
echo -e "${CYAN}Command: $CMD${NC}"
echo ""

$CMD

echo ""
echo -e "${CYAN}============================================================${NC}"
echo -e "${GREEN}  Scraping Complete!${NC}"
echo -e "${CYAN}============================================================${NC}"
