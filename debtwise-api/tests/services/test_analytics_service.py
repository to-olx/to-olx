"""
Tests for analytics service.
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.schemas.analytics import Period
from app.services.analytics import AnalyticsService


@pytest.fixture
def analytics_service():
    """Create analytics service instance."""
    return AnalyticsService()


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
def sample_transactions():
    """Create sample transactions for testing."""
    base_date = datetime.now().date()
    
    return [
        Transaction(
            id=1,
            user_id=1,
            amount=Decimal("-50.00"),
            category="Food",
            description="Groceries",
            transaction_date=base_date,
            type=TransactionType.EXPENSE,
        ),
        Transaction(
            id=2,
            user_id=1,
            amount=Decimal("-30.00"),
            category="Transport",
            description="Gas",
            transaction_date=base_date - timedelta(days=1),
            type=TransactionType.EXPENSE,
        ),
        Transaction(
            id=3,
            user_id=1,
            amount=Decimal("1000.00"),
            category="Income",
            description="Salary",
            transaction_date=base_date - timedelta(days=5),
            type=TransactionType.INCOME,
        ),
        Transaction(
            id=4,
            user_id=1,
            amount=Decimal("-200.00"),
            category="Shopping",
            description="Clothes",
            transaction_date=base_date - timedelta(days=7),
            type=TransactionType.EXPENSE,
        ),
        Transaction(
            id=5,
            user_id=1,
            amount=Decimal("-100.00"),
            category="Food",
            description="Restaurant",
            transaction_date=base_date - timedelta(days=10),
            type=TransactionType.EXPENSE,
        ),
    ]


class TestAnalyticsService:
    """Test analytics service functionality."""
    
    @pytest.mark.asyncio
    async def test_get_spending_summary_daily(
        self,
        analytics_service: AnalyticsService,
        sample_transactions: list,
        mock_db_session: AsyncSession,
    ):
        """Test daily spending summary."""
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_transactions
        mock_db_session.execute.return_value = mock_result
        
        # Get spending summary
        result = await analytics_service.get_spending_summary(
            db=mock_db_session,
            user_id=1,
            period=Period.DAILY,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today(),
        )
        
        # Verify result structure
        assert "summary" in result
        assert "details" in result
        assert "period" in result
        assert result["period"] == "daily"
        
        # Verify summary calculations
        summary = result["summary"]
        assert summary["total_income"] == 1000.00
        assert summary["total_expenses"] == 380.00
        assert summary["net_savings"] == 620.00
        assert summary["average_daily_expense"] > 0
        
        # Verify details
        assert len(result["details"]) > 0
        assert all("date" in detail for detail in result["details"])
        assert all("income" in detail for detail in result["details"])
        assert all("expenses" in detail for detail in result["details"])
    
    @pytest.mark.asyncio
    async def test_get_spending_summary_monthly(
        self,
        analytics_service: AnalyticsService,
        sample_transactions: list,
        mock_db_session: AsyncSession,
    ):
        """Test monthly spending summary."""
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_transactions
        mock_db_session.execute.return_value = mock_result
        
        # Get spending summary
        result = await analytics_service.get_spending_summary(
            db=mock_db_session,
            user_id=1,
            period=Period.MONTHLY,
            start_date=date.today() - timedelta(days=90),
            end_date=date.today(),
        )
        
        # Verify monthly grouping
        assert result["period"] == "monthly"
        assert len(result["details"]) > 0
        
        # Check that dates are monthly
        for detail in result["details"]:
            date_obj = datetime.fromisoformat(detail["date"])
            assert date_obj.day == 1  # Monthly summaries should start on 1st
    
    @pytest.mark.asyncio
    async def test_get_category_breakdown(
        self,
        analytics_service: AnalyticsService,
        sample_transactions: list,
        mock_db_session: AsyncSession,
    ):
        """Test category breakdown analysis."""
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_transactions
        mock_db_session.execute.return_value = mock_result
        
        # Get category breakdown
        result = await analytics_service.get_category_breakdown(
            db=mock_db_session,
            user_id=1,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today(),
        )
        
        # Verify result structure
        assert "categories" in result
        assert "total_expenses" in result
        assert "top_categories" in result
        
        # Verify categories
        categories = result["categories"]
        assert "Food" in categories
        assert "Transport" in categories
        assert "Shopping" in categories
        
        # Verify calculations
        assert categories["Food"]["amount"] == 150.00  # 50 + 100
        assert categories["Food"]["count"] == 2
        assert categories["Food"]["percentage"] > 0
        
        # Verify top categories
        assert len(result["top_categories"]) <= 5
        assert result["top_categories"][0]["amount"] >= result["top_categories"][-1]["amount"]
    
    @pytest.mark.asyncio
    async def test_get_trend_analysis(
        self,
        analytics_service: AnalyticsService,
        sample_transactions: list,
        mock_db_session: AsyncSession,
    ):
        """Test trend analysis."""
        # Add more historical data for trend analysis
        historical_transactions = []
        for i in range(60):  # 60 days of data
            historical_transactions.append(
                Transaction(
                    id=100 + i,
                    user_id=1,
                    amount=Decimal(f"-{50 + (i % 20)}"),
                    category="Food",
                    description="Daily expense",
                    transaction_date=date.today() - timedelta(days=i),
                    type=TransactionType.EXPENSE,
                )
            )
        
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = historical_transactions
        mock_db_session.execute.return_value = mock_result
        
        # Get trend analysis
        result = await analytics_service.get_trend_analysis(
            db=mock_db_session,
            user_id=1,
            period=Period.MONTHLY,
        )
        
        # Verify result structure
        assert "current_month" in result
        assert "previous_month" in result
        assert "trend" in result
        assert "insights" in result
        
        # Verify trend calculation
        assert result["trend"]["direction"] in ["up", "down", "stable"]
        assert "percentage_change" in result["trend"]
        assert "amount_change" in result["trend"]
    
    @pytest.mark.asyncio
    async def test_get_spending_by_tags(
        self,
        analytics_service: AnalyticsService,
        mock_db_session: AsyncSession,
    ):
        """Test spending analysis by tags."""
        # Create transactions with tags
        tagged_transactions = [
            Transaction(
                id=1,
                user_id=1,
                amount=Decimal("-50.00"),
                category="Food",
                description="Groceries",
                transaction_date=date.today(),
                type=TransactionType.EXPENSE,
                tags=["essential", "recurring"],
            ),
            Transaction(
                id=2,
                user_id=1,
                amount=Decimal("-200.00"),
                category="Shopping",
                description="Clothes",
                transaction_date=date.today() - timedelta(days=1),
                type=TransactionType.EXPENSE,
                tags=["discretionary"],
            ),
        ]
        
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = tagged_transactions
        mock_db_session.execute.return_value = mock_result
        
        # Get spending by tags
        result = await analytics_service.get_spending_by_tags(
            db=mock_db_session,
            user_id=1,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today(),
        )
        
        # Verify result
        assert "tags" in result
        assert "essential" in result["tags"]
        assert "discretionary" in result["tags"]
        assert result["tags"]["essential"]["amount"] == 50.00
        assert result["tags"]["discretionary"]["amount"] == 200.00
    
    @pytest.mark.asyncio
    async def test_get_cashflow_forecast(
        self,
        analytics_service: AnalyticsService,
        sample_transactions: list,
        mock_db_session: AsyncSession,
    ):
        """Test cashflow forecasting."""
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_transactions
        mock_db_session.execute.return_value = mock_result
        
        # Get cashflow forecast
        result = await analytics_service.get_cashflow_forecast(
            db=mock_db_session,
            user_id=1,
            days_ahead=30,
        )
        
        # Verify result structure
        assert "current_balance" in result
        assert "forecast" in result
        assert "predicted_balance" in result
        assert "insights" in result
        
        # Verify forecast data
        assert len(result["forecast"]) == 30  # 30 days forecast
        assert all("date" in day for day in result["forecast"])
        assert all("predicted_balance" in day for day in result["forecast"])
        assert all("confidence" in day for day in result["forecast"])
    
    @pytest.mark.asyncio
    async def test_empty_transactions(
        self,
        analytics_service: AnalyticsService,
        mock_db_session: AsyncSession,
    ):
        """Test analytics with no transactions."""
        # Mock empty result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result
        
        # Get spending summary
        result = await analytics_service.get_spending_summary(
            db=mock_db_session,
            user_id=1,
            period=Period.DAILY,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today(),
        )
        
        # Verify empty results are handled
        assert result["summary"]["total_income"] == 0
        assert result["summary"]["total_expenses"] == 0
        assert result["summary"]["net_savings"] == 0
        assert len(result["details"]) >= 0  # Can have empty date entries
    
    @pytest.mark.asyncio
    async def test_analytics_caching(
        self,
        analytics_service: AnalyticsService,
        sample_transactions: list,
        mock_db_session: AsyncSession,
    ):
        """Test analytics caching functionality."""
        with patch("app.core.redis.get_redis_client") as mock_redis:
            # Setup Redis mock
            redis_client = AsyncMock()
            redis_client.get.return_value = None  # Cache miss
            redis_client.setex = AsyncMock()
            mock_redis.return_value = redis_client
            
            # Mock database query
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = sample_transactions
            mock_db_session.execute.return_value = mock_result
            
            # First call - should hit database and cache
            result1 = await analytics_service.get_spending_summary(
                db=mock_db_session,
                user_id=1,
                period=Period.DAILY,
                start_date=date.today() - timedelta(days=30),
                end_date=date.today(),
            )
            
            # Verify cache was set
            redis_client.setex.assert_called_once()
            
            # Setup cache hit
            import json
            redis_client.get.return_value = json.dumps(result1).encode()
            
            # Second call - should hit cache
            result2 = await analytics_service.get_spending_summary(
                db=mock_db_session,
                user_id=1,
                period=Period.DAILY,
                start_date=date.today() - timedelta(days=30),
                end_date=date.today(),
            )
            
            # Verify results are same
            assert result1 == result2
            
            # Verify database was called only once
            assert mock_db_session.execute.call_count == 1
    
    @pytest.mark.asyncio
    async def test_analytics_with_invalid_dates(
        self,
        analytics_service: AnalyticsService,
        mock_db_session: AsyncSession,
    ):
        """Test analytics with invalid date ranges."""
        # Test with end date before start date
        with pytest.raises(ValueError, match="End date must be after start date"):
            await analytics_service.get_spending_summary(
                db=mock_db_session,
                user_id=1,
                period=Period.DAILY,
                start_date=date.today(),
                end_date=date.today() - timedelta(days=30),
            )
        
        # Test with future dates
        future_date = date.today() + timedelta(days=365)
        result = await analytics_service.get_spending_summary(
            db=mock_db_session,
            user_id=1,
            period=Period.DAILY,
            start_date=date.today(),
            end_date=future_date,
        )
        
        # Should handle gracefully
        assert result is not None


@pytest.fixture
def mock_db_session():
    """Create mock database session."""
    session = AsyncMock(spec=AsyncSession)
    return session