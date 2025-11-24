#!/bin/bash

# Collect 1000 Stress Posts from r/vozforums
# This script collects clean Vietnamese stress data for LDA and training

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

echo "======================================================================"
echo "  r/vozforums Stress Data Collection"
echo "  Target: 1000 Vietnamese stress posts"
echo "======================================================================"
echo ""

# Activate virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    print_status "Activating virtual environment..."
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    elif [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    else
        print_error "No virtual environment found"
        exit 1
    fi
fi
print_success "Virtual environment activated"

# Check Docker services
print_status "Checking Docker services..."
if ! docker ps | grep -q "reddit-kafka"; then
    print_error "Kafka not running. Start with: docker-compose up -d"
    exit 1
fi
if ! docker ps | grep -q "reddit-cassandra"; then
    print_error "Cassandra not running. Start with: docker-compose up -d"
    exit 1
fi
print_success "Docker services running"

# Check config
CONFIG_FILE="producers/reddit_producer/config/config.yaml"
if ! grep -q "vozforums_stress" "$CONFIG_FILE"; then
    print_error "Config not set to vozforums_stress mode"
    exit 1
fi
print_success "Config verified (vozforums_stress mode)"

# Create logs directory
mkdir -p logs

# Run producer
print_status "Starting r/vozforums stress collection..."
echo ""
echo "Progress will be logged to: logs/vozforums_stress.log"
echo "Press Ctrl+C to stop collection"
echo ""

cd producers/reddit_producer
python main.py 2>&1 | tee ../../logs/vozforums_stress.log

echo ""
echo "======================================================================"
echo "Collection complete!"
echo "======================================================================"
echo ""
echo "Next steps:"
echo "  1. Check first post date in logs: grep 'FIRST POST DATE' logs/vozforums_stress.log"
echo "  2. Export data: python scripts/export_vietnamese_from_cassandra.py"
echo "  3. Run LDA: python ml/lda/extract_topics.py"
echo ""
