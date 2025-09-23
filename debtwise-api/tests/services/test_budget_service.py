"""
Tests for budget service.
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.budget import Budget, BudgetPeriod
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.schemas.budget import BudgetCreate, BudgetUpdate
from app.services.budget import BudgetService, BudgetExceededException


@pytest.fixture
def budget_service():
    """Create budget service instance."""
    return BudgetService()


@pytest.fixture
def sample_user():
    """Create sample user."""
    return User(
        id=1,
        email="test@example.com",
        hashed_password="hashed",
        full_name="Test User",
    )


@pytest.fixture
def sample_budget():
    """Create sample budget."""
    return Budget(
        id=1,
        user_id=1,
        name="Food Budget",
        category="Food",
        amount=Decimal("500.00"),
        period=BudgetPeriod.MONTHLY,
        start_date=date.today().replace(day=1),
        end_date=None,
        is_active=True,
    )


@pytest.fixture
def sample_transactions():
    """Create sample transactions for budget testing."""
    return [
        Transaction(
            id=1,
            user_id=1,
            amount=Decimal("-100.00"),
            category="Food",
            description="Groceries",
            transaction_date=date.today(),
            type=TransactionType.EXPENSE,
        ),
        Transaction(
            id=2,
            user_id=1,
            amount=Decimal("-50.00"),
            category="Food",
            description="Restaurant",
            transaction_date=date.today() - timedelta(days=5),
            type=TransactionType.EXPENSE,
        ),
        Transaction(
            id=3,
            user_id=1,
            amount=Decimal("-75.00"),
            category="Transport",
            description="Gas",
            transaction_date=date.today() - timedelta(days=3),
            type=TransactionType.EXPENSE,
        ),
    ]


class TestBudgetService:
    """Test budget service functionality."""
    
    @pytest.mark.asyncio
    async def test_create_budget(
        self,
        budget_service: BudgetService,
        mock_db_session: AsyncSession,
    ):
        """Test budget creation."""
        # Prepare budget data
        budget_data = BudgetCreate(
            name="Monthly Food Budget",
            category="Food",
            amount=Decimal("500.00"),
            period=BudgetPeriod.MONTHLY,
            start_date=date.today(),
            alert_threshold=80,
        )
        
        # Mock database operations
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()
        
        # Create budget
        budget = await budget_service.create_budget(
            db=mock_db_session,
            user_id=1,
            budget_data=budget_data,
        )
        
        # Verify budget creation
        assert budget.name == "Monthly Food Budget"
        assert budget.category == "Food"
        assert budget.amount == Decimal("500.00")
        assert budget.period == BudgetPeriod.MONTHLY
        assert budget.alert_threshold == 80
        assert budget.is_active is True
        
        # Verify database operations
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_budget_duplicate_category(
        self,
        budget_service: BudgetService,
        mock_db_session: AsyncSession,
    ):
        """Test creating budget with duplicate category."""
        # Setup existing budget
        existing_budget = Budget(
            id=1,
            user_id=1,
            category="Food",
            amount=Decimal("300.00"),
            period=BudgetPeriod.MONTHLY,
        )
        
        # Mock query to return existing budget
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_budget
        mock_db_session.execute.return_value = mock_result
        
        # Try to create duplicate
        budget_data = BudgetCreate(
            name="Another Food Budget",
            category="Food",
            amount=Decimal("500.00"),
            period=BudgetPeriod.MONTHLY,
            start_date=date.today(),
        )
        
        with pytest.raises(ValueError, match="already exists"):
            await budget_service.create_budget(
                db=mock_db_session,
                user_id=1,
                budget_data=budget_data,
            )
    
    @pytest.mark.asyncio
    async def test_get_budget_with_status(
        self,
        budget_service: BudgetService,
        sample_budget: Budget,
        sample_transactions: list,
        mock_db_session: AsyncSession,
    ):
        """Test getting budget with spending status."""
        # Mock budget query
        mock_budget_result = MagicMock()
        mock_budget_result.scalar_one_or_none.return_value = sample_budget
        
        # Mock transactions query
        mock_trans_result = MagicMock()
        # Filter only Food transactions
        food_transactions = [t for t in sample_transactions if t.category == "Food"]
        mock_trans_result.scalars.return_value.all.return_value = food_transactions
        
        # Setup execute to return different results
        mock_db_session.execute.side_effect = [mock_budget_result, mock_trans_result]
        
        # Get budget with status
        result = await budget_service.get_budget_with_status(
            db=mock_db_session,
            budget_id=1,
            user_id=1,
        )
        
        # Verify result
        assert result["budget"].id == 1
        assert result["spent"] == Decimal("150.00")  # 100 + 50
        assert result["remaining"] == Decimal("350.00")  # 500 - 150
        assert result["percentage_used"] == 30.0  # 150/500 * 100
        assert result["status"] == "on_track"
        assert result["days_remaining"] > 0
    
    @pytest.mark.asyncio
    async def test_get_budget_status_over_budget(
        self,
        budget_service: BudgetService,
        sample_budget: Budget,
        mock_db_session: AsyncSession,
    ):
        """Test budget status when over budget."""
        # Create transactions that exceed budget
        over_budget_transactions = [
            Transaction(
                id=1,
                user_id=1,
                amount=Decimal("-600.00"),
                category="Food",
                description="Big expense",
                transaction_date=date.today(),
                type=TransactionType.EXPENSE,
            ),
        ]
        
        # Mock queries
        mock_budget_result = MagicMock()
        mock_budget_result.scalar_one_or_none.return_value = sample_budget
        
        mock_trans_result = MagicMock()
        mock_trans_result.scalars.return_value.all.return_value = over_budget_transactions
        
        mock_db_session.execute.side_effect = [mock_budget_result, mock_trans_result]
        
        # Get budget status
        result = await budget_service.get_budget_with_status(
            db=mock_db_session,
            budget_id=1,
            user_id=1,
        )
        
        # Verify over budget status
        assert result["spent"] == Decimal("600.00")
        assert result["remaining"] == Decimal("-100.00")
        assert result["percentage_used"] == 120.0
        assert result["status"] == "over_budget"
    
    @pytest.mark.asyncio
    async def test_update_budget(
        self,
        budget_service: BudgetService,
        sample_budget: Budget,
        mock_db_session: AsyncSession,
    ):
        """Test budget update."""
        # Mock query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_budget
        mock_db_session.execute.return_value = mock_result
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()
        
        # Update data
        update_data = BudgetUpdate(
            amount=Decimal("600.00"),
            alert_threshold=90,
        )
        
        # Update budget
        updated_budget = await budget_service.update_budget(
            db=mock_db_session,
            budget_id=1,
            user_id=1,
            budget_update=update_data,
        )
        
        # Verify update
        assert updated_budget.amount == Decimal("600.00")
        assert updated_budget.alert_threshold == 90
        mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_budget(
        self,
        budget_service: BudgetService,
        sample_budget: Budget,
        mock_db_session: AsyncSession,
    ):
        """Test budget deletion."""
        # Mock query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_budget
        mock_db_session.execute.return_value = mock_result
        mock_db_session.delete = AsyncMock()
        mock_db_session.commit = AsyncMock()
        
        # Delete budget
        result = await budget_service.delete_budget(
            db=mock_db_session,
            budget_id=1,
            user_id=1,
        )
        
        # Verify deletion
        assert result is True
        mock_db_session.delete.assert_called_once_with(sample_budget)
        mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_budget_alerts(
        self,
        budget_service: BudgetService,
        sample_budget: Budget,
        mock_db_session: AsyncSession,
    ):
        """Test budget alert checking."""
        # Set alert threshold
        sample_budget.alert_threshold = 80
        
        # Create transactions at 85% of budget
        transactions = [
            Transaction(
                id=1,
                user_id=1,
                amount=Decimal("-425.00"),  # 85% of 500
                category="Food",
                description="Various expenses",
                transaction_date=date.today(),
                type=TransactionType.EXPENSE,
            ),
        ]
        
        # Mock queries
        mock_budgets_result = MagicMock()
        mock_budgets_result.scalars.return_value.all.return_value = [sample_budget]
        
        mock_trans_result = MagicMock()
        mock_trans_result.scalars.return_value.all.return_value = transactions
        
        mock_db_session.execute.side_effect = [mock_budgets_result, mock_trans_result]
        
        # Check alerts
        alerts = await budget_service.check_budget_alerts(
            db=mock_db_session,
            user_id=1,
        )
        
        # Verify alert
        assert len(alerts) == 1
        assert alerts[0]["budget_id"] == 1
        assert alerts[0]["percentage_used"] == 85.0
        assert alerts[0]["alert_type"] == "threshold_exceeded"
    
    @pytest.mark.asyncio
    async def test_get_budget_recommendations(
        self,
        budget_service: BudgetService,
        sample_transactions: list,
        mock_db_session: AsyncSession,
    ):
        """Test budget recommendations based on spending."""
        # Mock transactions query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_transactions
        mock_db_session.execute.return_value = mock_result
        
        # Get recommendations
        recommendations = await budget_service.get_budget_recommendations(
            db=mock_db_session,
            user_id=1,
        )
        
        # Verify recommendations
        assert len(recommendations) > 0
        assert any(r["category"] == "Food" for r in recommendations)
        assert any(r["category"] == "Transport" for r in recommendations)
        
        # Check recommendation amounts are reasonable
        for rec in recommendations:
            assert rec["recommended_amount"] > 0
            assert rec["based_on"] == "historical_spending"
    
    @pytest.mark.asyncio
    async def test_budget_period_calculations(
        self,
        budget_service: BudgetService,
    ):
        """Test budget period date calculations."""
        # Test monthly budget
        monthly_start, monthly_end = budget_service._get_budget_period_dates(
            BudgetPeriod.MONTHLY,
            date(2024, 1, 15),
        )
        assert monthly_start == date(2024, 1, 1)
        assert monthly_end == date(2024, 1, 31)
        
        # Test weekly budget
        weekly_start, weekly_end = budget_service._get_budget_period_dates(
            BudgetPeriod.WEEKLY,
            date(2024, 1, 10),  # Wednesday
        )
        assert weekly_start.weekday() == 0  # Monday
        assert (weekly_end - weekly_start).days == 6
        
        # Test yearly budget
        yearly_start, yearly_end = budget_service._get_budget_period_dates(
            BudgetPeriod.YEARLY,
            date(2024, 6, 15),
        )
        assert yearly_start == date(2024, 1, 1)
        assert yearly_end == date(2024, 12, 31)
    
    @pytest.mark.asyncio
    async def test_rollover_budgets(
        self,
        budget_service: BudgetService,
        mock_db_session: AsyncSession,
    ):
        """Test budget rollover functionality."""
        # Create budget that needs rollover
        old_budget = Budget(
            id=1,
            user_id=1,
            name="January Food Budget",
            category="Food",
            amount=Decimal("500.00"),
            period=BudgetPeriod.MONTHLY,
            start_date=date.today().replace(day=1) - timedelta(days=32),
            is_active=True,
            rollover_enabled=True,
        )
        
        # Mock queries
        mock_budgets_result = MagicMock()
        mock_budgets_result.scalars.return_value.all.return_value = [old_budget]
        mock_db_session.execute.return_value = mock_budgets_result
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        
        # Run rollover
        rolled_over = await budget_service.rollover_budgets(
            db=mock_db_session,
            user_id=1,
        )
        
        # Verify rollover
        assert len(rolled_over) == 1
        assert mock_db_session.add.call_count == 1
        
        # Check new budget was created
        new_budget = mock_db_session.add.call_args[0][0]
        assert new_budget.category == "Food"
        assert new_budget.amount == Decimal("500.00")
        assert new_budget.start_date > old_budget.start_date


@pytest.fixture
def mock_db_session():
    """Create mock database session."""
    session = AsyncMock(spec=AsyncSession)
    return session