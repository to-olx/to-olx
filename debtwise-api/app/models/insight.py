"""
Predictive insights and forecast models.
"""

from datetime import date
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    JSON,
    Numeric,
    String,
    Text,
    Enum,
    Float,
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class InsightType(str, PyEnum):
    """Type of insight or prediction."""
    
    SPENDING_FORECAST = "spending_forecast"
    CASHFLOW_FORECAST = "cashflow_forecast"
    BUDGET_PROJECTION = "budget_projection"
    ANOMALY_DETECTION = "anomaly_detection"
    CATEGORY_TREND = "category_trend"
    DEBT_PAYOFF = "debt_payoff"
    SAVINGS_OPPORTUNITY = "savings_opportunity"


class InsightSeverity(str, PyEnum):
    """Severity level for insights and alerts."""
    
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    CRITICAL = "critical"


class InsightStatus(str, PyEnum):
    """Status of an insight."""
    
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class SpendingForecast(BaseModel):
    """Spending forecast model for predicting future expenses."""
    
    __tablename__ = "spending_forecasts"
    
    # Foreign keys
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Specific category forecast, null for overall forecast",
    )
    
    # Forecast period
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Predicted values
    predicted_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Predicted spending amount",
    )
    confidence_level: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Confidence level (0-1)",
    )
    prediction_std_dev: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Standard deviation of prediction",
    )
    
    # Prediction bounds
    lower_bound: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Lower prediction bound (e.g., 95% CI)",
    )
    upper_bound: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Upper prediction bound (e.g., 95% CI)",
    )
    
    # Model metadata
    model_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Algorithm used (e.g., 'arima', 'prophet', 'ml_ensemble')",
    )
    model_params: Mapped[Optional[Dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Model parameters and configuration",
    )
    
    # Historical basis
    historical_avg: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Historical average for comparison",
    )
    trend_direction: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Trend: 'increasing', 'decreasing', 'stable'",
    )
    trend_percentage: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Percentage change from historical average",
    )
    
    # Actual values (updated when period completes)
    actual_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Actual spending when period completes",
    )
    accuracy_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Model accuracy score (0-1)",
    )
    
    # Relationships
    user = relationship("User", backref="spending_forecasts")
    category = relationship("Category", backref="spending_forecasts")
    
    def __repr__(self) -> str:
        """String representation of the forecast."""
        return f"<SpendingForecast(id={self.id}, amount={self.predicted_amount}, period={self.start_date} to {self.end_date})>"


class CashflowForecast(BaseModel):
    """Cash flow forecast model for predicting account balances."""
    
    __tablename__ = "cashflow_forecasts"
    
    # Foreign keys
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Forecast date
    forecast_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    
    # Account information
    account_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Specific account, null for all accounts",
    )
    
    # Current state
    current_balance: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Current account balance",
    )
    
    # Predictions
    predicted_income: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    predicted_expenses: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    predicted_balance: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Predicted end balance",
    )
    
    # Risk indicators
    minimum_balance: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Predicted minimum balance during period",
    )
    low_balance_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Date of predicted minimum balance",
    )
    overdraft_risk: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Probability of overdraft (0-1)",
    )
    
    # Scheduled transactions
    scheduled_bills: Mapped[Optional[List[Dict]]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of upcoming scheduled bills",
    )
    scheduled_income: Mapped[Optional[List[Dict]]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of expected income",
    )
    
    # Relationships
    user = relationship("User", backref="cashflow_forecasts")


class PredictiveInsight(BaseModel):
    """Predictive insights and recommendations model."""
    
    __tablename__ = "predictive_insights"
    
    # Foreign keys
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Insight information
    insight_type: Mapped[InsightType] = mapped_column(
        Enum(InsightType),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Severity and status
    severity: Mapped[InsightSeverity] = mapped_column(
        Enum(InsightSeverity),
        nullable=False,
        default=InsightSeverity.INFO,
    )
    status: Mapped[InsightStatus] = mapped_column(
        Enum(InsightStatus),
        nullable=False,
        default=InsightStatus.ACTIVE,
        index=True,
    )
    
    # Insight data
    insight_data: Mapped[Dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Structured data for the insight",
    )
    
    # Related entities
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    budget_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("budgets.id", ondelete="SET NULL"),
        nullable=True,
    )
    transaction_ids: Mapped[Optional[List[int]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Related transaction IDs",
    )
    
    # Recommendation
    recommendation: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    action_items: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Suggested actions",
    )
    
    # Impact metrics
    potential_savings: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    risk_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Risk level (0-1)",
    )
    
    # Validity
    valid_until: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Date when insight expires",
    )
    
    # User interaction
    acknowledged_at: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    dismissed_at: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    
    # Relationships
    user = relationship("User", backref="predictive_insights")
    category = relationship("Category", backref="predictive_insights")
    budget = relationship("Budget", backref="predictive_insights")
    
    def __repr__(self) -> str:
        """String representation of the insight."""
        return f"<PredictiveInsight(id={self.id}, type={self.insight_type}, severity={self.severity})>"


class SpendingAnomaly(BaseModel):
    """Spending anomaly detection model."""
    
    __tablename__ = "spending_anomalies"
    
    # Foreign keys
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Anomaly details
    anomaly_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Anomaly score (higher = more unusual)",
    )
    anomaly_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type: 'amount', 'frequency', 'category', 'merchant'",
    )
    
    # Expected vs actual
    expected_range_min: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    expected_range_max: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    actual_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    
    # Detection metadata
    detection_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Algorithm used for detection",
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Detection confidence (0-1)",
    )
    
    # Context
    context_data: Mapped[Optional[Dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional context about the anomaly",
    )
    
    # User feedback
    is_confirmed: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        comment="User confirmed as unusual",
    )
    user_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Relationships
    user = relationship("User", backref="spending_anomalies")
    transaction = relationship("Transaction", backref="anomaly_flags")
    
    def __repr__(self) -> str:
        """String representation of the anomaly."""
        return f"<SpendingAnomaly(id={self.id}, score={self.anomaly_score}, type={self.anomaly_type})>"