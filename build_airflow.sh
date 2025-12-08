#!/bin/bash
# Quick build script for Airflow ML service

set -e

echo "======================================================================"
echo "Building Airflow ML Service (reddit-airflow-ml)"
echo "======================================================================"
echo ""

echo "[1/3] Building Airflow image with ML dependencies..."
echo "      This may take 10-15 minutes (installing torch/transformers)..."
echo ""

docker-compose build airflow-webserver airflow-scheduler

echo ""
echo "[2/3] Verifying image..."
docker images | grep reddit-airflow-ml

echo ""
echo "[3/3] Starting services..."
docker-compose up -d airflow-postgres airflow-webserver airflow-scheduler ollama

echo ""
echo "======================================================================"
echo "✓ Build Complete!"
echo "======================================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Pull Ollama model (one-time):"
echo "   docker exec reddit-ollama ollama pull llama3.1:8b"
echo ""
echo "2. Access Airflow UI:"
echo "   http://localhost:8082 (airflow/airflow)"
echo ""
echo "3. Enable DAG: vietnamese_absa_daily_retrain"
echo ""
echo "4. Verify ML dependencies:"
echo "   docker exec reddit-airflow-scheduler python -c 'import torch; import transformers; print(\"OK\")'"
echo ""
