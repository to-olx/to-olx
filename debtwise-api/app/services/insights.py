"""
Predictive insights service for forecasting and anomaly detection.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import numpy as np
from collections import defaultdict

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models import (
    Budget,
    BudgetPeriod,
    CashflowForecast,
    Category,
    InsightSeverity,
    InsightStatus,
    InsightType,
    PredictiveInsight,
    SpendingAnomaly,
    SpendingForecast,
    Transaction,
    TransactionType,
    User,
)
from app.schemas.insight import (
    GenerateForecastRequest,
    PredictiveInsightCreate,
)

logger = get_logger(__name__)


class InsightsService:
    """Service for generating predictive insights and forecasts."""
    
    def __init__(self, db: AsyncSession):
        """Initialize the insights service."""
        self.db = db
    
    async def generate_spending_forecast(
        self,
        user_id: int,
        start_date: date,
        end_date: date,
        category_id: Optional[int] = None,
    ) -> SpendingForecast:
        """
        Generate spending forecast for a user.
        
        Args:
            user_id: User ID
            start_date: Forecast start date
            end_date: Forecast end date
            category_id: Optional category ID for category-specific forecast
            
        Returns:
            SpendingForecast: Generated forecast
        """
        # Get historical transactions
        query = select(Transaction).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.transaction_type == TransactionType.EXPENSE,
                Transaction.transaction_date >= start_date - timedelta(days=365),
                Transaction.transaction_date < start_date,
            )
        )
        
        if category_id:
            query = query.where(Transaction.category_id == category_id)
        
        result = await self.db.execute(query)
        transactions = result.scalars().all()
        
        if not transactions:
            # No historical data, use defaults
            predicted_amount = Decimal("0.00")
            confidence = 0.0
        else:
            # Calculate historical statistics
            amounts = [float(t.amount) for t in transactions]
            historical_avg = Decimal(str(np.mean(amounts)))
            historical_std = float(np.std(amounts))
            
            # Simple time-based forecasting with trend detection
            # Group by month and calculate trend
            monthly_spending = defaultdict(float)
            for t in transactions:
                month_key = (t.transaction_date.year, t.transaction_date.month)
                monthly_spending[month_key] += float(t.amount)
            
            # Sort by date and calculate trend
            sorted_months = sorted(monthly_spending.items())
            if len(sorted_months) >= 3:
                # Use last 3 months to detect trend
                recent_values = [v for _, v in sorted_months[-3:]]
                trend = np.polyfit(range(len(recent_values)), recent_values, 1)[0]
                
                # Project forward
                months_ahead = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month) + 1
                predicted_monthly = recent_values[-1] + (trend * months_ahead)
                
                # Calculate total for period
                days_in_period = (end_date - start_date).days + 1
                avg_days_per_month = 30.44
                predicted_amount = Decimal(str(predicted_monthly * (days_in_period / avg_days_per_month)))
                
                # Confidence based on historical variance
                if historical_std > 0:
                    confidence = max(0.0, min(1.0, 1.0 - (historical_std / float(historical_avg))))
                else:
                    confidence = 0.95
                
                # Calculate bounds (95% confidence interval)
                z_score = 1.96  # 95% CI
                std_error = historical_std / np.sqrt(len(transactions))
                margin = z_score * std_error * (days_in_period / avg_days_per_month)
                
                lower_bound = max(Decimal("0"), predicted_amount - Decimal(str(margin)))
                upper_bound = predicted_amount + Decimal(str(margin))
                
                # Trend analysis
                if trend > 0.1 * float(historical_avg):
                    trend_direction = "increasing"
                    trend_percentage = (trend / float(historical_avg)) * 100
                elif trend < -0.1 * float(historical_avg):
                    trend_direction = "decreasing"
                    trend_percentage = (trend / float(historical_avg)) * 100
                else:
                    trend_direction = "stable"
                    trend_percentage = 0.0
            else:
                # Not enough data for trend, use average
                predicted_amount = historical_avg
                confidence = 0.5
                lower_bound = predicted_amount * Decimal("0.8")
                upper_bound = predicted_amount * Decimal("1.2")
                trend_direction = "stable"
                trend_percentage = 0.0
        
        # Create forecast record
        forecast = SpendingForecast(
            user_id=user_id,
            category_id=category_id,
            start_date=start_date,
            end_date=end_date,
            predicted_amount=predicted_amount,
            confidence_level=confidence,
            prediction_std_dev=Decimal(str(historical_std)) if transactions else None,
            lower_bound=lower_bound if transactions else Decimal("0"),
            upper_bound=upper_bound if transactions else Decimal("0"),
            model_type="statistical_trend",
            model_params={
                "method": "linear_regression",
                "historical_months": len(sorted_months) if transactions else 0,
                "trend_coefficient": float(trend) if transactions and len(sorted_months) >= 3 else 0,
            },
            historical_avg=historical_avg if transactions else Decimal("0"),
            trend_direction=trend_direction if transactions else None,
            trend_percentage=trend_percentage if transactions else None,
        )
        
        self.db.add(forecast)
        await self.db.commit()
        await self.db.refresh(forecast)
        
        return forecast
    
    async def generate_cashflow_forecast(
        self,
        user_id: int,
        forecast_date: date,
        account_name: Optional[str] = None,
    ) -> CashflowForecast:
        """
        Generate cash flow forecast for a user.
        
        Args:
            user_id: User ID
            forecast_date: Date to forecast
            account_name: Optional account name
            
        Returns:
            CashflowForecast: Generated forecast
        """
        # Get current balance (simplified - would integrate with actual account data)
        # For now, calculate from transaction history
        balance_query = select(
            func.sum(
                func.case(
                    (Transaction.transaction_type == TransactionType.INCOME, Transaction.amount),
                    (Transaction.transaction_type == TransactionType.EXPENSE, -Transaction.amount),
                    else_=0
                )
            )
        ).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.transaction_date <= datetime.now().date(),
            )
        )
        
        if account_name:
            balance_query = balance_query.where(Transaction.account_name == account_name)
        
        result = await self.db.execute(balance_query)
        current_balance = result.scalar() or Decimal("0")
        
        # Get historical patterns for income and expenses
        days_ahead = (forecast_date - datetime.now().date()).days
        
        # Income prediction
        income_query = select(Transaction).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.transaction_type == TransactionType.INCOME,
                Transaction.transaction_date >= datetime.now().date() - timedelta(days=90),
            )
        )
        
        if account_name:
            income_query = income_query.where(Transaction.account_name == account_name)
        
        result = await self.db.execute(income_query)
        income_transactions = result.scalars().all()
        
        # Identify recurring income
        income_patterns = self._detect_recurring_patterns(income_transactions)
        predicted_income = self._project_recurring_amount(income_patterns, days_ahead)
        
        # Expense prediction using spending forecast
        spending_forecast = await self.generate_spending_forecast(
            user_id,
            datetime.now().date(),
            forecast_date,
            None,
        )
        predicted_expenses = spending_forecast.predicted_amount
        
        # Calculate predicted balance
        predicted_balance = current_balance + predicted_income - predicted_expenses
        
        # Detect scheduled bills
        scheduled_bills = await self._get_scheduled_bills(user_id, forecast_date)
        
        # Calculate minimum balance and overdraft risk
        daily_expenses = predicted_expenses / Decimal(str(max(1, days_ahead)))
        running_balance = current_balance
        minimum_balance = current_balance
        low_balance_date = None
        
        for day in range(1, days_ahead + 1):
            # Subtract daily expenses
            running_balance -= daily_expenses
            
            # Add periodic income
            if day % 14 == 0:  # Bi-weekly income assumption
                running_balance += predicted_income / Decimal("2")
            
            # Track minimum
            if running_balance < minimum_balance:
                minimum_balance = running_balance
                low_balance_date = datetime.now().date() + timedelta(days=day)
        
        # Calculate overdraft risk
        if minimum_balance < 0:
            overdraft_risk = 1.0
        elif minimum_balance < current_balance * Decimal("0.1"):
            overdraft_risk = 0.7
        elif minimum_balance < current_balance * Decimal("0.2"):
            overdraft_risk = 0.3
        else:
            overdraft_risk = 0.0
        
        # Create forecast record
        forecast = CashflowForecast(
            user_id=user_id,
            forecast_date=forecast_date,
            account_name=account_name,
            current_balance=current_balance,
            predicted_income=predicted_income,
            predicted_expenses=predicted_expenses,
            predicted_balance=predicted_balance,
            minimum_balance=minimum_balance,
            low_balance_date=low_balance_date,
            overdraft_risk=overdraft_risk,
            scheduled_bills=scheduled_bills,
            scheduled_income=[],  # TODO: Implement scheduled income detection
        )
        
        self.db.add(forecast)
        await self.db.commit()
        await self.db.refresh(forecast)
        
        return forecast
    
    async def detect_spending_anomalies(
        self,
        user_id: int,
        lookback_days: int = 90,
    ) -> List[SpendingAnomaly]:
        """
        Detect spending anomalies for a user.
        
        Args:
            user_id: User ID
            lookback_days: Days to look back for anomaly detection
            
        Returns:
            List[SpendingAnomaly]: Detected anomalies
        """
        # Get recent transactions
        cutoff_date = datetime.now().date() - timedelta(days=lookback_days)
        
        query = select(Transaction).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.transaction_type == TransactionType.EXPENSE,
                Transaction.transaction_date >= cutoff_date,
            )
        ).options(selectinload(Transaction.category))
        
        result = await self.db.execute(query)
        transactions = result.scalars().all()
        
        if not transactions:
            return []
        
        anomalies = []
        
        # Group by category for analysis
        category_transactions = defaultdict(list)
        for t in transactions:
            category_key = t.category_id or "uncategorized"
            category_transactions[category_key].append(t)
        
        # Detect anomalies per category
        for category_key, cat_transactions in category_transactions.items():
            if len(cat_transactions) < 3:
                continue
            
            amounts = [float(t.amount) for t in cat_transactions]
            mean = np.mean(amounts)
            std = np.std(amounts)
            
            if std == 0:
                continue
            
            # Use z-score for anomaly detection
            for t in cat_transactions:
                z_score = abs((float(t.amount) - mean) / std)
                
                # Flag as anomaly if z-score > 2.5
                if z_score > 2.5:
                    anomaly = SpendingAnomaly(
                        user_id=user_id,
                        transaction_id=t.id,
                        anomaly_score=z_score,
                        anomaly_type="amount",
                        expected_range_min=Decimal(str(max(0, mean - 2 * std))),
                        expected_range_max=Decimal(str(mean + 2 * std)),
                        actual_amount=t.amount,
                        detection_method="z_score",
                        confidence=min(0.99, z_score / 4),  # Cap at 0.99
                        context_data={
                            "category_mean": mean,
                            "category_std": std,
                            "sample_size": len(cat_transactions),
                            "merchant": t.merchant,
                        },
                    )
                    anomalies.append(anomaly)
        
        # Save anomalies
        for anomaly in anomalies:
            self.db.add(anomaly)
        
        if anomalies:
            await self.db.commit()
            for anomaly in anomalies:
                await self.db.refresh(anomaly)
        
        return anomalies
    
    async def generate_insights(
        self,
        user_id: int,
    ) -> List[PredictiveInsight]:
        """
        Generate predictive insights for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List[PredictiveInsight]: Generated insights
        """
        insights = []
        
        # Check spending trends
        spending_insight = await self._generate_spending_trend_insight(user_id)
        if spending_insight:
            insights.append(spending_insight)
        
        # Check budget health
        budget_insights = await self._generate_budget_insights(user_id)
        insights.extend(budget_insights)
        
        # Check for anomalies
        anomaly_insights = await self._generate_anomaly_insights(user_id)
        insights.extend(anomaly_insights)
        
        # Check cash flow health
        cashflow_insight = await self._generate_cashflow_insight(user_id)
        if cashflow_insight:
            insights.append(cashflow_insight)
        
        # Save all insights
        for insight in insights:
            self.db.add(insight)
        
        if insights:
            await self.db.commit()
            for insight in insights:
                await self.db.refresh(insight)
        
        return insights
    
    def _detect_recurring_patterns(
        self,
        transactions: List[Transaction],
    ) -> Dict[str, Dict]:
        """Detect recurring transaction patterns."""
        if not transactions:
            return {}
        
        # Simple pattern detection based on merchant and amount
        patterns = defaultdict(list)
        
        for t in transactions:
            key = f"{t.merchant}:{float(t.amount):.2f}"
            patterns[key].append(t.transaction_date)
        
        recurring = {}
        for key, dates in patterns.items():
            if len(dates) >= 2:
                # Calculate intervals
                sorted_dates = sorted(dates)
                intervals = [(sorted_dates[i+1] - sorted_dates[i]).days 
                           for i in range(len(sorted_dates) - 1)]
                
                if intervals:
                    avg_interval = np.mean(intervals)
                    merchant, amount = key.split(":")
                    
                    recurring[key] = {
                        "merchant": merchant,
                        "amount": Decimal(amount),
                        "interval_days": avg_interval,
                        "occurrences": len(dates),
                        "last_date": sorted_dates[-1],
                    }
        
        return recurring
    
    def _project_recurring_amount(
        self,
        patterns: Dict[str, Dict],
        days_ahead: int,
    ) -> Decimal:
        """Project recurring amounts forward."""
        total = Decimal("0")
        
        for pattern in patterns.values():
            interval = pattern["interval_days"]
            if interval > 0:
                occurrences = days_ahead / interval
                total += pattern["amount"] * Decimal(str(occurrences))
        
        return total
    
    async def _get_scheduled_bills(
        self,
        user_id: int,
        until_date: date,
    ) -> List[Dict]:
        """Get scheduled bills until a certain date."""
        # Query recurring transactions
        query = select(Transaction).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.is_recurring == True,
                Transaction.transaction_type == TransactionType.EXPENSE,
            )
        )
        
        result = await self.db.execute(query)
        recurring = result.scalars().all()
        
        bills = []
        for t in recurring:
            bills.append({
                "description": t.description,
                "amount": str(t.amount),
                "expected_date": None,  # TODO: Calculate next occurrence
                "merchant": t.merchant,
            })
        
        return bills
    
    async def _generate_spending_trend_insight(
        self,
        user_id: int,
    ) -> Optional[PredictiveInsight]:
        """Generate insight about spending trends."""
        # Get current month spending
        current_month_start = date.today().replace(day=1)
        
        query = select(func.sum(Transaction.amount)).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.transaction_type == TransactionType.EXPENSE,
                Transaction.transaction_date >= current_month_start,
            )
        )
        
        result = await self.db.execute(query)
        current_spending = result.scalar() or Decimal("0")
        
        # Get last month's spending
        last_month_end = current_month_start - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        
        query = select(func.sum(Transaction.amount)).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.transaction_type == TransactionType.EXPENSE,
                Transaction.transaction_date >= last_month_start,
                Transaction.transaction_date <= last_month_end,
            )
        )
        
        result = await self.db.execute(query)
        last_month_spending = result.scalar() or Decimal("0")
        
        if last_month_spending == 0:
            return None
        
        # Calculate change
        change_pct = ((current_spending - last_month_spending) / last_month_spending) * 100
        
        if abs(change_pct) > 20:  # Significant change
            if change_pct > 0:
                title = "Spending Increase Detected"
                description = f"Your spending this month is {change_pct:.1f}% higher than last month."
                severity = InsightSeverity.WARNING
                recommendation = "Review your recent expenses to identify areas where you can cut back."
            else:
                title = "Great Job on Spending Reduction!"
                description = f"Your spending this month is {abs(change_pct):.1f}% lower than last month."
                severity = InsightSeverity.SUCCESS
                recommendation = "Keep up the good work! Consider putting the savings toward your financial goals."
            
            return PredictiveInsight(
                user_id=user_id,
                insight_type=InsightType.SPENDING_FORECAST,
                title=title,
                description=description,
                severity=severity,
                status=InsightStatus.ACTIVE,
                insight_data={
                    "current_month_spending": str(current_spending),
                    "last_month_spending": str(last_month_spending),
                    "change_percentage": float(change_pct),
                },
                recommendation=recommendation,
                action_items=[
                    "Review transaction history",
                    "Update budget if needed",
                    "Set spending alerts",
                ],
                potential_savings=max(Decimal("0"), current_spending - last_month_spending),
                valid_until=current_month_start + timedelta(days=30),
            )
        
        return None
    
    async def _generate_budget_insights(
        self,
        user_id: int,
    ) -> List[PredictiveInsight]:
        """Generate insights about budget health."""
        insights = []
        
        # Get active budgets with current period
        query = select(Budget).where(
            and_(
                Budget.user_id == user_id,
                Budget.is_active == True,
            )
        ).options(selectinload(Budget.budget_periods))
        
        result = await self.db.execute(query)
        budgets = result.scalars().all()
        
        for budget in budgets:
            # Find current period
            current_period = None
            today = date.today()
            
            for period in budget.budget_periods:
                if period.start_date <= today <= period.end_date:
                    current_period = period
                    break
            
            if not current_period:
                continue
            
            # Calculate usage percentage
            if current_period.total_amount > 0:
                usage_pct = (current_period.spent_amount / current_period.total_amount) * 100
                
                # Days progress in period
                period_days = (current_period.end_date - current_period.start_date).days + 1
                elapsed_days = (today - current_period.start_date).days + 1
                progress_pct = (elapsed_days / period_days) * 100
                
                # Check if overspending
                if usage_pct > progress_pct + 10:  # 10% tolerance
                    pace_ratio = usage_pct / progress_pct
                    projected_overage = (pace_ratio * current_period.total_amount) - current_period.total_amount
                    
                    insight = PredictiveInsight(
                        user_id=user_id,
                        insight_type=InsightType.BUDGET_PROJECTION,
                        title=f"Budget Alert: {budget.name}",
                        description=f"You've used {usage_pct:.1f}% of your budget but are only {progress_pct:.1f}% through the period.",
                        severity=InsightSeverity.WARNING if usage_pct < 90 else InsightSeverity.CRITICAL,
                        status=InsightStatus.ACTIVE,
                        budget_id=budget.id,
                        insight_data={
                            "budget_name": budget.name,
                            "usage_percentage": float(usage_pct),
                            "progress_percentage": float(progress_pct),
                            "projected_overage": str(projected_overage),
                            "remaining_days": (current_period.end_date - today).days,
                        },
                        recommendation=f"Reduce spending to stay within budget. Aim to spend no more than ${current_period.remaining_amount / ((current_period.end_date - today).days + 1):.2f} per day.",
                        action_items=[
                            "Review recent transactions",
                            "Identify non-essential expenses",
                            "Consider adjusting budget if unrealistic",
                        ],
                        potential_savings=projected_overage,
                        risk_score=min(1.0, usage_pct / 100),
                        valid_until=current_period.end_date,
                    )
                    insights.append(insight)
        
        return insights
    
    async def _generate_anomaly_insights(
        self,
        user_id: int,
    ) -> List[PredictiveInsight]:
        """Generate insights from detected anomalies."""
        # Get recent unconfirmed anomalies
        query = select(SpendingAnomaly).where(
            and_(
                SpendingAnomaly.user_id == user_id,
                SpendingAnomaly.is_confirmed == None,
                SpendingAnomaly.created_at >= datetime.now() - timedelta(days=7),
            )
        ).options(selectinload(SpendingAnomaly.transaction))
        
        result = await self.db.execute(query)
        anomalies = result.scalars().all()
        
        if not anomalies:
            return []
        
        # Group by anomaly type
        high_amount_anomalies = [a for a in anomalies if a.anomaly_score > 3]
        
        if len(high_amount_anomalies) >= 3:
            total_excess = sum(
                a.actual_amount - (a.expected_range_max or a.actual_amount)
                for a in high_amount_anomalies
            )
            
            insight = PredictiveInsight(
                user_id=user_id,
                insight_type=InsightType.ANOMALY_DETECTION,
                title="Multiple Unusual Transactions Detected",
                description=f"We've detected {len(high_amount_anomalies)} unusually high transactions in the past week.",
                severity=InsightSeverity.WARNING,
                status=InsightStatus.ACTIVE,
                insight_data={
                    "anomaly_count": len(high_amount_anomalies),
                    "total_excess": str(total_excess),
                    "transactions": [
                        {
                            "id": a.transaction_id,
                            "amount": str(a.actual_amount),
                            "description": a.transaction.description if a.transaction else None,
                        }
                        for a in high_amount_anomalies[:5]  # Limit to 5
                    ],
                },
                transaction_ids=[a.transaction_id for a in high_amount_anomalies],
                recommendation="Review these transactions to ensure they're legitimate and update your budget if needed.",
                action_items=[
                    "Verify transaction legitimacy",
                    "Update category budgets if needed",
                    "Set up alerts for large transactions",
                ],
                risk_score=0.7,
                valid_until=date.today() + timedelta(days=7),
            )
            
            return [insight]
        
        return []
    
    async def _generate_cashflow_insight(
        self,
        user_id: int,
    ) -> Optional[PredictiveInsight]:
        """Generate insight about cash flow health."""
        # Generate 30-day forecast
        forecast = await self.generate_cashflow_forecast(
            user_id,
            date.today() + timedelta(days=30),
        )
        
        if forecast.overdraft_risk > 0.5:
            days_until_low = (forecast.low_balance_date - date.today()).days if forecast.low_balance_date else 0
            
            insight = PredictiveInsight(
                user_id=user_id,
                insight_type=InsightType.CASHFLOW_FORECAST,
                title="Cash Flow Warning",
                description=f"Your account balance may run low in {days_until_low} days based on current spending patterns.",
                severity=InsightSeverity.CRITICAL if forecast.overdraft_risk > 0.8 else InsightSeverity.WARNING,
                status=InsightStatus.ACTIVE,
                insight_data={
                    "current_balance": str(forecast.current_balance),
                    "predicted_balance": str(forecast.predicted_balance),
                    "minimum_balance": str(forecast.minimum_balance),
                    "overdraft_risk": forecast.overdraft_risk,
                    "low_balance_date": forecast.low_balance_date.isoformat() if forecast.low_balance_date else None,
                },
                recommendation="Consider reducing non-essential expenses or increasing income to maintain a healthy balance.",
                action_items=[
                    "Review upcoming bills",
                    "Postpone non-essential purchases",
                    "Set up balance alerts",
                ],
                risk_score=forecast.overdraft_risk,
                valid_until=forecast.low_balance_date or date.today() + timedelta(days=7),
            )
            
            return insight
        
        return None
    
    async def get_dashboard_insights(
        self,
        user_id: int,
    ) -> Dict:
        """
        Get dashboard insights summary for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dict: Dashboard insights data
        """
        # Get current month spending
        current_month_start = date.today().replace(day=1)
        
        spending_query = select(func.sum(Transaction.amount)).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.transaction_type == TransactionType.EXPENSE,
                Transaction.transaction_date >= current_month_start,
            )
        )
        
        result = await self.db.execute(spending_query)
        current_month_spending = result.scalar() or Decimal("0")
        
        # Get spending forecast
        month_end = (current_month_start + timedelta(days=31)).replace(day=1) - timedelta(days=1)
        spending_forecast = await self.generate_spending_forecast(
            user_id,
            current_month_start,
            month_end,
        )
        
        # Get active insights
        insights_query = select(PredictiveInsight).where(
            and_(
                PredictiveInsight.user_id == user_id,
                PredictiveInsight.status == InsightStatus.ACTIVE,
            )
        )
        
        result = await self.db.execute(insights_query)
        active_insights = result.scalars().all()
        
        # Get recent anomalies
        anomalies_query = select(SpendingAnomaly).where(
            and_(
                SpendingAnomaly.user_id == user_id,
                SpendingAnomaly.created_at >= datetime.now() - timedelta(days=7),
            )
        ).limit(5)
        
        result = await self.db.execute(anomalies_query)
        recent_anomalies = result.scalars().all()
        
        # Get budgets at risk
        budgets_query = select(Budget).where(
            and_(
                Budget.user_id == user_id,
                Budget.is_active == True,
            )
        ).options(selectinload(Budget.budget_periods))
        
        result = await self.db.execute(budgets_query)
        budgets = result.scalars().all()
        
        budgets_at_risk = 0
        projected_overages = []
        
        for budget in budgets:
            current_period = next(
                (p for p in budget.budget_periods 
                 if p.start_date <= date.today() <= p.end_date),
                None
            )
            
            if current_period and current_period.total_amount > 0:
                usage_pct = (current_period.spent_amount / current_period.total_amount) * 100
                if usage_pct > 80:
                    budgets_at_risk += 1
                    if usage_pct > 100:
                        projected_overages.append({
                            "budget_name": budget.name,
                            "overage_amount": str(current_period.spent_amount - current_period.total_amount),
                            "usage_percentage": float(usage_pct),
                        })
        
        # Calculate savings opportunities
        savings_opportunities = [
            insight for insight in active_insights
            if insight.potential_savings and insight.potential_savings > 0
        ]
        
        total_potential_savings = sum(
            i.potential_savings for i in savings_opportunities
            if i.potential_savings
        )
        
        # Get cash flow forecast
        cashflow_7d = await self.generate_cashflow_forecast(
            user_id,
            date.today() + timedelta(days=7),
        )
        
        cashflow_30d = await self.generate_cashflow_forecast(
            user_id,
            date.today() + timedelta(days=30),
        )
        
        # Compile dashboard data
        return {
            "current_month_spending": current_month_spending,
            "predicted_month_end": spending_forecast.predicted_amount if spending_forecast else Decimal("0"),
            "spending_trend": spending_forecast.trend_direction if spending_forecast else "stable",
            "trend_percentage": spending_forecast.trend_percentage if spending_forecast else 0.0,
            "budgets_at_risk": budgets_at_risk,
            "total_budget_utilization": 0.0,  # TODO: Calculate overall utilization
            "projected_overages": projected_overages,
            "recent_anomalies": recent_anomalies,
            "anomaly_count": len(recent_anomalies),
            "active_insights": active_insights,
            "critical_alerts": len([i for i in active_insights if i.severity == InsightSeverity.CRITICAL]),
            "warning_alerts": len([i for i in active_insights if i.severity == InsightSeverity.WARNING]),
            "total_potential_savings": total_potential_savings,
            "top_savings_opportunities": [
                {
                    "title": i.title,
                    "amount": str(i.potential_savings),
                    "description": i.description,
                }
                for i in sorted(
                    savings_opportunities,
                    key=lambda x: x.potential_savings or 0,
                    reverse=True
                )[:3]
            ],
            "current_balance": cashflow_7d.current_balance if cashflow_7d else Decimal("0"),
            "predicted_7_day_balance": cashflow_7d.predicted_balance if cashflow_7d else Decimal("0"),
            "predicted_30_day_balance": cashflow_30d.predicted_balance if cashflow_30d else Decimal("0"),
            "low_balance_warning": {
                "date": cashflow_30d.low_balance_date.isoformat() if cashflow_30d.low_balance_date else None,
                "minimum_balance": str(cashflow_30d.minimum_balance),
                "risk": cashflow_30d.overdraft_risk,
            } if cashflow_30d and cashflow_30d.overdraft_risk > 0.3 else None,
        }


# Create service instance
def get_insights_service(db: AsyncSession) -> InsightsService:
    """Get insights service instance."""
    return InsightsService(db)