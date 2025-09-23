"""
Tests for insights service.
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.insight import Insight, InsightType, InsightPriority
from app.models.transaction import Transaction, TransactionType
from app.models.budget import Budget, BudgetPeriod
from app.models.debt import Debt, DebtType
from app.models.user import User
from app.services.insights import InsightsService


@pytest.fixture
def insights_service():
    """Create insights service instance."""
    return InsightsService()


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
    """Create sample transactions for insights testing."""
    base_date = datetime.now().date()
    
    transactions = []
    # Create pattern of increasing food expenses
    for i in range(30):
        amount = Decimal(f"-{50 + i * 2}")  # Increasing amounts
        transactions.append(
            Transaction(
                id=i + 1,
                user_id=1,
                amount=amount,
                category="Food",
                description=f"Food expense {i}",
                transaction_date=base_date - timedelta(days=i),
                type=TransactionType.EXPENSE,
            )
        )
    
    # Add some recurring transactions
    for i in range(3):
        transactions.append(
            Transaction(
                id=100 + i,
                user_id=1,
                amount=Decimal("-9.99"),
                category="Entertainment",
                description="Netflix subscription",
                transaction_date=base_date - timedelta(days=i * 30),
                type=TransactionType.EXPENSE,
                tags=["subscription"],
            )
        )
    
    return transactions


@pytest.fixture
def sample_budgets():
    """Create sample budgets."""
    return [
        Budget(
            id=1,
            user_id=1,
            name="Food Budget",
            category="Food",
            amount=Decimal("500.00"),
            period=BudgetPeriod.MONTHLY,
            start_date=date.today().replace(day=1),
        ),
        Budget(
            id=2,
            user_id=1,
            name="Entertainment Budget",
            category="Entertainment",
            amount=Decimal("100.00"),
            period=BudgetPeriod.MONTHLY,
            start_date=date.today().replace(day=1),
        ),
    ]


@pytest.fixture
def sample_debts():
    """Create sample debts."""
    return [
        Debt(
            id=1,
            user_id=1,
            name="Credit Card",
            type=DebtType.CREDIT_CARD,
            original_amount=Decimal("5000.00"),
            current_balance=Decimal("4500.00"),
            interest_rate=Decimal("18.99"),
            minimum_payment=Decimal("100.00"),
            due_date=date.today() + timedelta(days=15),
        ),
        Debt(
            id=2,
            user_id=1,
            name="Student Loan",
            type=DebtType.LOAN,
            original_amount=Decimal("20000.00"),
            current_balance=Decimal("15000.00"),
            interest_rate=Decimal("5.50"),
            minimum_payment=Decimal("250.00"),
            due_date=date.today() + timedelta(days=20),
        ),
    ]


class TestInsightsService:
    """Test insights service functionality."""
    
    @pytest.mark.asyncio
    async def test_generate_spending_insights(
        self,
        insights_service: InsightsService,
        sample_transactions: list,
        mock_db_session: AsyncSession,
    ):
        """Test spending insights generation."""
        # Mock transaction query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_transactions
        mock_db_session.execute.return_value = mock_result
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        
        # Generate insights
        insights = await insights_service.generate_spending_insights(
            db=mock_db_session,
            user_id=1,
        )
        
        # Verify insights were generated
        assert len(insights) > 0
        
        # Check for spending trend insight
        trend_insights = [i for i in insights if i.type == InsightType.SPENDING_TREND]
        assert len(trend_insights) > 0
        assert "Food" in trend_insights[0].title
        
        # Check for recurring transaction insight
        recurring_insights = [i for i in insights if "subscription" in i.description.lower()]
        assert len(recurring_insights) > 0
    
    @pytest.mark.asyncio
    async def test_generate_budget_insights(
        self,
        insights_service: InsightsService,
        sample_budgets: list,
        sample_transactions: list,
        mock_db_session: AsyncSession,
    ):
        """Test budget-related insights generation."""
        # Setup mocks for multiple queries
        mock_budgets_result = MagicMock()
        mock_budgets_result.scalars.return_value.all.return_value = sample_budgets
        
        # Only return Food transactions for budget calculation
        food_transactions = [t for t in sample_transactions if t.category == "Food"]
        mock_trans_result = MagicMock()
        mock_trans_result.scalars.return_value.all.return_value = food_transactions
        
        mock_db_session.execute.side_effect = [mock_budgets_result, mock_trans_result]
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        
        # Generate insights
        insights = await insights_service.generate_budget_insights(
            db=mock_db_session,
            user_id=1,
        )
        
        # Verify budget insights
        assert len(insights) > 0
        
        # Should have over-budget insight for Food
        over_budget_insights = [i for i in insights if i.type == InsightType.BUDGET_STATUS]
        assert len(over_budget_insights) > 0
        assert any("Food" in i.title for i in over_budget_insights)
    
    @pytest.mark.asyncio
    async def test_generate_debt_insights(
        self,
        insights_service: InsightsService,
        sample_debts: list,
        mock_db_session: AsyncSession,
    ):
        """Test debt-related insights generation."""
        # Mock debt query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_debts
        mock_db_session.execute.return_value = mock_result
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        
        # Generate insights
        insights = await insights_service.generate_debt_insights(
            db=mock_db_session,
            user_id=1,
        )
        
        # Verify debt insights
        assert len(insights) > 0
        
        # Should have high interest rate warning
        high_interest_insights = [i for i in insights if "interest" in i.description.lower()]
        assert len(high_interest_insights) > 0
        
        # Should have payment reminder
        payment_insights = [i for i in insights if i.type == InsightType.PAYMENT_DUE]
        assert len(payment_insights) > 0
    
    @pytest.mark.asyncio
    async def test_generate_savings_opportunities(
        self,
        insights_service: InsightsService,
        sample_transactions: list,
        mock_db_session: AsyncSession,
    ):
        """Test savings opportunity insights."""
        # Add some transactions with potential savings
        sample_transactions.extend([
            Transaction(
                id=200,
                user_id=1,
                amount=Decimal("-150.00"),
                category="Food",
                description="Restaurant - fancy dinner",
                transaction_date=date.today() - timedelta(days=1),
                type=TransactionType.EXPENSE,
                tags=["dining_out"],
            ),
            Transaction(
                id=201,
                user_id=1,
                amount=Decimal("-120.00"),
                category="Entertainment",
                description="Multiple streaming services",
                transaction_date=date.today() - timedelta(days=2),
                type=TransactionType.EXPENSE,
                tags=["subscription"],
            ),
        ])
        
        # Mock query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_transactions
        mock_db_session.execute.return_value = mock_result
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        
        # Generate insights
        insights = await insights_service.generate_savings_opportunities(
            db=mock_db_session,
            user_id=1,
        )
        
        # Verify savings insights
        assert len(insights) > 0
        
        # Should identify dining out savings
        dining_insights = [i for i in insights if "dining" in i.description.lower()]
        assert len(dining_insights) > 0
        
        # Should identify subscription overlap
        subscription_insights = [i for i in insights if "subscription" in i.description.lower()]
        assert len(subscription_insights) > 0
    
    @pytest.mark.asyncio
    async def test_get_user_insights_with_limit(
        self,
        insights_service: InsightsService,
        mock_db_session: AsyncSession,
    ):
        """Test getting user insights with limit."""
        # Create multiple insights
        insights = []
        for i in range(10):
            insights.append(
                Insight(
                    id=i + 1,
                    user_id=1,
                    type=InsightType.SPENDING_PATTERN,
                    title=f"Insight {i + 1}",
                    description=f"Description {i + 1}",
                    priority=InsightPriority.MEDIUM,
                    created_at=datetime.now() - timedelta(hours=i),
                )
            )
        
        # Mock query
        mock_result = MagicMock()
        # Only return first 5 insights
        mock_result.scalars.return_value.all.return_value = insights[:5]
        mock_db_session.execute.return_value = mock_result
        
        # Get insights with limit
        result = await insights_service.get_user_insights(
            db=mock_db_session,
            user_id=1,
            limit=5,
        )
        
        # Verify limit was applied
        assert len(result) == 5
        # Verify ordering (newest first)
        assert result[0].id == 1
    
    @pytest.mark.asyncio
    async def test_mark_insight_as_viewed(
        self,
        insights_service: InsightsService,
        mock_db_session: AsyncSession,
    ):
        """Test marking insight as viewed."""
        # Create insight
        insight = Insight(
            id=1,
            user_id=1,
            type=InsightType.SPENDING_PATTERN,
            title="Test Insight",
            description="Test Description",
            priority=InsightPriority.HIGH,
            is_read=False,
        )
        
        # Mock query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = insight
        mock_db_session.execute.return_value = mock_result
        mock_db_session.commit = AsyncMock()
        
        # Mark as viewed
        result = await insights_service.mark_insight_as_viewed(
            db=mock_db_session,
            insight_id=1,
            user_id=1,
        )
        
        # Verify marking
        assert result is True
        assert insight.is_read is True
        mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_dismiss_insight(
        self,
        insights_service: InsightsService,
        mock_db_session: AsyncSession,
    ):
        """Test dismissing an insight."""
        # Create insight
        insight = Insight(
            id=1,
            user_id=1,
            type=InsightType.SPENDING_PATTERN,
            title="Test Insight",
            description="Test Description",
            priority=InsightPriority.LOW,
            is_dismissed=False,
        )
        
        # Mock query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = insight
        mock_db_session.execute.return_value = mock_result
        mock_db_session.commit = AsyncMock()
        
        # Dismiss insight
        result = await insights_service.dismiss_insight(
            db=mock_db_session,
            insight_id=1,
            user_id=1,
        )
        
        # Verify dismissal
        assert result is True
        assert insight.is_dismissed is True
        mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ai_powered_insights(
        self,
        insights_service: InsightsService,
        sample_transactions: list,
        mock_db_session: AsyncSession,
    ):
        """Test AI-powered insight generation."""
        # Mock transaction query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_transactions
        mock_db_session.execute.return_value = mock_result
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        
        # Mock AI service
        with patch("app.services.insights.call_ai_service") as mock_ai:
            mock_ai.return_value = {
                "insights": [
                    {
                        "type": "anomaly",
                        "title": "Unusual spending detected",
                        "description": "Your Food spending has increased by 40% this month",
                        "priority": "high",
                        "recommendations": ["Set a stricter budget", "Track daily expenses"],
                    }
                ]
            }
            
            # Generate AI insights
            insights = await insights_service.generate_ai_insights(
                db=mock_db_session,
                user_id=1,
                transactions=sample_transactions,
            )
            
            # Verify AI insights
            assert len(insights) > 0
            assert insights[0].type == InsightType.ANOMALY
            assert insights[0].priority == InsightPriority.HIGH
            assert "Unusual spending" in insights[0].title
    
    @pytest.mark.asyncio
    async def test_insights_caching(
        self,
        insights_service: InsightsService,
        mock_db_session: AsyncSession,
    ):
        """Test insights caching mechanism."""
        # Create insights
        insights = [
            Insight(
                id=1,
                user_id=1,
                type=InsightType.SPENDING_PATTERN,
                title="Cached Insight",
                description="This should be cached",
                priority=InsightPriority.MEDIUM,
            )
        ]
        
        with patch("app.core.redis.get_redis_client") as mock_redis:
            # Setup Redis mock
            redis_client = AsyncMock()
            redis_client.get.return_value = None  # Cache miss
            redis_client.setex = AsyncMock()
            mock_redis.return_value = redis_client
            
            # Mock database query
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = insights
            mock_db_session.execute.return_value = mock_result
            
            # First call - should hit database
            result1 = await insights_service.get_user_insights(
                db=mock_db_session,
                user_id=1,
                use_cache=True,
            )
            
            # Verify cache was set
            redis_client.setex.assert_called_once()
            
            # Second call - should hit cache
            import json
            redis_client.get.return_value = json.dumps([{
                "id": 1,
                "title": "Cached Insight",
                "description": "This should be cached",
                "type": "spending_pattern",
                "priority": "medium",
            }]).encode()
            
            result2 = await insights_service.get_user_insights(
                db=mock_db_session,
                user_id=1,
                use_cache=True,
            )
            
            # Verify only one database call
            assert mock_db_session.execute.call_count == 1
    
    @pytest.mark.asyncio
    async def test_insights_priority_ordering(
        self,
        insights_service: InsightsService,
        mock_db_session: AsyncSession,
    ):
        """Test insights are ordered by priority."""
        # Create insights with different priorities
        insights = [
            Insight(
                id=1,
                user_id=1,
                type=InsightType.SPENDING_PATTERN,
                title="Low Priority",
                description="Description",
                priority=InsightPriority.LOW,
                created_at=datetime.now(),
            ),
            Insight(
                id=2,
                user_id=1,
                type=InsightType.BUDGET_STATUS,
                title="High Priority",
                description="Description",
                priority=InsightPriority.HIGH,
                created_at=datetime.now() - timedelta(hours=1),
            ),
            Insight(
                id=3,
                user_id=1,
                type=InsightType.SAVINGS_TIP,
                title="Medium Priority",
                description="Description",
                priority=InsightPriority.MEDIUM,
                created_at=datetime.now() - timedelta(hours=2),
            ),
        ]
        
        # Mock query
        mock_result = MagicMock()
        # Return in priority order
        mock_result.scalars.return_value.all.return_value = [
            insights[1],  # High
            insights[2],  # Medium
            insights[0],  # Low
        ]
        mock_db_session.execute.return_value = mock_result
        
        # Get insights
        result = await insights_service.get_user_insights(
            db=mock_db_session,
            user_id=1,
        )
        
        # Verify priority ordering
        assert result[0].priority == InsightPriority.HIGH
        assert result[1].priority == InsightPriority.MEDIUM
        assert result[2].priority == InsightPriority.LOW


@pytest.fixture
def mock_db_session():
    """Create mock database session."""
    session = AsyncMock(spec=AsyncSession)
    return session