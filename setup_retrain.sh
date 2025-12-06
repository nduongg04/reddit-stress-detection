#!/bin/bash
# Setup Script for Reddit Stress Detection - Retrain Pipeline
# Run this ONCE before starting the Airflow retrain pipeline

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
GRAY='\033[0;90m'
NC='\033[0m'

echo ""
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}Reddit Stress Detection - Retrain Setup${NC}"
echo -e "${BLUE}==========================================${NC}"
echo ""

# Check Python
echo -e "${YELLOW}Checking Python installation...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python not found. Please install Python 3.9+${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}✓ Python installed: $PYTHON_VERSION${NC}"
echo ""

# Check/Create virtual environment
echo -e "${YELLOW}Checking virtual environment...${NC}"
if [ -d ".venv" ]; then
    echo -e "${GREEN}✓ Virtual environment found${NC}"
else
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv .venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi
echo ""

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source .venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"
echo ""

# Install dependencies
echo -e "${YELLOW}Installing Python dependencies...${NC}"
echo -e "${GRAY}  This may take 5-10 minutes...${NC}"
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# Check Docker
echo -e "${YELLOW}Checking Docker...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not found. Please install Docker${NC}"
    exit 1
fi
DOCKER_VERSION=$(docker --version)
echo -e "${GREEN}✓ Docker installed: $DOCKER_VERSION${NC}"

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}✗ Docker Compose not found${NC}"
    exit 1
fi
COMPOSE_VERSION=$(docker-compose --version)
echo -e "${GREEN}✓ Docker Compose installed: $COMPOSE_VERSION${NC}"
echo ""

# Check model files
echo -e "${YELLOW}Checking Vietnamese ABSA PhoBERT model...${NC}"
if [ -f "ml/models/vietnamese_absa_sentiment_phobert_v1/model.pt" ]; then
    echo -e "${GREEN}✓ Model weights found${NC}"
else
    echo -e "${YELLOW}⚠ Model weights not found (model.pt)${NC}"
    echo -e "${GRAY}  You may need to train the model first${NC}"
fi

if [ -f "ml/models/registry/registry.json" ]; then
    echo -e "${GREEN}✓ Model registry initialized${NC}"
else
    echo -e "${YELLOW}⚠ Model registry not found${NC}"
    echo -e "${GRAY}  It will be created automatically${NC}"
fi
echo ""

# Check training data
echo -e "${YELLOW}Checking training data...${NC}"
if [ -d "ml/dataset/labeled" ]; then
    CSV_COUNT=$(find ml/dataset/labeled -name "*.csv" -type f | wc -l)
    if [ "$CSV_COUNT" -gt 0 ]; then
        echo -e "${GREEN}✓ Training data found ($CSV_COUNT CSV files)${NC}"
    else
        echo -e "${YELLOW}⚠ No CSV files in ml/dataset/labeled/${NC}"
        echo -e "${GRAY}  You need labeled data for retraining${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Training data directory not found${NC}"
    echo -e "${GRAY}  Creating directory...${NC}"
    mkdir -p ml/dataset/labeled
    echo -e "${GREEN}✓ Directory created${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}==========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${BLUE}==========================================${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "${NC}  1. Start Docker services:${NC}"
echo -e "${GRAY}     docker-compose up -d${NC}"
echo ""
echo -e "${NC}  2. Setup Ollama model (one-time):${NC}"
echo -e "${GRAY}     ./scripts/setup_ollama.sh${NC}"
echo ""
echo -e "${NC}  3. Access Airflow UI:${NC}"
echo -e "${GRAY}     http://localhost:8082 (airflow/airflow)${NC}"
echo ""
echo -e "${NC}  4. Enable the retrain DAG:${NC}"
echo -e "${GRAY}     vietnamese_absa_daily_retrain${NC}"
echo ""
