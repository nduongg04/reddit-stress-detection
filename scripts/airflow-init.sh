#!/bin/bash
# Airflow Initialization Script
#
# This script initializes the Airflow database and creates the admin user.
# Run this script once before starting Airflow for the first time.

set -e  # Exit on error

echo "=========================================="
echo "Airflow Initialization Script"
echo "=========================================="

# Configuration
AIRFLOW_CONTAINER="reddit-airflow-webserver"
ADMIN_USER="airflow"
ADMIN_PASSWORD="airflow"
ADMIN_EMAIL="admin@example.com"
ADMIN_FIRSTNAME="Airflow"
ADMIN_LASTNAME="Admin"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker first."
    exit 1
fi
print_success "Docker is running"

# Check if Airflow containers are running
print_info "Checking if Airflow containers are running..."
if ! docker ps | grep -q "reddit-airflow-postgres"; then
    print_error "Airflow Postgres is not running. Start it with: docker-compose up -d airflow-postgres"
    exit 1
fi
print_success "Airflow Postgres is running"

if ! docker ps | grep -q "reddit-airflow-webserver"; then
    print_error "Airflow webserver is not running. Start it with: docker-compose up -d airflow-webserver"
    exit 1
fi
print_success "Airflow webserver is running"

# Wait for webserver to be ready
print_info "Waiting for Airflow webserver to be ready..."
sleep 10

# Initialize Airflow database
print_info "Initializing Airflow database..."
docker exec $AIRFLOW_CONTAINER airflow db init || print_error "Database init failed (may already be initialized)"
print_success "Database initialized"

# Create admin user
print_info "Creating admin user..."
docker exec $AIRFLOW_CONTAINER airflow users create \
    --username "$ADMIN_USER" \
    --firstname "$ADMIN_FIRSTNAME" \
    --lastname "$ADMIN_LASTNAME" \
    --role Admin \
    --email "$ADMIN_EMAIL" \
    --password "$ADMIN_PASSWORD" 2>/dev/null || print_info "Admin user may already exist"
print_success "Admin user configured"

# Verify DAGs folder
print_info "Verifying DAGs folder..."
if [ ! -d "airflow/dags" ]; then
    print_error "DAGs folder not found. Creating it..."
    mkdir -p airflow/dags
fi
print_success "DAGs folder exists"

# List DAGs
print_info "Listing available DAGs..."
docker exec $AIRFLOW_CONTAINER airflow dags list 2>/dev/null || print_info "No DAGs found yet"

echo ""
echo "=========================================="
print_success "Airflow Initialization Complete!"
echo "=========================================="
echo ""
echo "Access Airflow UI at: http://localhost:8082"
echo "Username: $ADMIN_USER"
echo "Password: $ADMIN_PASSWORD"
echo ""
echo "Next steps:"
echo "1. Open http://localhost:8082 in your browser"
echo "2. Login with the credentials above"
echo "3. Check that your DAGs are visible"
echo "4. Test the sample_dag by triggering it manually"
echo ""
