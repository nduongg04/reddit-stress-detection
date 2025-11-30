#!/bin/bash
# ============================================================================
# Cassandra Schema Initialization Script
# Description: Creates the reddit_rt keyspace and all required tables
# Usage: ./scripts/init-cassandra-schema.sh
# ============================================================================

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CONTAINER_NAME="reddit-cassandra"
SCHEMA_DIR="cassandra/schema"
MAX_RETRIES=30
RETRY_INTERVAL=2

echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}Cassandra Schema Initialization${NC}"
echo -e "${BLUE}=================================================${NC}"

# Function to check if Cassandra is ready
check_cassandra_ready() {
    docker exec "$CONTAINER_NAME" cqlsh -e "SELECT cluster_name FROM system.local;" >/dev/null 2>&1
    return $?
}

# Wait for Cassandra to be ready
echo -e "\n${YELLOW}[1/4] Waiting for Cassandra to be ready...${NC}"
RETRY_COUNT=0
while ! check_cassandra_ready; do
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo -e "${RED}Error: Cassandra did not become ready within ${MAX_RETRIES} attempts${NC}"
        exit 1
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -e "  Attempt $RETRY_COUNT/$MAX_RETRIES - Waiting ${RETRY_INTERVAL}s..."
    sleep $RETRY_INTERVAL
done
echo -e "${GREEN}✓ Cassandra is ready${NC}"

# Execute schema files in order
echo -e "\n${YELLOW}[2/4] Creating keyspace and tables...${NC}"

# Array of schema files in execution order
SCHEMA_FILES=(
    "01_keyspace.cql"
    "02_raw_posts_by_day.cql"
    "03_classified_posts_by_hour.cql"
    "04_agg_subreddit_hour.cql"
    "05_agg_global_hour.cql"
)

for schema_file in "${SCHEMA_FILES[@]}"; do
    schema_path="$SCHEMA_DIR/$schema_file"

    if [ ! -f "$schema_path" ]; then
        echo -e "${RED}Error: Schema file not found: $schema_path${NC}"
        exit 1
    fi

    echo -e "  Executing: ${BLUE}$schema_file${NC}"

    # Copy schema file to container and execute
    docker cp "$schema_path" "$CONTAINER_NAME:/tmp/$schema_file"

    if docker exec "$CONTAINER_NAME" cqlsh -f "/tmp/$schema_file"; then
        echo -e "  ${GREEN}✓ $schema_file executed successfully${NC}"
    else
        echo -e "${RED}Error: Failed to execute $schema_file${NC}"
        exit 1
    fi

    # Clean up temp file
    docker exec "$CONTAINER_NAME" rm "/tmp/$schema_file"
done

# Verify keyspace creation
echo -e "\n${YELLOW}[3/4] Verifying keyspace...${NC}"
KEYSPACE_CHECK=$(docker exec "$CONTAINER_NAME" cqlsh -e "DESCRIBE KEYSPACE reddit_rt;" 2>/dev/null || echo "")

if [ -z "$KEYSPACE_CHECK" ]; then
    echo -e "${RED}Error: Keyspace reddit_rt not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Keyspace 'reddit_rt' verified${NC}"

# List all tables
echo -e "\n${YELLOW}[4/4] Verifying tables...${NC}"
TABLES=$(docker exec "$CONTAINER_NAME" cqlsh -e "USE reddit_rt; DESCRIBE TABLES;" 2>/dev/null || echo "")

if [ -z "$TABLES" ]; then
    echo -e "${RED}Error: No tables found in keyspace reddit_rt${NC}"
    exit 1
fi

echo -e "Tables created:"
echo -e "${GREEN}$TABLES${NC}"

# Display table details
echo -e "\n${BLUE}=================================================${NC}"
echo -e "${BLUE}Table Details${NC}"
echo -e "${BLUE}=================================================${NC}"

TABLE_NAMES=("raw_posts_by_day" "classified_posts_by_hour" "agg_subreddit_hour" "agg_global_hour")

for table in "${TABLE_NAMES[@]}"; do
    echo -e "\n${YELLOW}Table: $table${NC}"
    docker exec "$CONTAINER_NAME" cqlsh -e "USE reddit_rt; DESCRIBE TABLE $table;" 2>/dev/null | head -15
    echo "..."
done

# Summary
echo -e "\n${BLUE}=================================================${NC}"
echo -e "${GREEN}✓ Schema initialization completed successfully!${NC}"
echo -e "${BLUE}=================================================${NC}"
echo -e "\nKeyspace: ${GREEN}reddit_rt${NC}"
echo -e "Tables created:"
echo -e "  1. ${GREEN}raw_posts_by_day${NC}          (TTL: 14 days)"
echo -e "  2. ${GREEN}classified_posts_by_hour${NC}  (TTL: 90 days)"
echo -e "  3. ${GREEN}agg_subreddit_hour${NC}        (TTL: 180 days)"
echo -e "  4. ${GREEN}agg_global_hour${NC}           (TTL: 180 days)"
echo -e "\nYou can now connect to Cassandra and start using the schema:"
echo -e "  ${BLUE}docker exec -it $CONTAINER_NAME cqlsh${NC}"
echo -e "  ${BLUE}USE reddit_rt;${NC}"
echo -e "  ${BLUE}DESCRIBE TABLES;${NC}"
echo ""
