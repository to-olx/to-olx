#!/bin/bash
# Performance testing script for DebtWise API

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
HOST="${HOST:-http://localhost:8000}"
USERS="${USERS:-10}"
SPAWN_RATE="${SPAWN_RATE:-2}"
RUN_TIME="${RUN_TIME:-60s}"
OUTPUT_DIR="performance_results"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            HOST="$2"
            shift 2
            ;;
        --users)
            USERS="$2"
            shift 2
            ;;
        --spawn-rate)
            SPAWN_RATE="$2"
            shift 2
            ;;
        --time)
            RUN_TIME="$2"
            shift 2
            ;;
        --web)
            WEB_MODE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --host URL          API host URL (default: http://localhost:8000)"
            echo "  --users N           Number of concurrent users (default: 10)"
            echo "  --spawn-rate N      User spawn rate per second (default: 2)"
            echo "  --time T            Test duration (default: 60s)"
            echo "  --web               Run with web UI"
            echo "  --help              Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}DebtWise API Performance Testing${NC}"
echo "=================================="
echo "Host: $HOST"
echo "Users: $USERS"
echo "Spawn Rate: $SPAWN_RATE users/s"
echo "Duration: $RUN_TIME"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Install Locust if not already installed
if ! command -v locust &> /dev/null; then
    echo -e "${YELLOW}Installing Locust...${NC}"
    pip install locust
fi

# Check if API is running
echo -e "${YELLOW}Checking API availability...${NC}"
if ! curl -f -s "$HOST/api/v1/health" > /dev/null; then
    echo -e "${RED}Error: API is not available at $HOST${NC}"
    echo "Please ensure the API is running before running performance tests."
    exit 1
fi
echo -e "${GREEN}API is available${NC}"

if [ "$WEB_MODE" = true ]; then
    # Run with web UI
    echo -e "${YELLOW}Starting Locust web UI...${NC}"
    echo "Access the web UI at: http://localhost:8089"
    locust -f locustfile.py --host "$HOST"
else
    # Run in headless mode
    echo -e "${YELLOW}Running performance tests...${NC}"
    
    # Run Locust test
    locust -f locustfile.py \
        --headless \
        --host "$HOST" \
        --users "$USERS" \
        --spawn-rate "$SPAWN_RATE" \
        --run-time "$RUN_TIME" \
        --html "$OUTPUT_DIR/report_${TIMESTAMP}.html" \
        --csv "$OUTPUT_DIR/stats_${TIMESTAMP}" \
        --loglevel INFO
    
    echo -e "${GREEN}Performance test completed!${NC}"
    echo ""
    echo "Results saved to:"
    echo "  - HTML Report: $OUTPUT_DIR/report_${TIMESTAMP}.html"
    echo "  - CSV Stats: $OUTPUT_DIR/stats_${TIMESTAMP}_stats.csv"
    echo "  - CSV History: $OUTPUT_DIR/stats_${TIMESTAMP}_stats_history.csv"
    
    # Generate summary
    echo ""
    echo -e "${YELLOW}Performance Summary:${NC}"
    echo "===================="
    
    # Parse and display key metrics from CSV
    if [ -f "$OUTPUT_DIR/stats_${TIMESTAMP}_stats.csv" ]; then
        # Skip header and aggregate row, show endpoint stats
        tail -n +2 "$OUTPUT_DIR/stats_${TIMESTAMP}_stats.csv" | head -n -1 | \
        awk -F',' '{
            printf "%-40s | Avg: %6.0fms | Med: %6.0fms | 95%%: %6.0fms | RPS: %6.1f\n", 
            $2, $6, $7, $11, $11
        }' | column -t
    fi
    
    # Check for failures
    FAILURES=$(tail -n 1 "$OUTPUT_DIR/stats_${TIMESTAMP}_stats.csv" | cut -d',' -f4)
    if [ "$FAILURES" != "0" ] && [ ! -z "$FAILURES" ]; then
        echo ""
        echo -e "${RED}Warning: $FAILURES requests failed during the test${NC}"
        echo "Please check the detailed report for more information."
    fi
fi

# Cleanup old results (keep last 10)
echo ""
echo -e "${YELLOW}Cleaning up old results...${NC}"
cd "$OUTPUT_DIR"
ls -t report_*.html 2>/dev/null | tail -n +11 | xargs -r rm
ls -t stats_*_stats.csv 2>/dev/null | tail -n +11 | xargs -r rm
ls -t stats_*_stats_history.csv 2>/dev/null | tail -n +11 | xargs -r rm
cd ..

echo -e "${GREEN}Done!${NC}"