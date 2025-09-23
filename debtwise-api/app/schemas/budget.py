"""
Schemas for budget operations.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.budget import BudgetPeriodType


# Budget Schemas
class BudgetBase(BaseModel):
    """Base budget schema."""
    
    name: str = Field(..., max_length=100, description="Budget name")
    description: Optional[str] = Field(None, max_length=500, description="Budget description")
    category_id: Optional[int] = Field(None, description="Category ID (null for total budget)")
    period_type: BudgetPeriodType = Field(BudgetPeriodType.MONTHLY, description="Budget period type")
    start_date: date = Field(..., description="Start date of the first budget period")
    amount: Decimal = Field(..., gt=0, decimal_places=2, description="Budget amount per period")
    allow_rollover: bool = Field(False, description="Whether unused budget rolls over")
    max_rollover_periods: Optional[int] = Field(None, ge=1, description="Max periods for rollover")
    max_rollover_amount: Optional[Decimal] = Field(None, gt=0, decimal_places=2, description="Max rollover amount")
    is_active: bool = Field(True, description="Whether the budget is active")
    
    @field_validator("max_rollover_periods", "max_rollover_amount")
    @classmethod
    def validate_rollover_settings(cls, v, values):
        """Validate rollover settings are only set when rollover is allowed."""
        if v is not None and values.data.get("allow_rollover") is False:
            raise ValueError("Rollover settings can only be set when allow_rollover is True")
        return v


class BudgetCreate(BudgetBase):
    """Schema for creating a budget."""
    
    # Optional: create alerts at the same time
    alerts: Optional[List["BudgetAlertCreate"]] = Field(None, description="Budget alerts to create")


class BudgetUpdate(BaseModel):
    """Schema for updating a budget."""
    
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    amount: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    allow_rollover: Optional[bool] = None
    max_rollover_periods: Optional[int] = Field(None, ge=1)
    max_rollover_amount: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    is_active: Optional[bool] = None


class BudgetResponse(BudgetBase):
    """Schema for budget response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    
    # Optional nested data
    current_period: Optional["BudgetPeriodResponse"] = None
    alerts: Optional[List["BudgetAlertResponse"]] = None


# Budget Period Schemas
class BudgetPeriodBase(BaseModel):
    """Base budget period schema."""
    
    start_date: date
    end_date: date
    base_amount: Decimal = Field(..., decimal_places=2)
    rollover_amount: Decimal = Field(0, decimal_places=2)
    total_amount: Decimal = Field(..., decimal_places=2)
    spent_amount: Decimal = Field(0, decimal_places=2)
    remaining_amount: Decimal = Field(..., decimal_places=2)
    is_closed: bool = Field(False)


class BudgetPeriodResponse(BudgetPeriodBase):
    """Schema for budget period response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    budget_id: int
    created_at: datetime
    updated_at: datetime
    
    # Calculated fields
    percentage_used: Optional[float] = None
    percentage_remaining: Optional[float] = None


# Budget Alert Schemas
class BudgetAlertBase(BaseModel):
    """Base budget alert schema."""
    
    threshold_percentage: int = Field(..., ge=1, le=100, description="Alert threshold (1-100%)")
    alert_message: Optional[str] = Field(None, max_length=500, description="Custom alert message")
    is_enabled: bool = Field(True)
    send_email: bool = Field(True)
    send_push: bool = Field(False)


class BudgetAlertCreate(BudgetAlertBase):
    """Schema for creating a budget alert."""
    pass


class BudgetAlertUpdate(BaseModel):
    """Schema for updating a budget alert."""
    
    threshold_percentage: Optional[int] = Field(None, ge=1, le=100)
    alert_message: Optional[str] = Field(None, max_length=500)
    is_enabled: Optional[bool] = None
    send_email: Optional[bool] = None
    send_push: Optional[bool] = None


class BudgetAlertResponse(BudgetAlertBase):
    """Schema for budget alert response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    budget_id: int
    created_at: datetime
    updated_at: datetime


# Budget Summary Schemas
class BudgetSummaryResponse(BaseModel):
    """Schema for budget summary response."""
    
    budget_id: int
    budget_name: str
    category_id: Optional[int]
    category_name: Optional[str]
    period_type: BudgetPeriodType
    current_period: BudgetPeriodResponse
    
    # Summary statistics
    total_budgeted: Decimal
    total_spent: Decimal
    total_remaining: Decimal
    percentage_used: float
    
    # Trend data
    average_monthly_spending: Optional[Decimal] = None
    projected_end_of_period: Optional[Decimal] = None
    days_remaining: int
    
    # Alert status
    active_alerts: List[str] = Field(default_factory=list)
    is_over_budget: bool = False


class BudgetOverviewResponse(BaseModel):
    """Schema for overall budget overview."""
    
    total_budgets: int
    active_budgets: int
    
    # Current period totals
    total_budgeted_amount: Decimal
    total_spent_amount: Decimal
    total_remaining_amount: Decimal
    overall_percentage_used: float
    
    # Individual budget summaries
    budgets: List[BudgetSummaryResponse]
    
    # Categories without budgets
    unbudgeted_spending: Optional[Decimal] = None
    unbudgeted_categories: Optional[List[str]] = None


class BudgetRolloverRequest(BaseModel):
    """Schema for processing budget rollovers."""
    
    budget_id: int = Field(..., description="Budget ID to process rollover for")
    period_date: Optional[date] = Field(None, description="Date within the period to process (defaults to current)")


class BudgetRolloverResponse(BaseModel):
    """Schema for budget rollover response."""
    
    budget_id: int
    periods_processed: int
    
    # Rollover details
    previous_period: Optional[BudgetPeriodResponse] = None
    new_period: BudgetPeriodResponse
    rollover_amount: Decimal
    
    # Status
    success: bool
    message: str