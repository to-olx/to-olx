"""
Tests for budget API endpoints.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.budget import Budget, BudgetPeriod, BudgetPeriodType
from app.models.transaction import Category, TransactionType
from app.models.user import User


@pytest.mark.asyncio
async def test_create_budget(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db: AsyncSession,
):
    """Test creating a new budget."""
    # Create a category first
    category_data = {
        "name": "Test Category",
        "transaction_type": "expense",
        "is_active": True
    }
    response = await client.post(
        "/api/v1/spending/categories",
        json=category_data,
        headers=auth_headers,
    )
    assert response.status_code == 200
    category = response.json()
    
    # Create budget
    budget_data = {
        "name": "Test Monthly Budget",
        "description": "Test budget description",
        "category_id": category["id"],
        "period_type": "monthly",
        "start_date": date.today().isoformat(),
        "amount": "1000.00",
        "allow_rollover": True,
        "max_rollover_periods": 3,
        "is_active": True
    }
    
    response = await client.post(
        "/api/v1/budgets/budgets",
        json=budget_data,
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["name"] == budget_data["name"]
    assert data["description"] == budget_data["description"]
    assert data["category_id"] == category["id"]
    assert data["period_type"] == budget_data["period_type"]
    assert Decimal(data["amount"]) == Decimal(budget_data["amount"])
    assert data["allow_rollover"] == budget_data["allow_rollover"]
    assert data["user_id"] == test_user.id


@pytest.mark.asyncio
async def test_get_budgets(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
):
    """Test getting all budgets for a user."""
    response = await client.get(
        "/api/v1/budgets/budgets",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_budget_by_id(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
    db: AsyncSession,
):
    """Test getting a specific budget."""
    # Create a budget first
    budget_data = {
        "name": "Test Budget",
        "period_type": "monthly",
        "start_date": date.today().isoformat(),
        "amount": "500.00",
        "is_active": True
    }
    
    create_response = await client.post(
        "/api/v1/budgets/budgets",
        json=budget_data,
        headers=auth_headers,
    )
    assert create_response.status_code == 200
    created_budget = create_response.json()
    
    # Get the budget
    response = await client.get(
        f"/api/v1/budgets/budgets/{created_budget['id']}",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created_budget["id"]
    assert data["name"] == budget_data["name"]


@pytest.mark.asyncio
async def test_update_budget(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
):
    """Test updating a budget."""
    # Create a budget first
    budget_data = {
        "name": "Original Budget",
        "period_type": "monthly",
        "start_date": date.today().isoformat(),
        "amount": "500.00",
        "is_active": True
    }
    
    create_response = await client.post(
        "/api/v1/budgets/budgets",
        json=budget_data,
        headers=auth_headers,
    )
    assert create_response.status_code == 200
    created_budget = create_response.json()
    
    # Update the budget
    update_data = {
        "name": "Updated Budget",
        "amount": "750.00"
    }
    
    response = await client.put(
        f"/api/v1/budgets/budgets/{created_budget['id']}",
        json=update_data,
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == update_data["name"]
    assert Decimal(data["amount"]) == Decimal(update_data["amount"])


@pytest.mark.asyncio
async def test_delete_budget(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
):
    """Test deleting a budget."""
    # Create a budget first
    budget_data = {
        "name": "Budget to Delete",
        "period_type": "monthly",
        "start_date": date.today().isoformat(),
        "amount": "500.00",
        "is_active": True
    }
    
    create_response = await client.post(
        "/api/v1/budgets/budgets",
        json=budget_data,
        headers=auth_headers,
    )
    assert create_response.status_code == 200
    created_budget = create_response.json()
    
    # Delete the budget
    response = await client.delete(
        f"/api/v1/budgets/budgets/{created_budget['id']}",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    
    # Verify it's deleted
    get_response = await client.get(
        f"/api/v1/budgets/budgets/{created_budget['id']}",
        headers=auth_headers,
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_budget_summary(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
):
    """Test getting budget summary."""
    # Create a category and budget
    category_data = {
        "name": "Test Summary Category",
        "transaction_type": "expense",
        "is_active": True
    }
    cat_response = await client.post(
        "/api/v1/spending/categories",
        json=category_data,
        headers=auth_headers,
    )
    assert cat_response.status_code == 200
    category = cat_response.json()
    
    budget_data = {
        "name": "Summary Test Budget",
        "category_id": category["id"],
        "period_type": "monthly",
        "start_date": date.today().isoformat(),
        "amount": "1000.00",
        "is_active": True
    }
    
    budget_response = await client.post(
        "/api/v1/budgets/budgets",
        json=budget_data,
        headers=auth_headers,
    )
    assert budget_response.status_code == 200
    budget = budget_response.json()
    
    # Add a transaction
    transaction_data = {
        "amount": "250.00",
        "transaction_date": date.today().isoformat(),
        "description": "Test purchase",
        "transaction_type": "expense",
        "category_id": category["id"]
    }
    
    trans_response = await client.post(
        "/api/v1/spending/transactions",
        json=transaction_data,
        headers=auth_headers,
    )
    assert trans_response.status_code == 200
    
    # Get budget summary
    response = await client.get(
        f"/api/v1/budgets/budgets/{budget['id']}/summary",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["budget_id"] == budget["id"]
    assert data["budget_name"] == budget["name"]
    assert Decimal(data["total_budgeted"]) == Decimal("1000.00")
    assert Decimal(data["total_spent"]) == Decimal("250.00")
    assert Decimal(data["total_remaining"]) == Decimal("750.00")
    assert data["percentage_used"] == 25.0


@pytest.mark.asyncio
async def test_budget_overview(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
):
    """Test getting overall budget overview."""
    response = await client.get(
        "/api/v1/budgets/budgets/summary/overview",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "total_budgets" in data
    assert "active_budgets" in data
    assert "total_budgeted_amount" in data
    assert "total_spent_amount" in data
    assert "overall_percentage_used" in data
    assert "budgets" in data
    assert isinstance(data["budgets"], list)


@pytest.mark.asyncio
async def test_create_budget_alert(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
):
    """Test creating a budget alert."""
    # Create a budget first
    budget_data = {
        "name": "Alert Test Budget",
        "period_type": "monthly",
        "start_date": date.today().isoformat(),
        "amount": "1000.00",
        "is_active": True
    }
    
    budget_response = await client.post(
        "/api/v1/budgets/budgets",
        json=budget_data,
        headers=auth_headers,
    )
    assert budget_response.status_code == 200
    budget = budget_response.json()
    
    # Create alert
    alert_data = {
        "threshold_percentage": 80,
        "alert_message": "Budget is at 80%!",
        "is_enabled": True,
        "send_email": True
    }
    
    response = await client.post(
        f"/api/v1/budgets/budgets/{budget['id']}/alerts",
        json=alert_data,
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["threshold_percentage"] == alert_data["threshold_percentage"]
    assert data["alert_message"] == alert_data["alert_message"]
    assert data["is_enabled"] == alert_data["is_enabled"]
    assert data["budget_id"] == budget["id"]


@pytest.mark.asyncio
async def test_budget_rollover(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
):
    """Test budget rollover functionality."""
    # Create a budget with rollover enabled
    budget_data = {
        "name": "Rollover Test Budget",
        "period_type": "monthly",
        "start_date": (date.today() - timedelta(days=35)).isoformat(),  # Start in previous month
        "amount": "1000.00",
        "allow_rollover": True,
        "is_active": True
    }
    
    budget_response = await client.post(
        "/api/v1/budgets/budgets",
        json=budget_data,
        headers=auth_headers,
    )
    assert budget_response.status_code == 200
    budget = budget_response.json()
    
    # Process rollover
    rollover_data = {
        "budget_id": budget["id"]
    }
    
    response = await client.post(
        "/api/v1/budgets/budgets/rollover",
        json=rollover_data,
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["budget_id"] == budget["id"]
    assert data["success"] is True
    assert "periods_processed" in data
    assert "new_period" in data