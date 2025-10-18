#!/bin/bash
# Airflow Logs Viewer
#
# This script helps view logs from Airflow components

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# Check arguments
if [ $# -eq 0 ]; then
    echo "Usage: $0 [webserver|scheduler|all] [--follow]"
    echo ""
    echo "Examples:"
    echo "  $0 webserver           # Show webserver logs"
    echo "  $0 scheduler --follow  # Follow scheduler logs"
    echo "  $0 all                 # Show all Airflow logs"
    exit 1
fi

COMPONENT=$1
FOLLOW_FLAG=""

if [ "$2" == "--follow" ] || [ "$2" == "-f" ]; then
    FOLLOW_FLAG="-f"
fi

case $COMPONENT in
    webserver)
        print_info "Viewing Airflow Webserver logs..."
        docker logs $FOLLOW_FLAG reddit-airflow-webserver
        ;;
    scheduler)
        print_info "Viewing Airflow Scheduler logs..."
        docker logs $FOLLOW_FLAG reddit-airflow-scheduler
        ;;
    postgres)
        print_info "Viewing Airflow Postgres logs..."
        docker logs $FOLLOW_FLAG reddit-airflow-postgres
        ;;
    all)
        print_info "Viewing all Airflow logs..."
        echo "=== Webserver Logs ==="
        docker logs --tail 20 reddit-airflow-webserver
        echo ""
        echo "=== Scheduler Logs ==="
        docker logs --tail 20 reddit-airflow-scheduler
        echo ""
        echo "=== Postgres Logs ==="
        docker logs --tail 10 reddit-airflow-postgres
        ;;
    *)
        echo "Unknown component: $COMPONENT"
        echo "Valid components: webserver, scheduler, postgres, all"
        exit 1
        ;;
esac
