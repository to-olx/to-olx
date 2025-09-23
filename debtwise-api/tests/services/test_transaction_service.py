"""
Tests for transaction service layer.
"""

import re
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import (
    Category,
    Transaction,
    TransactionRule,
    TransactionType,
)
from app.models.user import User
from app.schemas.transaction import (
    CategoryCreate,
    CategoryUpdate,
    TransactionCreate,
    TransactionFilter,
    TransactionRuleCreate,
    TransactionUpdate,
)
from app.services.transaction import (
    CategoryService,
    TransactionRuleService,
    TransactionService,
)


@pytest.mark.asyncio
class TestTransactionService:
    """Test transaction service methods."""
    
    async def test_create_transaction(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_category: Category,
    ) -> None:
        """Test creating a transaction."""
        transaction_data = TransactionCreate(
            amount=Decimal("45.99"),
            transaction_date=date.today(),
            description="Test transaction",
            transaction_type=TransactionType.EXPENSE,
            category_id=test_category.id,
            merchant="Test Merchant",
            tags="test,service",
        )
        
        transaction = TransactionService.create_transaction(
            db=db_session,
            user_id=test_user.id,
            transaction_data=transaction_data,
        )
        
        assert transaction.id is not None
        assert transaction.amount == Decimal("45.99")
        assert transaction.description == "Test transaction"
        assert transaction.category_id == test_category.id
        assert transaction.user_id == test_user.id
    
    async def test_create_transaction_with_auto_categorization(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_category: Category,
        test_rule: TransactionRule,
    ) -> None:
        """Test creating a transaction with auto-categorization."""
        transaction_data = TransactionCreate(
            amount=Decimal("15.99"),
            transaction_date=date.today(),
            description="Coffee at STARBUCKS",
            transaction_type=TransactionType.EXPENSE,
            merchant="STARBUCKS",
            # No category_id - should be auto-categorized
        )
        
        transaction = TransactionService.create_transaction(
            db=db_session,
            user_id=test_user.id,
            transaction_data=transaction_data,
        )
        
        assert transaction.category_id == test_rule.category_id
    
    async def test_update_transaction(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_transaction: Transaction,
    ) -> None:
        """Test updating a transaction."""
        update_data = TransactionUpdate(
            description="Updated description",
            amount=Decimal("99.99"),
        )
        
        updated = TransactionService.update_transaction(
            db=db_session,
            user_id=test_user.id,
            transaction_id=test_transaction.id,
            transaction_data=update_data,
        )
        
        assert updated.description == "Updated description"
        assert updated.amount == Decimal("99.99")
    
    async def test_delete_transaction(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_transaction: Transaction,
    ) -> None:
        """Test deleting a transaction."""
        success = TransactionService.delete_transaction(
            db=db_session,
            user_id=test_user.id,
            transaction_id=test_transaction.id,
        )
        
        assert success is True
        
        # Verify deletion
        deleted = db_session.get(Transaction, test_transaction.id)
        assert deleted is None
    
    async def test_get_transactions_with_filters(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_transactions: list[Transaction],
    ) -> None:
        """Test getting transactions with various filters."""
        # Test date filter
        filters = TransactionFilter(
            start_date=date.today() - timedelta(days=7),
            end_date=date.today(),
        )
        
        transactions, total = TransactionService.get_transactions(
            db=db_session,
            user_id=test_user.id,
            filters=filters,
        )
        
        assert len(transactions) > 0
        assert all(
            filters.start_date <= t.transaction_date <= filters.end_date
            for t in transactions
        )
        
        # Test amount filter
        filters = TransactionFilter(
            min_amount=Decimal("20"),
            max_amount=Decimal("50"),
        )
        
        transactions, total = TransactionService.get_transactions(
            db=db_session,
            user_id=test_user.id,
            filters=filters,
        )
        
        assert all(
            Decimal("20") <= t.amount <= Decimal("50")
            for t in transactions
        )
        
        # Test search filter
        filters = TransactionFilter(search_text="coffee")
        
        transactions, total = TransactionService.get_transactions(
            db=db_session,
            user_id=test_user.id,
            filters=filters,
        )
        
        assert all(
            "coffee" in t.description.lower() or (t.merchant and "coffee" in t.merchant.lower())
            for t in transactions
        )
    
    async def test_import_csv(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_category: Category,
    ) -> None:
        """Test importing transactions from CSV."""
        csv_content = """Date,Description,Amount,Merchant
2024-01-15,Grocery Shopping,-45.99,Whole Foods
2024-01-16,Salary Deposit,3500.00,
2024-01-17,Gas Station,-35.00,Shell"""
        
        from app.schemas.transaction import CSVImportRequest
        
        import_config = CSVImportRequest(
            date_format="%Y-%m-%d",
            date_column="Date",
            amount_column="Amount",
            description_column="Description",
            merchant_column="Merchant",
        )
        
        results = TransactionService.import_csv(
            db=db_session,
            user_id=test_user.id,
            file_content=csv_content,
            import_config=import_config,
        )
        
        assert results["total_rows"] == 3
        assert results["imported_count"] == 3
        assert results["error_count"] == 0
        assert len(results["imported_transactions"]) == 3
        
        # Verify transactions were created correctly
        transactions = results["imported_transactions"]
        assert transactions[0].amount == Decimal("45.99")
        assert transactions[0].transaction_type == TransactionType.EXPENSE
        assert transactions[1].amount == Decimal("3500.00")
        assert transactions[1].transaction_type == TransactionType.INCOME


@pytest.mark.asyncio
class TestCategoryService:
    """Test category service methods."""
    
    async def test_create_category(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test creating a category."""
        category_data = CategoryCreate(
            name="Test Category",
            icon="🧪",
            color="#FF5733",
            transaction_type=TransactionType.EXPENSE,
            budget_amount=Decimal("500.00"),
        )
        
        category = CategoryService.create_category(
            db=db_session,
            user_id=test_user.id,
            category_data=category_data,
        )
        
        assert category.id is not None
        assert category.name == "Test Category"
        assert category.budget_amount == Decimal("500.00")
        assert category.user_id == test_user.id
    
    async def test_create_subcategory(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_category: Category,
    ) -> None:
        """Test creating a subcategory."""
        subcategory_data = CategoryCreate(
            name="Test Subcategory",
            parent_id=test_category.id,
            transaction_type=test_category.transaction_type,
        )
        
        subcategory = CategoryService.create_category(
            db=db_session,
            user_id=test_user.id,
            category_data=subcategory_data,
        )
        
        assert subcategory.parent_id == test_category.id
    
    async def test_create_duplicate_category(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_category: Category,
    ) -> None:
        """Test that duplicate categories are rejected."""
        category_data = CategoryCreate(
            name=test_category.name,
            transaction_type=test_category.transaction_type,
        )
        
        with pytest.raises(ValueError, match="already exists"):
            CategoryService.create_category(
                db=db_session,
                user_id=test_user.id,
                category_data=category_data,
            )
    
    async def test_update_category(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_category: Category,
    ) -> None:
        """Test updating a category."""
        update_data = CategoryUpdate(
            name="Updated Category",
            budget_amount=Decimal("750.00"),
        )
        
        updated = CategoryService.update_category(
            db=db_session,
            user_id=test_user.id,
            category_id=test_category.id,
            category_data=update_data,
        )
        
        assert updated.name == "Updated Category"
        assert updated.budget_amount == Decimal("750.00")
    
    async def test_delete_category_with_transactions(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_category: Category,
        test_transaction: Transaction,
    ) -> None:
        """Test that categories with transactions cannot be deleted."""
        with pytest.raises(ValueError, match="Cannot delete category with"):
            CategoryService.delete_category(
                db=db_session,
                user_id=test_user.id,
                category_id=test_category.id,
            )
    
    async def test_create_default_categories(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test creating default categories."""
        categories = CategoryService.create_default_categories(
            db=db_session,
            user_id=test_user.id,
        )
        
        assert len(categories) > 10
        
        # Check some expected categories
        category_names = {cat.name for cat in categories}
        assert "Food & Dining" in category_names
        assert "Transportation" in category_names
        assert "Salary" in category_names


@pytest.mark.asyncio
class TestTransactionRuleService:
    """Test transaction rule service methods."""
    
    async def test_create_rule(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_category: Category,
    ) -> None:
        """Test creating a transaction rule."""
        rule_data = TransactionRuleCreate(
            name="Coffee Rule",
            category_id=test_category.id,
            description_pattern="COFFEE|STARBUCKS",
            priority=100,
        )
        
        rule = TransactionRuleService.create_rule(
            db=db_session,
            user_id=test_user.id,
            rule_data=rule_data,
        )
        
        assert rule.id is not None
        assert rule.name == "Coffee Rule"
        assert rule.category_id == test_category.id
        assert rule.priority == 100
    
    async def test_create_rule_with_invalid_regex(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_category: Category,
    ) -> None:
        """Test that invalid regex patterns are rejected."""
        rule_data = TransactionRuleCreate(
            name="Invalid Rule",
            category_id=test_category.id,
            description_pattern="[invalid regex",  # Missing closing bracket
        )
        
        with pytest.raises(ValueError, match="Invalid description pattern"):
            TransactionRuleService.create_rule(
                db=db_session,
                user_id=test_user.id,
                rule_data=rule_data,
            )
    
    async def test_update_rule(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_rule: TransactionRule,
    ) -> None:
        """Test updating a rule."""
        update_data = TransactionRuleUpdate(
            priority=200,
            merchant_pattern="STARBUCKS|DUNKIN",
        )
        
        updated = TransactionRuleService.update_rule(
            db=db_session,
            user_id=test_user.id,
            rule_id=test_rule.id,
            rule_data=update_data,
        )
        
        assert updated.priority == 200
        assert updated.merchant_pattern == "STARBUCKS|DUNKIN"
    
    async def test_apply_rules_to_existing(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_rule: TransactionRule,
        test_uncategorized_transaction: Transaction,
    ) -> None:
        """Test applying rules to existing transactions."""
        results = TransactionRuleService.apply_rules_to_existing(
            db=db_session,
            user_id=test_user.id,
            override_existing=False,
        )
        
        assert results["processed"] >= 1
        assert results["categorized"] >= 1
        
        # Verify the transaction was categorized
        db_session.refresh(test_uncategorized_transaction)
        assert test_uncategorized_transaction.category_id == test_rule.category_id


# Test fixtures for service tests
@pytest.fixture
def test_category(db_session: AsyncSession, test_user: User) -> Category:
    """Create a test category."""
    category = Category(
        user_id=test_user.id,
        name="Test Category",
        transaction_type=TransactionType.EXPENSE,
        is_active=True,
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


@pytest.fixture
def test_transaction(
    db_session: AsyncSession,
    test_user: User,
    test_category: Category,
) -> Transaction:
    """Create a test transaction."""
    transaction = Transaction(
        user_id=test_user.id,
        category_id=test_category.id,
        amount=Decimal("45.99"),
        transaction_date=date.today(),
        description="Test transaction",
        transaction_type=TransactionType.EXPENSE,
    )
    db_session.add(transaction)
    db_session.commit()
    db_session.refresh(transaction)
    return transaction


@pytest.fixture
def test_transactions(
    db_session: AsyncSession,
    test_user: User,
    test_category: Category,
) -> list[Transaction]:
    """Create multiple test transactions."""
    transactions = [
        Transaction(
            user_id=test_user.id,
            category_id=test_category.id,
            amount=Decimal("25.99"),
            transaction_date=date.today(),
            description="Coffee shop visit",
            transaction_type=TransactionType.EXPENSE,
            merchant="Local Coffee Shop",
        ),
        Transaction(
            user_id=test_user.id,
            category_id=test_category.id,
            amount=Decimal("45.99"),
            transaction_date=date.today() - timedelta(days=1),
            description="Grocery shopping",
            transaction_type=TransactionType.EXPENSE,
            merchant="Whole Foods",
        ),
        Transaction(
            user_id=test_user.id,
            category_id=test_category.id,
            amount=Decimal("15.99"),
            transaction_date=date.today() - timedelta(days=2),
            description="Coffee at Starbucks",
            transaction_type=TransactionType.EXPENSE,
            merchant="Starbucks",
        ),
    ]
    
    for transaction in transactions:
        db_session.add(transaction)
    
    db_session.commit()
    return transactions


@pytest.fixture
def test_rule(
    db_session: AsyncSession,
    test_user: User,
    test_category: Category,
) -> TransactionRule:
    """Create a test transaction rule."""
    rule = TransactionRule(
        user_id=test_user.id,
        category_id=test_category.id,
        name="Coffee Rule",
        description_pattern="COFFEE|STARBUCKS",
        merchant_pattern="STARBUCKS",
        priority=100,
        is_active=True,
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)
    return rule


@pytest.fixture
def test_uncategorized_transaction(
    db_session: AsyncSession,
    test_user: User,
) -> Transaction:
    """Create an uncategorized transaction."""
    transaction = Transaction(
        user_id=test_user.id,
        category_id=None,  # Uncategorized
        amount=Decimal("15.99"),
        transaction_date=date.today(),
        description="STARBUCKS COFFEE",
        transaction_type=TransactionType.EXPENSE,
        merchant="STARBUCKS",
    )
    db_session.add(transaction)
    db_session.commit()
    db_session.refresh(transaction)
    return transaction