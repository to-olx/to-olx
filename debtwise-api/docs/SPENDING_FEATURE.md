# Spending Feature Documentation

## Overview

The spending feature in DebtWise provides comprehensive transaction tracking, categorization, and import functionality. This document outlines the implementation details, API endpoints, and usage instructions.

## Features Implemented

### 1. Transaction Management
- **CRUD Operations**: Create, read, update, and delete transactions
- **Transaction Types**: Income, Expense, and Transfer
- **Filtering & Search**: Advanced filtering by date, category, amount, tags, etc.
- **Tagging System**: Add multiple tags to transactions for better organization

### 2. Category Management
- **Hierarchical Categories**: Support for parent-child category relationships
- **Budget Tracking**: Set monthly budgets per category
- **Category Types**: Separate categories for income and expenses
- **Default Categories**: Pre-defined categories for new users

### 3. Transaction Rules
- **Auto-categorization**: Automatically assign categories based on patterns
- **Pattern Matching**: Use regex patterns for description and merchant matching
- **Priority System**: Rules are applied based on priority order
- **Bulk Application**: Apply rules to existing transactions

### 4. CSV Import
- **Flexible Import**: Configurable column mapping for different bank formats
- **Duplicate Detection**: Skip already imported transactions
- **Auto-categorization**: Apply rules during import
- **Error Handling**: Detailed error reporting for failed imports

## Database Models

### Transaction
```python
- id: Primary key
- user_id: Foreign key to User
- category_id: Foreign key to Category (nullable)
- amount: Decimal (10,2)
- transaction_date: Date
- description: String(500)
- transaction_type: Enum (income/expense/transfer)
- account_name: String(100) (nullable)
- merchant: String(255) (nullable)
- notes: Text (nullable)
- tags: String(500) - comma-separated
- import_id: String(100) - for duplicate detection
- is_recurring: Boolean
- created_at: DateTime
- updated_at: DateTime
```

### Category
```python
- id: Primary key
- user_id: Foreign key to User
- parent_id: Self-referential foreign key (nullable)
- name: String(100)
- icon: String(50) (nullable) - emoji or icon name
- color: String(7) (nullable) - hex color code
- transaction_type: Enum (income/expense)
- budget_amount: Decimal(10,2) (nullable)
- is_active: Boolean
- created_at: DateTime
- updated_at: DateTime
```

### TransactionRule
```python
- id: Primary key
- user_id: Foreign key to User
- category_id: Foreign key to Category
- name: String(100)
- description_pattern: String(500) - regex pattern
- merchant_pattern: String(500) - regex pattern
- amount_min: Decimal(10,2) (nullable)
- amount_max: Decimal(10,2) (nullable)
- transaction_type: Enum (nullable)
- priority: Integer (0-1000)
- is_active: Boolean
- created_at: DateTime
- updated_at: DateTime
```

## API Endpoints

### Transaction Endpoints

#### Create Transaction
```http
POST /api/v1/spending/transactions
Authorization: Bearer <token>
Content-Type: application/json

{
  "amount": 45.99,
  "transaction_date": "2024-01-15",
  "description": "Grocery shopping",
  "transaction_type": "expense",
  "category_id": 5,
  "merchant": "Whole Foods",
  "tags": "groceries,food",
  "is_recurring": false
}
```

#### List Transactions
```http
GET /api/v1/spending/transactions?skip=0&limit=100&start_date=2024-01-01&category_ids=5,6
Authorization: Bearer <token>
```

Query Parameters:
- `skip`: Pagination offset (default: 0)
- `limit`: Number of results (default: 100, max: 1000)
- `start_date`: Filter by start date
- `end_date`: Filter by end date
- `category_ids`: List of category IDs
- `transaction_type`: Filter by type (income/expense/transfer)
- `min_amount`: Minimum amount
- `max_amount`: Maximum amount
- `search_text`: Search in description and merchant
- `tags`: List of tags to filter by
- `account_names`: List of account names
- `is_recurring`: Filter recurring transactions

#### Update Transaction
```http
PATCH /api/v1/spending/transactions/{transaction_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "category_id": 7,
  "tags": "groceries,organic"
}
```

#### Delete Transaction
```http
DELETE /api/v1/spending/transactions/{transaction_id}
Authorization: Bearer <token>
```

### Category Endpoints

#### Create Category
```http
POST /api/v1/spending/categories
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Restaurants",
  "parent_id": 5,
  "icon": "🍽️",
  "color": "#FF5733",
  "transaction_type": "expense",
  "budget_amount": 200.00
}
```

#### List Categories
```http
GET /api/v1/spending/categories?include_inactive=false
Authorization: Bearer <token>
```

#### Create Default Categories
```http
POST /api/v1/spending/categories/defaults
Authorization: Bearer <token>
```

Creates the following default categories:
- **Income**: Salary, Freelance, Investment, Other Income
- **Expenses**: Food & Dining, Transportation, Shopping, Entertainment, Bills & Utilities, Healthcare, Education, Home, Insurance, Personal Care, Gifts & Donations, Other

### Transaction Rule Endpoints

#### Create Rule
```http
POST /api/v1/spending/rules
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Starbucks to Coffee",
  "category_id": 12,
  "description_pattern": "STARBUCKS|COFFEE",
  "merchant_pattern": "STARBUCKS",
  "priority": 100
}
```

#### Apply Rules to Existing Transactions
```http
POST /api/v1/spending/rules/apply?override_existing=false
Authorization: Bearer <token>
```

### CSV Import Endpoint

#### Import Transactions
```http
POST /api/v1/spending/transactions/import
Authorization: Bearer <token>
Content-Type: multipart/form-data

Form fields:
- file: CSV file
- date_format: %Y-%m-%d (default)
- date_column: Date
- amount_column: Amount
- description_column: Description
- merchant_column: Merchant (optional)
- category_column: Category (optional)
- account_column: Account (optional)
- tags_column: Tags (optional)
- skip_duplicates: true (default)
- auto_categorize: true (default)
- default_account: Checking (optional)
```

#### CSV Format Example
```csv
Date,Description,Amount,Merchant,Category
2024-01-15,Grocery Shopping,-45.99,Whole Foods,Food & Dining
2024-01-16,Salary Deposit,3500.00,,Salary
2024-01-17,Gas Station,-35.00,Shell,Transportation
```

### Analytics Endpoints

#### Spending by Category
```http
GET /api/v1/spending/analytics/spending-by-category?start_date=2024-01-01&transaction_type=expense
Authorization: Bearer <token>
```

Response:
```json
[
  {
    "category_id": 5,
    "category_name": "Food & Dining",
    "total_amount": 523.45,
    "transaction_count": 23,
    "percentage": 25.5,
    "budget_amount": 500.00,
    "budget_percentage": 104.69
  }
]
```

#### Spending Trend
```http
GET /api/v1/spending/analytics/spending-trend?start_date=2024-01-01&group_by=month
Authorization: Bearer <token>
```

Query Parameters:
- `group_by`: day, week, month (default), or year

Response:
```json
[
  {
    "period": "2024-01",
    "income": 3500.00,
    "expenses": 2051.23,
    "net": 1448.77,
    "category_breakdown": [...]
  }
]
```

## Database Migration

To apply the database changes, run the initialization script:

```bash
# Using Docker Compose
docker-compose up -d db
docker-compose run --rm api uv run python -m app.core.db_init

# Or directly with Python (ensure DATABASE_URL is set)
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/dbname"
uv run python -m app.core.db_init
```

## Testing

Create a test file to verify the implementation:

```python
# test_spending.py
import asyncio
import httpx
from datetime import date

async def test_spending_features():
    base_url = "http://localhost:8000/api/v1"
    
    # First, get auth token
    auth_response = await client.post(
        f"{base_url}/auth/login",
        data={"username": "testuser", "password": "testpass"}
    )
    token = auth_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create default categories
    categories = await client.post(
        f"{base_url}/spending/categories/defaults",
        headers=headers
    )
    print(f"Created {len(categories.json())} default categories")
    
    # Create a transaction
    transaction = await client.post(
        f"{base_url}/spending/transactions",
        headers=headers,
        json={
            "amount": 45.99,
            "transaction_date": str(date.today()),
            "description": "Test grocery shopping",
            "transaction_type": "expense",
            "category_id": categories.json()[4]["id"],  # Food & Dining
            "merchant": "Test Store",
            "tags": "test,groceries"
        }
    )
    print(f"Created transaction: {transaction.json()}")
    
    # Get spending analytics
    analytics = await client.get(
        f"{base_url}/spending/analytics/spending-by-category",
        headers=headers
    )
    print(f"Spending by category: {analytics.json()}")

if __name__ == "__main__":
    asyncio.run(test_spending_features())
```

## Best Practices

### 1. Category Organization
- Create a logical hierarchy with broad parent categories
- Use specific subcategories for detailed tracking
- Set realistic monthly budgets for expense categories

### 2. Transaction Rules
- Start with simple, high-priority rules for common transactions
- Use merchant patterns for specific vendors
- Use description patterns for transaction types
- Test rules on existing transactions before enabling

### 3. CSV Import
- Always review the first few rows of your CSV
- Map columns correctly based on your bank's format
- Enable auto-categorize for efficiency
- Check import results for any errors

### 4. Data Management
- Regularly review uncategorized transactions
- Update rules based on new transaction patterns
- Use tags for additional organization beyond categories
- Archive old transactions periodically for performance

## Security Considerations

1. **Authentication**: All endpoints require a valid JWT token
2. **Data Isolation**: Users can only access their own transactions
3. **Input Validation**: All inputs are validated using Pydantic schemas
4. **SQL Injection**: Using SQLAlchemy ORM prevents SQL injection
5. **Rate Limiting**: API endpoints are rate-limited per user

## Future Enhancements

1. **Recurring Transactions**: Automatic creation of recurring transactions
2. **Budget Alerts**: Notifications when approaching budget limits
3. **Export Functionality**: Export transactions to various formats
4. **Mobile App Integration**: Optimized endpoints for mobile apps
5. **Bank Integration**: Direct bank account connectivity
6. **Advanced Analytics**: More detailed spending insights and predictions