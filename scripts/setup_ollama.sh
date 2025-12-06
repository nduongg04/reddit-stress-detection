#!/bin/bash
# Script to pull Ollama model for active learning validation

echo "=========================================="
echo "Ollama Model Setup for Active Learning"
echo "=========================================="

# Wait for Ollama service to be ready
echo "Waiting for Ollama service..."
until curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
    sleep 2
    echo "  Waiting for Ollama..."
done

echo "✓ Ollama service is ready"

# Pull llama3.1:8b model (used by DAG)
echo ""
echo "Pulling llama3.1:8b model (this may take a while)..."
docker exec reddit-ollama ollama pull llama3.1:8b

echo ""
echo "✓ Ollama model setup complete!"
echo ""
echo "Available models:"
docker exec reddit-ollama ollama list

echo ""
echo "You can now run the Airflow DAG for retraining."
