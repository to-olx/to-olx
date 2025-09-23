"""
Debt and debt payment models.
"""

from datetime import date
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class DebtType(str, PyEnum):
    """Debt type enumeration."""
    
    CREDIT_CARD = "credit_card"
    PERSONAL_LOAN = "personal_loan"
    STUDENT_LOAN = "student_loan"
    MORTGAGE = "mortgage"
    AUTO_LOAN = "auto_loan"
    MEDICAL_DEBT = "medical_debt"
    OTHER = "other"


class DebtStatus(str, PyEnum):
    """Debt status enumeration."""
    
    ACTIVE = "active"
    PAID_OFF = "paid_off"
    IN_COLLECTIONS = "in_collections"
    WRITTEN_OFF = "written_off"


class Debt(BaseModel):
    """Debt model for tracking user debts."""
    
    __tablename__ = "debts"
    
    # Foreign keys
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Debt information
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    debt_type: Mapped[DebtType] = mapped_column(
        Enum(DebtType),
        nullable=False,
        default=DebtType.OTHER,
    )
    
    # Financial details
    original_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    current_balance: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    interest_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        comment="Annual percentage rate (APR)",
    )
    minimum_payment: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    
    # Dates
    due_date: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="Day of month payment is due (1-31)",
    )
    origination_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    
    # Status
    status: Mapped[DebtStatus] = mapped_column(
        Enum(DebtStatus),
        nullable=False,
        default=DebtStatus.ACTIVE,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    
    # Relationships
    user = relationship("User", back_populates="debts")
    payments = relationship(
        "DebtPayment",
        back_populates="debt",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        """String representation of the debt."""
        return f"<Debt(id={self.id}, name='{self.name}', balance={self.current_balance})>"


class DebtPayment(BaseModel):
    """Debt payment model for tracking payment history."""
    
    __tablename__ = "debt_payments"
    
    # Foreign keys
    debt_id: Mapped[int] = mapped_column(
        ForeignKey("debts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Payment information
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    payment_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    principal_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Amount applied to principal",
    )
    interest_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Amount applied to interest",
    )
    
    # Additional fields
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_extra_payment: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this is an extra payment beyond minimum",
    )
    
    # Relationships
    debt = relationship("Debt", back_populates="payments")
    user = relationship("User", back_populates="debt_payments")
    
    def __repr__(self) -> str:
        """String representation of the payment."""
        return f"<DebtPayment(id={self.id}, debt_id={self.debt_id}, amount={self.amount})>"