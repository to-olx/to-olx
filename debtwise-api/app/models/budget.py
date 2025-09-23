"""
Budget models for tracking spending limits and rollovers.
"""

from datetime import date
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    Enum,
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class BudgetPeriodType(str, PyEnum):
    """Budget period type enumeration."""
    
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class Budget(BaseModel):
    """Budget model for tracking spending limits across periods."""
    
    __tablename__ = "budgets"
    
    # Foreign keys
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="If null, this is a total budget across all categories",
    )
    
    # Budget information
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Period configuration
    period_type: Mapped[BudgetPeriodType] = mapped_column(
        Enum(BudgetPeriodType),
        nullable=False,
        default=BudgetPeriodType.MONTHLY,
    )
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Start date of the first budget period",
    )
    
    # Budget amounts
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Budget amount per period",
    )
    
    # Rollover configuration
    allow_rollover: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether unused budget rolls over to next period",
    )
    max_rollover_periods: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum number of periods to accumulate rollover (null = unlimited)",
    )
    max_rollover_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Maximum rollover amount (null = unlimited)",
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    
    # Relationships
    user = relationship("User", backref="budgets")
    category = relationship("Category", backref="budgets")
    budget_periods = relationship(
        "BudgetPeriod",
        back_populates="budget",
        cascade="all, delete-orphan",
    )
    
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="_user_budget_uc"),
    )
    
    def __repr__(self) -> str:
        """String representation of the budget."""
        return f"<Budget(id={self.id}, name='{self.name}', amount={self.amount})>"


class BudgetPeriod(BaseModel):
    """Budget period model for tracking spending within specific time periods."""
    
    __tablename__ = "budget_periods"
    
    # Foreign keys
    budget_id: Mapped[int] = mapped_column(
        ForeignKey("budgets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Period dates
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    
    # Budget amounts
    base_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Base budget amount for this period",
    )
    rollover_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=0,
        comment="Amount rolled over from previous periods",
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Total budget (base + rollover)",
    )
    
    # Actual spending (cached for performance)
    spent_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=0,
        comment="Actual amount spent in this period",
    )
    
    # Calculated fields
    remaining_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=0,
        comment="Remaining budget (total - spent)",
    )
    
    # Period status
    is_closed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this period is closed for changes",
    )
    
    # Relationships
    budget = relationship("Budget", back_populates="budget_periods")
    
    __table_args__ = (
        UniqueConstraint("budget_id", "start_date", name="_budget_period_uc"),
    )
    
    def __repr__(self) -> str:
        """String representation of the budget period."""
        return f"<BudgetPeriod(id={self.id}, start={self.start_date}, end={self.end_date})>"


class BudgetAlert(BaseModel):
    """Budget alert model for notifying users about budget status."""
    
    __tablename__ = "budget_alerts"
    
    # Foreign keys
    budget_id: Mapped[int] = mapped_column(
        ForeignKey("budgets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Alert configuration
    threshold_percentage: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Percentage of budget spent to trigger alert (e.g., 80 for 80%)",
    )
    alert_message: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    
    # Alert settings
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    send_email: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    send_push: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    
    # Relationships
    budget = relationship("Budget", backref="alerts")
    
    __table_args__ = (
        UniqueConstraint("budget_id", "threshold_percentage", name="_budget_alert_uc"),
    )
    
    def __repr__(self) -> str:
        """String representation of the budget alert."""
        return f"<BudgetAlert(id={self.id}, threshold={self.threshold_percentage}%)>"