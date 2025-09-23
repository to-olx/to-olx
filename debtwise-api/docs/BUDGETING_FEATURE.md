# DebtWise Budgeting Feature

## Overview

The DebtWise budgeting feature provides comprehensive budget management capabilities including:

- **Multiple Budget Periods**: Support for weekly, monthly, quarterly, and yearly budgets
- **Budget Rollovers**: Carry forward unused budget amounts to future periods
- **Budget Alerts**: Configurable notifications when spending reaches certain thresholds
- **Budget Summaries**: Real-time tracking and analytics for budget performance
- **Category & Total Budgets**: Set budgets for specific categories or overall spending

## Architecture

### Database Models

#### Budget Model (`app/models/budget.py`)
- **Budget**: Main budget configuration
  - Links to user and optionally to a category
  - Defines period type, start date, and amount
  - Configures rollover settings
  - Supports budget alerts

- **BudgetPeriod**: Tracks spending within specific time periods
  - Automatically created for each budget period
  - Tracks base amount, rollover, and actual spending
  - Calculates remaining budget in real-time

- **BudgetAlert**: Configurable spending alerts
  - Threshold-based notifications (e.g., alert at 80% spent)
  - Email and push notification support
  - Custom alert messages

### API Endpoints

#### Budget Management
- `POST /api/v1/budgets/budgets` - Create a new budget
- `GET /api/v1/budgets/budgets` - List all budgets
- `GET /api/v1/budgets/budgets/{budget_id}` - Get specific budget
- `PUT /api/v1/budgets/budgets/{budget_id}` - Update budget
- `DELETE /api/v1/budgets/budgets/{budget_id}` - Delete budget

#### Budget Analytics
- `GET /api/v1/budgets/budgets/summary/overview` - Overall budget overview
- `GET /api/v1/budgets/budgets/{budget_id}/summary` - Specific budget summary
- `GET /api/v1/budgets/budgets/{budget_id}/current-period` - Current period details

#### Budget Operations
- `POST /api/v1/budgets/budgets/rollover` - Process budget rollovers
- `POST /api/v1/budgets/budgets/{budget_id}/alerts` - Create budget alert
- `PUT /api/v1/budgets/budgets/alerts/{alert_id}` - Update alert
- `DELETE /api/v1/budgets/budgets/alerts/{alert_id}` - Delete alert

## Features

### 1. Budget Creation

Create budgets with various configurations:

```python
{
    "name": "Monthly Groceries",
    "description": "Budget for grocery shopping",
    "category_id": 1,  # Optional: null for total budget
    "period_type": "monthly",  # weekly, monthly, quarterly, yearly
    "start_date": "2024-01-01",
    "amount": "500.00",
    "allow_rollover": true,
    "max_rollover_periods": 3,  # Optional: limit rollover accumulation
    "max_rollover_amount": "150.00",  # Optional: cap rollover amount
    "is_active": true
}
```

### 2. Budget Periods

Budget periods are automatically created and managed:

- **Initial Period**: Created when budget is created
- **Subsequent Periods**: Generated as needed with rollover calculations
- **Period Tracking**: Each period tracks:
  - Base amount (from budget configuration)
  - Rollover amount (from previous periods)
  - Total amount (base + rollover)
  - Spent amount (actual transactions)
  - Remaining amount (total - spent)

### 3. Budget Rollovers

Unused budget can roll over to future periods:

```python
# Process rollover for a budget
POST /api/v1/budgets/budgets/rollover
{
    "budget_id": 1,
    "period_date": "2024-02-01"  # Optional: defaults to today
}
```

Rollover features:
- **Automatic Calculation**: Unused amounts carry forward
- **Configurable Limits**: Set maximum periods or amounts
- **Period Closing**: Previous periods are closed when rolling over

### 4. Budget Alerts

Set up notifications for budget thresholds:

```python
{
    "threshold_percentage": 80,  # Alert at 80% spent
    "alert_message": "You've used 80% of your grocery budget",
    "is_enabled": true,
    "send_email": true,
    "send_push": false
}
```

### 5. Budget Summaries

Get comprehensive budget analytics:

```json
{
    "budget_id": 1,
    "budget_name": "Monthly Groceries",
    "category_name": "Groceries",
    "period_type": "monthly",
    "current_period": {
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "total_amount": "650.00",  // Including rollover
        "spent_amount": "425.50",
        "remaining_amount": "224.50"
    },
    "total_budgeted": "650.00",
    "total_spent": "425.50",
    "total_remaining": "224.50",
    "percentage_used": 65.5,
    "days_remaining": 10,
    "average_monthly_spending": "380.25",
    "projected_end_of_period": "520.75",
    "active_alerts": [],
    "is_over_budget": false
}
```

## Usage Examples

### Example 1: Create a Monthly Budget with Rollover

```python
# Create a budget for groceries
response = client.post("/api/v1/budgets/budgets", json={
    "name": "Monthly Groceries",
    "category_id": grocery_category_id,
    "period_type": "monthly",
    "start_date": "2024-01-01",
    "amount": "500.00",
    "allow_rollover": True,
    "max_rollover_periods": 3,
    "alerts": [
        {
            "threshold_percentage": 80,
            "send_email": True
        }
    ]
})
```

### Example 2: Get Budget Overview

```python
# Get overview of all budgets
response = client.get("/api/v1/budgets/budgets/summary/overview")

# Response includes:
# - Total budgeted across all categories
# - Total spent
# - Individual budget summaries
# - Unbudgeted spending
```

### Example 3: Process Monthly Rollover

```python
# At the end of the month, process rollovers
response = client.post("/api/v1/budgets/budgets/rollover", json={
    "budget_id": budget_id
})

# Response shows:
# - Previous period summary
# - New period with rollover amount
# - Success status
```

## Best Practices

### 1. Budget Planning
- Start with category-specific budgets for detailed tracking
- Add a total budget to monitor overall spending
- Use realistic amounts based on historical spending

### 2. Rollover Configuration
- Enable rollover for variable expenses (groceries, entertainment)
- Disable rollover for fixed expenses (rent, subscriptions)
- Set reasonable limits to prevent excessive accumulation

### 3. Alert Management
- Set multiple alert thresholds (50%, 80%, 100%)
- Use custom messages for context
- Review and adjust thresholds based on spending patterns

### 4. Period Management
- Choose appropriate period types for different expenses
- Weekly for variable daily expenses
- Monthly for regular bills
- Quarterly/Yearly for seasonal expenses

## Implementation Details

### Service Layer (`app/services/budget.py`)

The budget service handles:
- Budget CRUD operations
- Period creation and management
- Rollover calculations
- Spending calculations
- Summary generation

### Key Methods:
- `create_budget()`: Creates budget with initial period
- `process_rollover()`: Handles period transitions
- `get_budget_summary()`: Generates analytics
- `_update_period_spent_amount()`: Calculates actual spending

### Integration with Transactions

The budget system integrates with the transaction system:
- Transactions are automatically counted against budgets
- Budget summaries reflect real-time spending
- Category-based or total spending tracking

## Future Enhancements

Potential improvements for the budgeting feature:

1. **Budget Templates**: Pre-defined budget configurations
2. **Budget Goals**: Savings targets and goals
3. **Budget Sharing**: Family/group budget management
4. **Advanced Analytics**: Trends, predictions, and insights
5. **Mobile Notifications**: Real-time push notifications
6. **Budget Recommendations**: AI-powered budget suggestions
7. **Export/Import**: Budget data portability
8. **Recurring Adjustments**: Seasonal budget modifications

## Testing

Run the budget example script:

```bash
python examples/budget_example.py
```

This demonstrates:
- Creating budgets with different configurations
- Setting up alerts
- Adding transactions
- Viewing summaries
- Processing rollovers

## API Reference

See the API documentation for detailed endpoint specifications:
- Request/response schemas
- Error codes
- Authentication requirements
- Rate limits