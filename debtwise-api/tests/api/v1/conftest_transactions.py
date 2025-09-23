"""
Test fixtures for transaction-related tests.

Add these fixtures to your main conftest.py file or import them.
"""

from datetime import date
from typing import Any, Dict, List

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import TransactionType


@pytest.fixture
async def test_category(
    async_client: AsyncClient,
    auth_headers: Dict[str, str],
) -> Dict[str, Any]:
    """Create a test category."""
    category_data = {
        "name": "Test Food Category",
        "icon": "🍔",
        "color": "#FF5733",
        "transaction_type": TransactionType.EXPENSE.value,
        "budget_amount": 500.00,
        "is_active": True,
    }
    
    response = await async_client.post(
        "/api/v1/spending/categories",
        headers=auth_headers,
        json=category_data,
    )
    
    assert response.status_code == 200
    return response.json()


@pytest.fixture
async def test_income_category(
    async_client: AsyncClient,
    auth_headers: Dict[str, str],
) -> Dict[str, Any]:
    """Create a test income category."""
    category_data = {
        "name": "Test Income Category",
        "icon": "💰",
        "transaction_type": TransactionType.INCOME.value,
        "is_active": True,
    }
    
    response = await async_client.post(
        "/api/v1/spending/categories",
        headers=auth_headers,
        json=category_data,
    )
    
    assert response.status_code == 200
    return response.json()


@pytest.fixture
async def test_transactions(
    async_client: AsyncClient,
    auth_headers: Dict[str, str],
    test_category: Dict[str, Any],
    test_income_category: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Create test transactions."""
    transactions = []
    
    # Create expense transactions
    expense_data = [
        {
            "amount": 45.99,
            "transaction_date": str(date.today()),
            "description": "Grocery shopping at Whole Foods",
            "transaction_type": TransactionType.EXPENSE.value,
            "category_id": test_category["id"],
            "merchant": "Whole Foods",
            "tags": "groceries,food",
        },
        {
            "amount": 25.50,
            "transaction_date": str(date.today()),
            "description": "Lunch at restaurant",
            "transaction_type": TransactionType.EXPENSE.value,
            "category_id": test_category["id"],
            "merchant": "Local Restaurant",
            "tags": "dining,lunch",
        },
    ]
    
    for data in expense_data:
        response = await async_client.post(
            "/api/v1/spending/transactions",
            headers=auth_headers,
            json=data,
        )
        assert response.status_code == 200
        transactions.append(response.json())
    
    # Create income transaction
    income_data = {
        "amount": 3500.00,
        "transaction_date": str(date.today()),
        "description": "Monthly salary",
        "transaction_type": TransactionType.INCOME.value,
        "category_id": test_income_category["id"],
        "tags": "salary,income",
    }
    
    response = await async_client.post(
        "/api/v1/spending/transactions",
        headers=auth_headers,
        json=income_data,
    )
    assert response.status_code == 200
    transactions.append(response.json())
    
    return transactions


@pytest.fixture
async def test_rule(
    async_client: AsyncClient,
    auth_headers: Dict[str, str],
    test_category: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a test transaction rule."""
    rule_data = {
        "name": "Grocery Store Rule",
        "category_id": test_category["id"],
        "description_pattern": "WHOLE FOODS|TRADER JOE|GROCERY",
        "merchant_pattern": "WHOLE FOODS",
        "priority": 100,
        "is_active": True,
    }
    
    response = await async_client.post(
        "/api/v1/spending/rules",
        headers=auth_headers,
        json=rule_data,
    )
    
    assert response.status_code == 200
    return response.json()


@pytest.fixture
async def test_uncategorized_transaction(
    async_client: AsyncClient,
    auth_headers: Dict[str, str],
) -> Dict[str, Any]:
    """Create an uncategorized transaction for rule testing."""
    transaction_data = {
        "amount": 67.89,
        "transaction_date": str(date.today()),
        "description": "Shopping at WHOLE FOODS MARKET",
        "transaction_type": TransactionType.EXPENSE.value,
        "merchant": "WHOLE FOODS",
        "tags": "shopping",
        # No category_id - uncategorized
    }
    
    response = await async_client.post(
        "/api/v1/spending/transactions",
        headers=auth_headers,
        json=transaction_data,
    )
    
    assert response.status_code == 200
    return response.json()


@pytest.fixture
async def default_categories(
    async_client: AsyncClient,
    auth_headers: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Create default categories for testing."""
    response = await async_client.post(
        "/api/v1/spending/categories/defaults",
        headers=auth_headers,
    )
    
    # If categories already exist, get them instead
    if response.status_code != 200:
        response = await async_client.get(
            "/api/v1/spending/categories",
            headers=auth_headers,
        )
    
    assert response.status_code == 200
    return response.json()