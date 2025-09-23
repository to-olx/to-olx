"""
Debt and payment schemas for API requests and responses.
"""

from datetime import date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.debt import DebtStatus, DebtType


class DebtBase(BaseModel):
    """Base debt schema with common fields."""
    
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    debt_type: DebtType = Field(DebtType.OTHER)
    original_amount: Decimal = Field(..., gt=0, decimal_places=2)
    current_balance: Decimal = Field(..., ge=0, decimal_places=2)
    interest_rate: Decimal = Field(..., ge=0, le=100, decimal_places=2)
    minimum_payment: Decimal = Field(..., ge=0, decimal_places=2)
    due_date: Optional[int] = Field(None, ge=1, le=31)
    origination_date: Optional[date] = None
    
    @field_validator("current_balance")
    @classmethod
    def validate_current_balance(cls, v: Decimal, info) -> Decimal:
        """Ensure current balance doesn't exceed original amount."""
        if "original_amount" in info.data and v > info.data["original_amount"]:
            raise ValueError("Current balance cannot exceed original amount")
        return v


class DebtCreate(DebtBase):
    """Schema for creating a new debt."""
    
    pass


class DebtUpdate(BaseModel):
    """Schema for updating an existing debt."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    debt_type: Optional[DebtType] = None
    current_balance: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    interest_rate: Optional[Decimal] = Field(None, ge=0, le=100, decimal_places=2)
    minimum_payment: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    due_date: Optional[int] = Field(None, ge=1, le=31)
    status: Optional[DebtStatus] = None


class DebtResponse(DebtBase):
    """Schema for debt response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    status: DebtStatus
    is_active: bool
    created_at: date
    updated_at: date
    
    # Calculated fields
    total_paid: Optional[Decimal] = Field(None, description="Total amount paid towards debt")
    total_interest_paid: Optional[Decimal] = Field(None, description="Total interest paid")
    months_to_payoff: Optional[int] = Field(None, description="Estimated months to pay off debt")
    next_payment_date: Optional[date] = Field(None, description="Next payment due date")


class DebtPaymentBase(BaseModel):
    """Base payment schema with common fields."""
    
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    payment_date: date
    notes: Optional[str] = Field(None, max_length=500)
    is_extra_payment: bool = Field(False)


class DebtPaymentCreate(DebtPaymentBase):
    """Schema for creating a new payment."""
    
    debt_id: int


class DebtPaymentResponse(DebtPaymentBase):
    """Schema for payment response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    debt_id: int
    user_id: int
    principal_amount: Decimal
    interest_amount: Decimal
    created_at: date
    
    # Additional info
    balance_after_payment: Optional[Decimal] = Field(None, description="Debt balance after this payment")


class DebtSummary(BaseModel):
    """Schema for debt summary statistics."""
    
    total_debt: Decimal = Field(..., description="Total current debt balance")
    total_original_debt: Decimal = Field(..., description="Total original debt amount")
    total_paid: Decimal = Field(..., description="Total amount paid across all debts")
    total_interest_paid: Decimal = Field(..., description="Total interest paid")
    active_debts_count: int = Field(..., description="Number of active debts")
    paid_off_debts_count: int = Field(..., description="Number of paid off debts")
    average_interest_rate: Decimal = Field(..., description="Weighted average interest rate")
    total_minimum_payment: Decimal = Field(..., description="Total minimum monthly payment")
    debts_by_type: dict[DebtType, int] = Field(..., description="Count of debts by type")


class PayoffStrategy(str):
    """Payoff strategy options."""
    
    SNOWBALL = "snowball"  # Pay smallest balance first
    AVALANCHE = "avalanche"  # Pay highest interest rate first
    CUSTOM = "custom"  # User-defined order


class PayoffPlanRequest(BaseModel):
    """Request schema for generating a payoff plan."""
    
    strategy: PayoffStrategy = Field(..., description="Payoff strategy to use")
    extra_monthly_payment: Decimal = Field(0, ge=0, decimal_places=2, description="Extra amount to pay monthly")
    debt_ids: Optional[List[int]] = Field(None, description="Specific debt IDs to include (all if not specified)")


class DebtPayoffProjection(BaseModel):
    """Schema for individual debt payoff projection."""
    
    debt_id: int
    debt_name: str
    current_balance: Decimal
    payoff_order: int
    months_to_payoff: int
    payoff_date: date
    total_interest: Decimal
    total_payments: Decimal


class PayoffPlanResponse(BaseModel):
    """Response schema for payoff plan."""
    
    strategy: PayoffStrategy
    extra_monthly_payment: Decimal
    total_months: int = Field(..., description="Total months to pay off all debts")
    payoff_date: date = Field(..., description="Date when all debts will be paid off")
    total_interest_saved: Decimal = Field(..., description="Interest saved compared to minimum payments")
    time_saved_months: int = Field(..., description="Months saved compared to minimum payments")
    debts: List[DebtPayoffProjection] = Field(..., description="Payoff details for each debt")


class InterestCalculatorRequest(BaseModel):
    """Request schema for interest calculator."""
    
    principal: Decimal = Field(..., gt=0, decimal_places=2)
    interest_rate: Decimal = Field(..., ge=0, le=100, decimal_places=2)
    payment_amount: Decimal = Field(..., gt=0, decimal_places=2)
    
    @field_validator("payment_amount")
    @classmethod
    def validate_payment(cls, v: Decimal, info) -> Decimal:
        """Ensure payment covers at least the interest."""
        if "principal" in info.data and "interest_rate" in info.data:
            monthly_interest = info.data["principal"] * (info.data["interest_rate"] / 100 / 12)
            if v < monthly_interest:
                raise ValueError(f"Payment must be at least ${monthly_interest:.2f} to cover interest")
        return v


class InterestCalculatorResponse(BaseModel):
    """Response schema for interest calculator."""
    
    months_to_payoff: int
    total_payments: Decimal
    total_interest: Decimal
    interest_percentage: Decimal = Field(..., description="Percentage of total payments that is interest")
    monthly_breakdown: List[dict] = Field(..., description="First 12 months payment breakdown")