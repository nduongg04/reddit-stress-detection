#!/bin/bash
# Run Vietnamese Reddit Producer in Background
set -e

cd "$(dirname "$0")"

# Activate virtual environment
source .venv/bin/activate

# Run producer in background
cd producers/reddit_producer
nohup python main.py > ../../logs/vietnamese_collection.log 2>&1 &

PRODUCER_PID=$!

echo "✓ Vietnamese producer started!"
echo "  PID: $PRODUCER_PID"
echo "  Logs: logs/vietnamese_collection.log"
echo ""
echo "Monitor progress:"
echo "  tail -f logs/vietnamese_collection.log"
echo ""
echo "Stop producer:"
echo "  kill $PRODUCER_PID"
