# Predictive Insights Feature Documentation

## Overview

The Predictive Insights feature in DebtWise provides users with AI-powered financial forecasting, anomaly detection, and personalized recommendations to help them make better financial decisions.

## Key Features

### 1. Spending Forecasts
- **What it does**: Predicts future spending based on historical transaction patterns
- **Algorithms**: Statistical trend analysis with linear regression and seasonal pattern detection
- **Confidence levels**: Each forecast includes confidence intervals and accuracy scores
- **Granularity**: Can forecast by category or overall spending

### 2. Cash Flow Forecasts
- **What it does**: Projects account balances and identifies potential cash flow issues
- **Risk assessment**: Calculates overdraft risk and minimum balance warnings
- **Scheduled transactions**: Accounts for recurring bills and income
- **Time horizons**: 7-day, 30-day, and custom period forecasts

### 3. Anomaly Detection
- **What it does**: Identifies unusual spending patterns and transactions
- **Detection methods**: Z-score analysis within categories
- **Anomaly types**: Amount-based, frequency-based, category mismatches
- **User feedback**: Allows confirmation or dismissal of detected anomalies

### 4. Predictive Insights
- **What it does**: Generates actionable insights based on spending patterns
- **Insight types**:
  - Budget projections and warnings
  - Spending trend analysis
  - Cash flow alerts
  - Savings opportunities
- **Severity levels**: INFO, SUCCESS, WARNING, CRITICAL
- **Action items**: Each insight includes specific recommendations

### 5. Dashboard Summary
- **What it does**: Provides a comprehensive overview of financial health
- **Key metrics**:
  - Current vs predicted spending
  - Budget utilization
  - Active alerts by severity
  - Total savings opportunities
  - Cash flow projections

## API Endpoints

### Generate Forecasts
```
POST /api/v1/insights/forecasts/generate
```
Generate new spending or cash flow forecasts.

**Request Body:**
```json
{
  "forecast_type": "spending",
  "time_period": "30d",
  "category_ids": [1, 2, 3]
}
```

### Get Spending Forecasts
```
GET /api/v1/insights/forecasts/spending
```
Retrieve existing spending forecasts with optional filters.

### Get Cash Flow Forecasts
```
GET /api/v1/insights/forecasts/cashflow
```
Retrieve cash flow projections for specific dates.

### Get Insights
```
GET /api/v1/insights
```
Get predictive insights with filtering options.

**Query Parameters:**
- `insight_type`: Filter by type (SPENDING_FORECAST, BUDGET_PROJECTION, etc.)
- `severity`: Filter by severity (INFO, SUCCESS, WARNING, CRITICAL)
- `status`: Filter by status (ACTIVE, ACKNOWLEDGED, RESOLVED, DISMISSED)

### Generate New Insights
```
POST /api/v1/insights/generate
```
Trigger generation of new insights based on current data.

### Update Insight Status
```
PATCH /api/v1/insights/{insight_id}
```
Acknowledge or dismiss an insight.

### Get Anomalies
```
GET /api/v1/insights/anomalies
```
Get detected spending anomalies.

### Get Dashboard Summary
```
GET /api/v1/insights/dashboard
```
Get comprehensive dashboard data.

## Data Models

### SpendingForecast
Stores predicted spending amounts with confidence levels and model metadata.

### CashflowForecast
Tracks projected account balances and overdraft risks.

### PredictiveInsight
Contains actionable insights with recommendations and impact metrics.

### SpendingAnomaly
Records detected unusual transactions with anomaly scores.

## Implementation Details

### Forecasting Algorithm
1. **Data Collection**: Gathers historical transactions (up to 1 year)
2. **Pattern Detection**: Identifies recurring transactions and seasonal trends
3. **Trend Analysis**: Uses linear regression to detect spending trends
4. **Prediction**: Projects future spending with confidence intervals
5. **Validation**: Compares predictions with actuals to improve accuracy

### Anomaly Detection Algorithm
1. **Categorization**: Groups transactions by category
2. **Statistical Analysis**: Calculates mean and standard deviation per category
3. **Z-Score Calculation**: Identifies transactions beyond 2.5 standard deviations
4. **Context Enrichment**: Adds merchant and timing context
5. **User Feedback Loop**: Learns from user confirmations/dismissals

### Insight Generation Process
1. **Data Analysis**: Runs multiple analysis passes on user data
2. **Pattern Recognition**: Identifies concerning trends or opportunities
3. **Severity Assessment**: Assigns appropriate severity levels
4. **Recommendation Engine**: Generates specific action items
5. **Deduplication**: Prevents duplicate insights

## Usage Examples

### Example 1: Generate Monthly Spending Forecast
```python
# Request
POST /api/v1/insights/forecasts/generate
{
  "forecast_type": "spending",
  "time_period": "30d"
}

# Response
{
  "spending_forecast": {
    "predicted_amount": 3500.00,
    "confidence_level": 0.85,
    "trend_direction": "increasing",
    "trend_percentage": 5.2
  }
}
```

### Example 2: Get Critical Insights
```python
# Request
GET /api/v1/insights?severity=CRITICAL&status=ACTIVE

# Response
[
  {
    "title": "Budget Overspending Alert",
    "description": "You've used 90% of your Food budget...",
    "severity": "CRITICAL",
    "recommendation": "Reduce spending to $10/day...",
    "potential_savings": 150.00
  }
]
```

## Best Practices

1. **Regular Updates**: Generate insights at least weekly for best results
2. **User Engagement**: Encourage users to confirm/dismiss anomalies for better accuracy
3. **Action Tracking**: Monitor which recommendations users follow
4. **Model Improvement**: Regularly retrain models with new data
5. **Privacy**: Ensure all predictions respect user privacy settings

## Future Enhancements

1. **Machine Learning Models**: Implement more sophisticated ML algorithms
2. **External Data Integration**: Include economic indicators and seasonal factors
3. **Peer Comparisons**: Anonymous spending comparisons within demographics
4. **Goal-Based Insights**: Tie predictions to user's financial goals
5. **Natural Language Insights**: More conversational insight descriptions