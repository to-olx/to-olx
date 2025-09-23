#!/bin/bash
# Generate comprehensive test coverage report for DebtWise API

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COVERAGE_THRESHOLD=80
OUTPUT_DIR="coverage_reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

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

# Create output directory
mkdir -p "$OUTPUT_DIR"

log_info "DebtWise API Test Coverage Report"
echo "=================================="

# Check if in correct directory
if [ ! -f "pyproject.toml" ]; then
    log_error "Please run this script from the debtwise-api directory"
    exit 1
fi

# Install test dependencies if needed
log_info "Checking test dependencies..."
uv pip install pytest pytest-cov pytest-asyncio pytest-mock httpx

# Run tests with coverage
log_info "Running tests with coverage analysis..."

# Run full test suite with coverage
uv run pytest \
    --cov=app \
    --cov-report=term-missing \
    --cov-report=html:"$OUTPUT_DIR/htmlcov_$TIMESTAMP" \
    --cov-report=xml:"$OUTPUT_DIR/coverage_$TIMESTAMP.xml" \
    --cov-report=json:"$OUTPUT_DIR/coverage_$TIMESTAMP.json" \
    --cov-config=.coveragerc \
    -v \
    --tb=short \
    | tee "$OUTPUT_DIR/test_output_$TIMESTAMP.log"

# Extract coverage percentage
COVERAGE_PERCENT=$(grep "TOTAL" "$OUTPUT_DIR/test_output_$TIMESTAMP.log" | awk '{print $NF}' | sed 's/%//')

log_info "Overall coverage: ${COVERAGE_PERCENT}%"

# Check if coverage meets threshold
if (( $(echo "$COVERAGE_PERCENT >= $COVERAGE_THRESHOLD" | bc -l) )); then
    log_success "Coverage threshold of ${COVERAGE_THRESHOLD}% met!"
else
    log_warning "Coverage ${COVERAGE_PERCENT}% is below threshold of ${COVERAGE_THRESHOLD}%"
fi

# Generate detailed coverage report by module
log_info "Generating detailed coverage report..."

cat > "$OUTPUT_DIR/coverage_summary_$TIMESTAMP.md" <<EOF
# DebtWise API Test Coverage Report

**Date:** $(date)  
**Overall Coverage:** ${COVERAGE_PERCENT}%  
**Threshold:** ${COVERAGE_THRESHOLD}%

## Coverage by Module

| Module | Statements | Missing | Coverage |
|--------|------------|---------|----------|
EOF

# Parse coverage data and add to report
uv run coverage report --format=markdown >> "$OUTPUT_DIR/coverage_summary_$TIMESTAMP.md" 2>/dev/null || {
    # Fallback if markdown format not available
    uv run coverage report | grep -E "^app/" | while read line; do
        module=$(echo "$line" | awk '{print $1}')
        stmts=$(echo "$line" | awk '{print $2}')
        miss=$(echo "$line" | awk '{print $3}')
        cover=$(echo "$line" | awk '{print $4}')
        echo "| $module | $stmts | $miss | $cover |" >> "$OUTPUT_DIR/coverage_summary_$TIMESTAMP.md"
    done
}

# Identify files with low coverage
log_info "Identifying files with low coverage..."

echo -e "\n## Files with Coverage Below ${COVERAGE_THRESHOLD}%\n" >> "$OUTPUT_DIR/coverage_summary_$TIMESTAMP.md"

uv run coverage report | grep -E "^app/" | while read line; do
    cover_percent=$(echo "$line" | awk '{print $4}' | sed 's/%//')
    if [ ! -z "$cover_percent" ] && (( $(echo "$cover_percent < $COVERAGE_THRESHOLD" | bc -l) )); then
        module=$(echo "$line" | awk '{print $1}')
        echo "- **$module**: $cover_percent%" >> "$OUTPUT_DIR/coverage_summary_$TIMESTAMP.md"
    fi
done

# Add uncovered lines summary
echo -e "\n## Uncovered Lines by Module\n" >> "$OUTPUT_DIR/coverage_summary_$TIMESTAMP.md"

# Get detailed missing lines
uv run coverage report -m | grep -A 1000 "TOTAL" | tail -n +2 | grep -E "^app/" | while read line; do
    if [[ $line == *":"* ]]; then
        module=$(echo "$line" | cut -d: -f1)
        missing=$(echo "$line" | cut -d: -f2-)
        if [ ! -z "$missing" ] && [ "$missing" != " " ]; then
            echo "- **$module**: Lines $missing" >> "$OUTPUT_DIR/coverage_summary_$TIMESTAMP.md"
        fi
    fi
done

# Test execution summary
echo -e "\n## Test Execution Summary\n" >> "$OUTPUT_DIR/coverage_summary_$TIMESTAMP.md"

# Extract test summary from output
grep -E "(passed|failed|skipped|error)" "$OUTPUT_DIR/test_output_$TIMESTAMP.log" | tail -1 >> "$OUTPUT_DIR/coverage_summary_$TIMESTAMP.md"

# Add recommendations
cat >> "$OUTPUT_DIR/coverage_summary_$TIMESTAMP.md" <<EOF

## Recommendations for Improving Coverage

1. **Priority Areas** (lowest coverage):
   - Review and add tests for modules below ${COVERAGE_THRESHOLD}%
   - Focus on critical business logic first

2. **Test Types to Add**:
   - Unit tests for uncovered functions
   - Integration tests for API endpoints
   - Edge case and error handling tests

3. **Quick Wins**:
   - Add tests for simple utility functions
   - Test error conditions and exceptions
   - Cover configuration and initialization code

## Coverage Reports

- **HTML Report**: \`$OUTPUT_DIR/htmlcov_$TIMESTAMP/index.html\`
- **XML Report**: \`$OUTPUT_DIR/coverage_$TIMESTAMP.xml\`
- **JSON Report**: \`$OUTPUT_DIR/coverage_$TIMESTAMP.json\`
EOF

# Generate coverage badge
BADGE_COLOR="red"
if (( $(echo "$COVERAGE_PERCENT >= 90" | bc -l) )); then
    BADGE_COLOR="brightgreen"
elif (( $(echo "$COVERAGE_PERCENT >= 80" | bc -l) )); then
    BADGE_COLOR="green"
elif (( $(echo "$COVERAGE_PERCENT >= 70" | bc -l) )); then
    BADGE_COLOR="yellow"
elif (( $(echo "$COVERAGE_PERCENT >= 60" | bc -l) )); then
    BADGE_COLOR="orange"
fi

cat > "$OUTPUT_DIR/coverage_badge.json" <<EOF
{
    "schemaVersion": 1,
    "label": "coverage",
    "message": "${COVERAGE_PERCENT}%",
    "color": "$BADGE_COLOR"
}
EOF

log_success "Coverage report generated!"
echo ""
echo "Reports saved in: $OUTPUT_DIR/"
echo "- Summary: $OUTPUT_DIR/coverage_summary_$TIMESTAMP.md"
echo "- HTML: $OUTPUT_DIR/htmlcov_$TIMESTAMP/index.html"
echo "- Badge: $OUTPUT_DIR/coverage_badge.json"

# Open HTML report if possible
if command -v open &> /dev/null; then
    open "$OUTPUT_DIR/htmlcov_$TIMESTAMP/index.html"
elif command -v xdg-open &> /dev/null; then
    xdg-open "$OUTPUT_DIR/htmlcov_$TIMESTAMP/index.html"
fi

# Exit with appropriate code
if (( $(echo "$COVERAGE_PERCENT >= $COVERAGE_THRESHOLD" | bc -l) )); then
    exit 0
else
    exit 1
fi