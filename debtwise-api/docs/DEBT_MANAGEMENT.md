# Debt Management Feature Documentation

## Overview

The Debt Management feature in DebtWise helps users track, manage, and pay off their debts efficiently. It includes comprehensive debt tracking, payment recording, interest calculations, and intelligent payoff strategies.

## Features

### 1. Debt Tracking
- **Create and manage multiple debts**: Track credit cards, loans, mortgages, and more
- **Detailed debt information**: Original amount, current balance, interest rates, minimum payments
- **Debt categorization**: Credit card, personal loan, student loan, mortgage, auto loan, medical debt
- **Status tracking**: Active, paid off, in collections, written off

### 2. Payment Recording
- **Track all payments**: Record regular and extra payments
- **Automatic calculations**: Principal vs interest breakdown
- **Payment history**: Complete record of all payments made
- **Balance updates**: Automatic balance reduction after payments

### 3. Debt Calculators
- **Interest calculator**: Calculate total interest and payoff timeline
- **Monthly breakdown**: See how payments are applied over time
- **What-if scenarios**: Test different payment amounts

### 4. Payoff Strategies
- **Snowball method**: Pay off smallest balances first (psychological wins)
- **Avalanche method**: Pay off highest interest rates first (save money)
- **Custom plans**: Create your own payoff order
- **Extra payment allocation**: Optimize where extra payments go

### 5. Analytics and Insights
- **Debt summary**: Total debt, paid amounts, interest paid
- **Progress tracking**: Monitor debt reduction over time
- **Payoff projections**: See when you'll be debt-free

## API Endpoints

### Debt Management

#### Get Debt Summary
```
GET /api/v1/debts/summary
```
Returns comprehensive statistics about user's debts.

#### List All Debts
```
GET /api/v1/debts/
Query params:
  - include_inactive: boolean (default: false)
  - debt_type: string (filter by type)
```

#### Get Specific Debt
```
GET /api/v1/debts/{debt_id}
```

#### Create New Debt
```
POST /api/v1/debts/
Body: {
  "name": "string",
  "description": "string",
  "debt_type": "credit_card|personal_loan|student_loan|mortgage|auto_loan|medical_debt|other",
  "original_amount": "decimal",
  "current_balance": "decimal",
  "interest_rate": "decimal (APR)",
  "minimum_payment": "decimal",
  "due_date": "integer (1-31)",
  "origination_date": "date"
}
```

#### Update Debt
```
PATCH /api/v1/debts/{debt_id}
Body: Partial debt object
```

#### Delete Debt
```
DELETE /api/v1/debts/{debt_id}
```
Performs soft delete (marks as inactive).

### Payment Management

#### Record Payment
```
POST /api/v1/debts/payments
Body: {
  "debt_id": "integer",
  "amount": "decimal",
  "payment_date": "date",
  "notes": "string",
  "is_extra_payment": "boolean"
}
```

#### Get Payment History
```
GET /api/v1/debts/{debt_id}/payments
```

### Calculators and Planning

#### Generate Payoff Plan
```
POST /api/v1/debts/payoff-plan
Body: {
  "strategy": "snowball|avalanche|custom",
  "extra_monthly_payment": "decimal",
  "debt_ids": ["integer"] (optional)
}
```

#### Interest Calculator
```
POST /api/v1/debts/calculator/interest
Body: {
  "principal": "decimal",
  "interest_rate": "decimal (APR)",
  "payment_amount": "decimal"
}
```

## Database Schema

### Debts Table
- `id`: Primary key
- `user_id`: Foreign key to users
- `name`: Debt name/description
- `debt_type`: Enum (credit_card, personal_loan, etc.)
- `original_amount`: Original debt amount
- `current_balance`: Current outstanding balance
- `interest_rate`: Annual percentage rate (APR)
- `minimum_payment`: Minimum monthly payment
- `due_date`: Day of month payment is due
- `origination_date`: When debt was created
- `status`: Enum (active, paid_off, etc.)
- `is_active`: Soft delete flag
- `created_at`, `updated_at`: Timestamps

### Debt Payments Table
- `id`: Primary key
- `debt_id`: Foreign key to debts
- `user_id`: Foreign key to users
- `amount`: Total payment amount
- `payment_date`: Date of payment
- `principal_amount`: Amount applied to principal
- `interest_amount`: Amount applied to interest
- `notes`: Optional payment notes
- `is_extra_payment`: Flag for extra payments
- `created_at`, `updated_at`: Timestamps

## Business Logic

### Interest Calculation
- Monthly interest rate = Annual rate / 12
- Monthly interest charge = Current balance × Monthly rate
- Principal payment = Total payment - Interest charge

### Payoff Strategies

#### Snowball Method
1. Make minimum payments on all debts
2. Apply extra payment to debt with smallest balance
3. When a debt is paid off, add its payment to the next smallest
4. Provides psychological wins and momentum

#### Avalanche Method
1. Make minimum payments on all debts
2. Apply extra payment to debt with highest interest rate
3. When a debt is paid off, add its payment to the next highest rate
4. Mathematically optimal - saves the most money

### Payment Processing
1. Calculate interest portion based on current balance
2. Apply remaining payment to principal
3. Update debt balance
4. Mark as paid off if balance reaches zero
5. Track payment history for reporting

## Testing

The feature includes comprehensive tests:
- Unit tests for debt service methods
- Integration tests for API endpoints
- Calculator accuracy tests
- Access control tests
- Edge case handling

## Security

- All debt operations require authentication
- Users can only access their own debts
- Soft delete preserves data integrity
- Input validation prevents invalid data

## Future Enhancements

1. **Automated payment reminders**: Email/SMS notifications
2. **Credit score impact**: Show how payoff affects credit
3. **Debt consolidation calculator**: Compare consolidation options
4. **Payment scheduling**: Set up recurring payments
5. **Goal setting**: Set debt-free target dates
6. **Visual analytics**: Charts and graphs of progress
7. **Export functionality**: Download payment history
8. **Multi-currency support**: Handle international debts