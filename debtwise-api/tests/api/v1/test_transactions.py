"""
Tests for transaction management endpoints.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import TransactionType


@pytest.mark.asyncio
class TestTransactionEndpoints:
    """Test transaction CRUD endpoints."""
    
    async def test_create_transaction(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_category: Dict[str, Any],
    ) -> None:
        """Test creating a transaction."""
        transaction_data = {
            "amount": 45.99,
            "transaction_date": str(date.today()),
            "description": "Test grocery shopping",
            "transaction_type": TransactionType.EXPENSE.value,
            "category_id": test_category["id"],
            "merchant": "Test Store",
            "tags": "test,groceries",
            "is_recurring": False,
        }
        
        response = await async_client.post(
            "/api/v1/spending/transactions",
            headers=auth_headers,
            json=transaction_data,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["amount"] == "45.99"
        assert data["description"] == "Test grocery shopping"
        assert data["category_id"] == test_category["id"]
        assert data["merchant"] == "Test Store"
        assert data["tags"] == "groceries,test"  # Should be sorted
        assert "id" in data
        assert "created_at" in data
    
    async def test_get_transactions(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_transactions: list[Dict[str, Any]],
    ) -> None:
        """Test getting transactions with filters."""
        response = await async_client.get(
            "/api/v1/spending/transactions",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "transactions" in data
        assert "total" in data
        assert data["total"] >= len(test_transactions)
        assert len(data["transactions"]) >= len(test_transactions)
    
    async def test_get_transactions_with_filters(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_transactions: list[Dict[str, Any]],
        test_category: Dict[str, Any],
    ) -> None:
        """Test getting transactions with various filters."""
        # Filter by date range
        start_date = (date.today() - timedelta(days=30)).isoformat()
        end_date = date.today().isoformat()
        
        response = await async_client.get(
            f"/api/v1/spending/transactions?start_date={start_date}&end_date={end_date}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert all(
            start_date <= t["transaction_date"] <= end_date
            for t in data["transactions"]
        )
        
        # Filter by category
        response = await async_client.get(
            f"/api/v1/spending/transactions?category_ids={test_category['id']}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert all(
            t["category_id"] == test_category["id"]
            for t in data["transactions"]
        )
        
        # Filter by transaction type
        response = await async_client.get(
            f"/api/v1/spending/transactions?transaction_type={TransactionType.EXPENSE.value}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert all(
            t["transaction_type"] == TransactionType.EXPENSE.value
            for t in data["transactions"]
        )
    
    async def test_update_transaction(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_transactions: list[Dict[str, Any]],
    ) -> None:
        """Test updating a transaction."""
        transaction_id = test_transactions[0]["id"]
        update_data = {
            "description": "Updated description",
            "amount": 99.99,
            "tags": "updated,test",
        }
        
        response = await async_client.patch(
            f"/api/v1/spending/transactions/{transaction_id}",
            headers=auth_headers,
            json=update_data,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description"
        assert data["amount"] == "99.99"
        assert data["tags"] == "test,updated"  # Should be sorted
    
    async def test_delete_transaction(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_transactions: list[Dict[str, Any]],
    ) -> None:
        """Test deleting a transaction."""
        transaction_id = test_transactions[0]["id"]
        
        response = await async_client.delete(
            f"/api/v1/spending/transactions/{transaction_id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        
        # Verify transaction is deleted
        response = await async_client.get(
            f"/api/v1/spending/transactions/{transaction_id}",
            headers=auth_headers,
        )
        assert response.status_code == 404


@pytest.mark.asyncio
class TestCategoryEndpoints:
    """Test category management endpoints."""
    
    async def test_create_category(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
    ) -> None:
        """Test creating a category."""
        category_data = {
            "name": "Test Category",
            "icon": "🧪",
            "color": "#FF5733",
            "transaction_type": TransactionType.EXPENSE.value,
            "budget_amount": 500.00,
        }
        
        response = await async_client.post(
            "/api/v1/spending/categories",
            headers=auth_headers,
            json=category_data,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Category"
        assert data["icon"] == "🧪"
        assert data["color"] == "#FF5733"
        assert data["budget_amount"] == "500.00"
        assert "id" in data
    
    async def test_create_subcategory(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_category: Dict[str, Any],
    ) -> None:
        """Test creating a subcategory."""
        subcategory_data = {
            "name": "Test Subcategory",
            "parent_id": test_category["id"],
            "transaction_type": test_category["transaction_type"],
        }
        
        response = await async_client.post(
            "/api/v1/spending/categories",
            headers=auth_headers,
            json=subcategory_data,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Subcategory"
        assert data["parent_id"] == test_category["id"]
    
    async def test_get_categories(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_category: Dict[str, Any],
    ) -> None:
        """Test getting all categories."""
        response = await async_client.get(
            "/api/v1/spending/categories",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert any(cat["id"] == test_category["id"] for cat in data)
    
    async def test_update_category(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_category: Dict[str, Any],
    ) -> None:
        """Test updating a category."""
        category_id = test_category["id"]
        update_data = {
            "name": "Updated Category",
            "budget_amount": 750.00,
        }
        
        response = await async_client.patch(
            f"/api/v1/spending/categories/{category_id}",
            headers=auth_headers,
            json=update_data,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Category"
        assert data["budget_amount"] == "750.00"
    
    async def test_delete_category_with_transactions(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_category: Dict[str, Any],
        test_transactions: list[Dict[str, Any]],
    ) -> None:
        """Test that categories with transactions cannot be deleted."""
        response = await async_client.delete(
            f"/api/v1/spending/categories/{test_category['id']}",
            headers=auth_headers,
        )
        
        assert response.status_code == 400
        assert "Cannot delete category" in response.json()["detail"]
    
    async def test_create_default_categories(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
    ) -> None:
        """Test creating default categories."""
        response = await async_client.post(
            "/api/v1/spending/categories/defaults",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 10  # Should create multiple default categories
        
        # Verify categories include expected defaults
        category_names = {cat["name"] for cat in data}
        assert "Food & Dining" in category_names
        assert "Transportation" in category_names
        assert "Salary" in category_names


@pytest.mark.asyncio
class TestTransactionRuleEndpoints:
    """Test transaction rule endpoints."""
    
    async def test_create_rule(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_category: Dict[str, Any],
    ) -> None:
        """Test creating a transaction rule."""
        rule_data = {
            "name": "Coffee Rule",
            "category_id": test_category["id"],
            "description_pattern": "COFFEE|STARBUCKS|DUNKIN",
            "merchant_pattern": "STARBUCKS",
            "amount_min": 2.00,
            "amount_max": 20.00,
            "priority": 100,
        }
        
        response = await async_client.post(
            "/api/v1/spending/rules",
            headers=auth_headers,
            json=rule_data,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Coffee Rule"
        assert data["category_id"] == test_category["id"]
        assert data["priority"] == 100
        assert "id" in data
    
    async def test_get_rules(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_rule: Dict[str, Any],
    ) -> None:
        """Test getting all rules."""
        response = await async_client.get(
            "/api/v1/spending/rules",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert any(rule["id"] == test_rule["id"] for rule in data)
    
    async def test_apply_rules(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_rule: Dict[str, Any],
        test_uncategorized_transaction: Dict[str, Any],
    ) -> None:
        """Test applying rules to existing transactions."""
        response = await async_client.post(
            "/api/v1/spending/rules/apply",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "processed" in data
        assert "categorized" in data
        assert "skipped" in data
        assert data["processed"] >= 1
        assert data["categorized"] >= 1


@pytest.mark.asyncio
class TestCSVImportEndpoint:
    """Test CSV import functionality."""
    
    async def test_import_csv(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_category: Dict[str, Any],
    ) -> None:
        """Test importing transactions from CSV."""
        csv_content = """Date,Description,Amount,Merchant
2024-01-15,Grocery Shopping,-45.99,Whole Foods
2024-01-16,Salary Deposit,3500.00,
2024-01-17,Gas Station,-35.00,Shell"""
        
        files = {"file": ("test.csv", csv_content, "text/csv")}
        data = {
            "date_format": "%Y-%m-%d",
            "date_column": "Date",
            "amount_column": "Amount",
            "description_column": "Description",
            "merchant_column": "Merchant",
            "skip_duplicates": "true",
            "auto_categorize": "true",
        }
        
        response = await async_client.post(
            "/api/v1/spending/transactions/import",
            headers=auth_headers,
            files=files,
            data=data,
        )
        
        assert response.status_code == 200
        result = response.json()
        assert result["total_rows"] == 3
        assert result["imported_count"] == 3
        assert result["error_count"] == 0
        assert len(result["imported_transactions"]) == 3
    
    async def test_import_csv_with_duplicates(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_category: Dict[str, Any],
    ) -> None:
        """Test that duplicate transactions are skipped."""
        csv_content = """Date,Description,Amount,Merchant
2024-01-15,Grocery Shopping,-45.99,Whole Foods"""
        
        files = {"file": ("test.csv", csv_content, "text/csv")}
        data = {
            "date_format": "%Y-%m-%d",
            "date_column": "Date",
            "amount_column": "Amount",
            "description_column": "Description",
            "merchant_column": "Merchant",
            "skip_duplicates": "true",
        }
        
        # Import once
        response = await async_client.post(
            "/api/v1/spending/transactions/import",
            headers=auth_headers,
            files=files,
            data=data,
        )
        assert response.status_code == 200
        assert response.json()["imported_count"] == 1
        
        # Import again - should skip duplicate
        files = {"file": ("test.csv", csv_content, "text/csv")}
        response = await async_client.post(
            "/api/v1/spending/transactions/import",
            headers=auth_headers,
            files=files,
            data=data,
        )
        assert response.status_code == 200
        result = response.json()
        assert result["imported_count"] == 0
        assert result["skipped_count"] == 1


@pytest.mark.asyncio
class TestAnalyticsEndpoints:
    """Test analytics endpoints."""
    
    async def test_spending_by_category(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_transactions: list[Dict[str, Any]],
    ) -> None:
        """Test getting spending by category."""
        response = await async_client.get(
            "/api/v1/spending/analytics/spending-by-category",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        if data:  # If there are results
            assert all(
                {"category_id", "category_name", "total_amount", "transaction_count", "percentage"}.issubset(item.keys())
                for item in data
            )
            # Verify percentages sum to ~100
            total_percentage = sum(item["percentage"] for item in data)
            assert 99 <= total_percentage <= 101
    
    async def test_spending_trend(
        self,
        async_client: AsyncClient,
        auth_headers: Dict[str, str],
        test_transactions: list[Dict[str, Any]],
    ) -> None:
        """Test getting spending trend."""
        response = await async_client.get(
            "/api/v1/spending/analytics/spending-trend?group_by=month",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        if data:  # If there are results
            assert all(
                {"period", "income", "expenses", "net", "category_breakdown"}.issubset(item.keys())
                for item in data
            )
            # Verify net calculation
            for item in data:
                assert Decimal(str(item["net"])) == Decimal(str(item["income"])) - Decimal(str(item["expenses"]))