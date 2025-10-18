#!/bin/bash
# Airflow Reset Script
#
# This script completely resets the Airflow environment.
# WARNING: This will delete all DAG runs, task history, and logs!

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

echo "=========================================="
echo "Airflow Environment Reset"
echo "=========================================="
echo ""
print_error "WARNING: This will delete:"
echo "  - All DAG run history"
echo "  - All task execution logs"
echo "  - All Airflow metadata"
echo "  - Database content"
echo ""
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    print_info "Reset cancelled"
    exit 0
fi

echo ""
print_info "Stopping Airflow containers..."
docker-compose stop airflow-webserver airflow-scheduler || true
print_success "Containers stopped"

print_info "Removing Airflow containers..."
docker-compose rm -f airflow-webserver airflow-scheduler airflow-postgres || true
print_success "Containers removed"

print_info "Removing Airflow volumes..."
docker volume rm doan_airflow-data doan_airflow-postgres-data 2>/dev/null || true
print_success "Volumes removed"

print_info "Cleaning local logs..."
rm -rf airflow/logs/*
print_success "Logs cleaned"

echo ""
print_success "Airflow environment reset complete!"
echo ""
echo "To start fresh:"
echo "1. docker-compose up -d airflow-postgres"
echo "2. docker-compose up -d airflow-webserver airflow-scheduler"
echo "3. ./scripts/airflow-init.sh"
echo ""
