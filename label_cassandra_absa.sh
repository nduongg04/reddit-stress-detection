#!/bin/bash
# Label Vietnamese posts from Cassandra with ABSA sentiment

set -e

echo "========================================"
echo "ABSA Labeling from Cassandra"
echo "========================================"
echo ""

# Activate virtual environment
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

# Check Cassandra is running
if ! docker ps | grep -q reddit-cassandra; then
    echo "✗ Cassandra is not running!"
    echo "  Start it with: docker-compose up -d cassandra"
    exit 1
fi

# Check Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "✗ Ollama not found!"
    echo "  Install: brew install ollama"
    exit 1
fi

# Check llama3.1:8b model
if ! ollama list | grep -q llama3.1:8b; then
    echo "Pulling llama3.1:8b model..."
    ollama pull llama3.1:8b
fi

# Run labeling
echo ""
echo "Starting labeling (this will take ~30-60 minutes)..."
echo ""

python ml/dataset/label_from_cassandra_absa.py

echo ""
echo "========================================"
echo "✓ Labeling complete!"
echo "========================================"
echo ""
echo "Output: ml/dataset/labeled/vozforums_absa_from_cassandra.csv"
