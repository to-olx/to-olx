#!/bin/bash
# Comprehensive load testing script for DebtWise API

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
HOST="${HOST:-http://localhost:8000}"
OUTPUT_DIR="load_test_results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Test scenarios
declare -A SCENARIOS=(
    ["baseline"]="10:1:60s"           # 10 users, 1/s spawn, 1 min
    ["normal_load"]="100:5:300s"      # 100 users, 5/s spawn, 5 min
    ["high_load"]="500:10:600s"       # 500 users, 10/s spawn, 10 min
    ["stress_test"]="1000:20:300s"    # 1000 users, 20/s spawn, 5 min
    ["spike_test"]="0:100:120s"       # 0 to 100 users instantly, 2 min
    ["endurance"]="200:5:1800s"       # 200 users, 5/s spawn, 30 min
)

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if Locust is installed
    if ! command -v locust &> /dev/null; then
        log_warning "Locust not found. Installing..."
        pip install locust
    fi
    
    # Check if API is running
    if ! curl -f -s "$HOST/api/v1/health" > /dev/null; then
        log_error "API is not available at $HOST"
        exit 1
    fi
    
    # Create output directory
    mkdir -p "$OUTPUT_DIR/$TIMESTAMP"
    
    log_success "Prerequisites check passed"
}

run_scenario() {
    local scenario_name=$1
    local config=$2
    
    IFS=':' read -r users spawn_rate duration <<< "$config"
    
    log_info "Running scenario: $scenario_name"
    log_info "Configuration: $users users, $spawn_rate spawn/s, $duration duration"
    
    local output_prefix="$OUTPUT_DIR/$TIMESTAMP/${scenario_name}"
    
    # Run Locust
    locust \
        -f load_test_scenarios.py \
        --headless \
        --host "$HOST" \
        --users "$users" \
        --spawn-rate "$spawn_rate" \
        --run-time "$duration" \
        --html "${output_prefix}_report.html" \
        --csv "${output_prefix}" \
        --loglevel INFO \
        --logfile "${output_prefix}.log" \
        --exit-code-on-error 1
    
    # Analyze results
    analyze_results "$scenario_name" "$output_prefix"
}

analyze_results() {
    local scenario_name=$1
    local output_prefix=$2
    
    log_info "Analyzing results for $scenario_name..."
    
    # Create analysis report
    cat > "${output_prefix}_analysis.txt" <<EOF
Load Test Analysis: $scenario_name
Date: $(date)
=====================================

Summary Statistics:
EOF
    
    # Extract key metrics from CSV
    if [ -f "${output_prefix}_stats.csv" ]; then
        # Parse CSV and extract important metrics
        tail -n +2 "${output_prefix}_stats.csv" | awk -F',' '
        {
            if ($2 != "Aggregated") {
                printf "%-40s | Requests: %d | Failures: %d | Avg: %.0fms | Med: %.0fms | 95%%: %.0fms\n", 
                    $2, $3, $4, $6, $7, $11
            }
        }' >> "${output_prefix}_analysis.txt"
        
        # Check for failures
        local total_failures=$(tail -n +2 "${output_prefix}_stats.csv" | awk -F',' '{sum+=$4} END {print sum}')
        
        if [ "$total_failures" -gt 0 ]; then
            log_warning "Scenario $scenario_name had $total_failures failed requests"
        else
            log_success "Scenario $scenario_name completed with no failures"
        fi
    fi
}

generate_summary_report() {
    log_info "Generating summary report..."
    
    local summary_file="$OUTPUT_DIR/$TIMESTAMP/LOAD_TEST_SUMMARY.md"
    
    cat > "$summary_file" <<EOF
# DebtWise API Load Test Summary

**Date:** $(date)  
**Host:** $HOST  
**Test Duration:** $((SECONDS / 60)) minutes

## Test Scenarios Run

EOF
    
    # Add scenario results
    for scenario in "${!SCENARIOS[@]}"; do
        if [ -f "$OUTPUT_DIR/$TIMESTAMP/${scenario}_stats.csv" ]; then
            echo "### $scenario" >> "$summary_file"
            echo "" >> "$summary_file"
            
            # Extract aggregated stats
            tail -1 "$OUTPUT_DIR/$TIMESTAMP/${scenario}_stats.csv" | awk -F',' '{
                printf "- **Total Requests:** %d\n", $3
                printf "- **Failed Requests:** %d (%.2f%%)\n", $4, ($4/$3)*100
                printf "- **Average Response Time:** %.0fms\n", $6
                printf "- **Median Response Time:** %.0fms\n", $7
                printf "- **95th Percentile:** %.0fms\n", $11
                printf "- **Requests per Second:** %.2f\n\n", $10
            }' >> "$summary_file"
        fi
    done
    
    # Add recommendations
    cat >> "$summary_file" <<EOF

## Recommendations

Based on the load test results:

1. **Performance Optimization Needed:**
   - Endpoints with response times > 500ms should be optimized
   - Consider caching for frequently accessed data

2. **Scaling Requirements:**
   - Current infrastructure can handle X concurrent users
   - Recommend horizontal scaling at Y users

3. **Error Handling:**
   - Review and fix any endpoints with high failure rates
   - Implement better error recovery mechanisms

## Detailed Reports

Individual scenario reports are available in:
\`$OUTPUT_DIR/$TIMESTAMP/\`

EOF
    
    log_success "Summary report generated: $summary_file"
}

# Main execution
main() {
    log_info "DebtWise API Load Testing Suite"
    echo "================================="
    
    # Check prerequisites
    check_prerequisites
    
    # Parse command line arguments
    case "${1:-all}" in
        baseline|normal_load|high_load|stress_test|spike_test|endurance)
            # Run specific scenario
            run_scenario "$1" "${SCENARIOS[$1]}"
            ;;
        all)
            # Run all scenarios
            for scenario in baseline normal_load high_load stress_test; do
                run_scenario "$scenario" "${SCENARIOS[$scenario]}"
                
                # Wait between scenarios
                if [ "$scenario" != "stress_test" ]; then
                    log_info "Waiting 30 seconds before next scenario..."
                    sleep 30
                fi
            done
            ;;
        custom)
            # Custom scenario
            if [ -z "$2" ] || [ -z "$3" ] || [ -z "$4" ]; then
                echo "Usage: $0 custom <users> <spawn-rate> <duration>"
                exit 1
            fi
            run_scenario "custom" "$2:$3:$4"
            ;;
        *)
            echo "Usage: $0 {baseline|normal_load|high_load|stress_test|spike_test|endurance|all|custom}"
            echo ""
            echo "Scenarios:"
            for scenario in "${!SCENARIOS[@]}"; do
                echo "  - $scenario: ${SCENARIOS[$scenario]}"
            done
            exit 1
            ;;
    esac
    
    # Generate summary report
    generate_summary_report
    
    # Open reports in browser if available
    if command -v open &> /dev/null; then
        open "$OUTPUT_DIR/$TIMESTAMP/LOAD_TEST_SUMMARY.md"
    elif command -v xdg-open &> /dev/null; then
        xdg-open "$OUTPUT_DIR/$TIMESTAMP/LOAD_TEST_SUMMARY.md"
    fi
    
    log_success "Load testing completed!"
    echo ""
    echo "Results saved in: $OUTPUT_DIR/$TIMESTAMP/"
}

# Record start time
SECONDS=0

# Run main function
main "$@"