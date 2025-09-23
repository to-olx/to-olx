"""
Schemas for predictive insights and forecasts.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.insight import InsightSeverity, InsightStatus, InsightType


# Spending Forecast Schemas
class SpendingForecastBase(BaseModel):
    """Base spending forecast schema."""
    
    category_id: Optional[int] = Field(None, description="Category ID (null for overall)")
    start_date: date = Field(..., description="Forecast start date")
    end_date: date = Field(..., description="Forecast end date")
    

class SpendingForecastResponse(BaseModel):
    """Schema for spending forecast response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    category_id: Optional[int]
    category_name: Optional[str] = None
    start_date: date
    end_date: date
    
    # Predictions
    predicted_amount: Decimal
    confidence_level: float
    prediction_std_dev: Optional[Decimal]
    lower_bound: Optional[Decimal]
    upper_bound: Optional[Decimal]
    
    # Model info
    model_type: str
    model_params: Optional[Dict[str, Any]]
    
    # Comparison
    historical_avg: Decimal
    trend_direction: Optional[str]
    trend_percentage: Optional[float]
    
    # Actuals (if available)
    actual_amount: Optional[Decimal]
    accuracy_score: Optional[float]
    
    created_at: datetime
    updated_at: datetime


# Cashflow Forecast Schemas  
class CashflowForecastBase(BaseModel):
    """Base cashflow forecast schema."""
    
    forecast_date: date = Field(..., description="Date to forecast")
    account_name: Optional[str] = Field(None, description="Account name (null for all)")


class CashflowForecastResponse(BaseModel):
    """Schema for cashflow forecast response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    forecast_date: date
    account_name: Optional[str]
    
    # Current state
    current_balance: Decimal
    
    # Predictions
    predicted_income: Decimal
    predicted_expenses: Decimal
    predicted_balance: Decimal
    
    # Risk indicators
    minimum_balance: Optional[Decimal]
    low_balance_date: Optional[date]
    overdraft_risk: float
    
    # Scheduled transactions
    scheduled_bills: Optional[List[Dict[str, Any]]]
    scheduled_income: Optional[List[Dict[str, Any]]]
    
    created_at: datetime
    updated_at: datetime


# Predictive Insight Schemas
class PredictiveInsightBase(BaseModel):
    """Base predictive insight schema."""
    
    insight_type: InsightType
    title: str = Field(..., max_length=200)
    description: str
    severity: InsightSeverity = InsightSeverity.INFO
    
    # Related entities
    category_id: Optional[int] = None
    budget_id: Optional[int] = None
    
    # Recommendation
    recommendation: Optional[str] = None
    action_items: Optional[List[str]] = None


class PredictiveInsightCreate(PredictiveInsightBase):
    """Schema for creating a predictive insight."""
    
    insight_data: Dict[str, Any] = Field(default_factory=dict)
    transaction_ids: Optional[List[int]] = None
    potential_savings: Optional[Decimal] = None
    risk_score: Optional[float] = Field(None, ge=0, le=1)
    valid_until: Optional[date] = None


class PredictiveInsightUpdate(BaseModel):
    """Schema for updating a predictive insight."""
    
    status: Optional[InsightStatus] = None
    acknowledged_at: Optional[date] = None
    dismissed_at: Optional[date] = None


class PredictiveInsightResponse(PredictiveInsightBase):
    """Schema for predictive insight response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    status: InsightStatus
    
    # Data
    insight_data: Dict[str, Any]
    transaction_ids: Optional[List[int]]
    
    # Impact
    potential_savings: Optional[Decimal]
    risk_score: Optional[float]
    
    # Validity
    valid_until: Optional[date]
    acknowledged_at: Optional[date]
    dismissed_at: Optional[date]
    
    created_at: datetime
    updated_at: datetime
    
    # Related names
    category_name: Optional[str] = None
    budget_name: Optional[str] = None


# Spending Anomaly Schemas
class SpendingAnomalyResponse(BaseModel):
    """Schema for spending anomaly response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    transaction_id: int
    
    # Anomaly details
    anomaly_score: float
    anomaly_type: str
    
    # Expected vs actual
    expected_range_min: Optional[Decimal]
    expected_range_max: Optional[Decimal]
    actual_amount: Decimal
    
    # Detection
    detection_method: str
    confidence: float
    context_data: Optional[Dict[str, Any]]
    
    # User feedback
    is_confirmed: Optional[bool]
    user_notes: Optional[str]
    
    created_at: datetime
    
    # Transaction details
    transaction_description: Optional[str] = None
    transaction_date: Optional[date] = None
    merchant: Optional[str] = None
    category_name: Optional[str] = None


# Dashboard Insights Schema
class DashboardInsightsResponse(BaseModel):
    """Schema for dashboard insights overview."""
    
    # Key metrics
    current_month_spending: Decimal
    predicted_month_end: Decimal
    spending_trend: str  # 'up', 'down', 'stable'
    trend_percentage: float
    
    # Budget health
    budgets_at_risk: int
    total_budget_utilization: float
    projected_overages: List[Dict[str, Any]]
    
    # Anomalies
    recent_anomalies: List[SpendingAnomalyResponse]
    anomaly_count: int
    
    # Top insights
    active_insights: List[PredictiveInsightResponse]
    critical_alerts: int
    warning_alerts: int
    
    # Savings opportunities
    total_potential_savings: Decimal
    top_savings_opportunities: List[Dict[str, Any]]
    
    # Cash flow
    current_balance: Decimal
    predicted_7_day_balance: Decimal
    predicted_30_day_balance: Decimal
    low_balance_warning: Optional[Dict[str, Any]]


# Forecast Request Schemas
class GenerateForecastRequest(BaseModel):
    """Schema for generating forecasts."""
    
    forecast_type: str = Field(..., description="Type: 'spending', 'cashflow', 'all'")
    time_period: str = Field("30d", description="Period: '7d', '30d', '90d', 'custom'")
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    category_ids: Optional[List[int]] = Field(None, description="Specific categories to forecast")
    
    @field_validator("time_period")
    @classmethod
    def validate_time_period(cls, v, values):
        """Validate time period or custom dates."""
        if v == "custom" and not (values.data.get("start_date") and values.data.get("end_date")):
            raise ValueError("start_date and end_date required for custom time period")
        return v


# Insight Filter Schemas
class InsightFilterParams(BaseModel):
    """Schema for filtering insights."""
    
    insight_type: Optional[InsightType] = None
    severity: Optional[InsightSeverity] = None
    status: Optional[InsightStatus] = None
    category_id: Optional[int] = None
    budget_id: Optional[int] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)