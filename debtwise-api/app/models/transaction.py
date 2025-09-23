"""
Transaction and category models for spending tracking.
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
    Text,
    UniqueConstraint,
    Enum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class TransactionType(str, PyEnum):
    """Transaction type enumeration."""
    
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"


class Category(BaseModel):
    """Category model for organizing transactions."""
    
    __tablename__ = "categories"
    
    # Foreign keys
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    
    # Category information
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    
    # Category type
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType),
        nullable=False,
        default=TransactionType.EXPENSE,
    )
    
    # Budget information
    budget_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Monthly budget for this category",
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    
    # Relationships
    user = relationship("User", backref="categories")
    parent = relationship("Category", remote_side="Category.id", backref="subcategories")
    transactions = relationship("Transaction", back_populates="category")
    transaction_rules = relationship("TransactionRule", back_populates="category")
    
    __table_args__ = (
        UniqueConstraint("user_id", "name", "parent_id", name="_user_category_uc"),
    )
    
    def __repr__(self) -> str:
        """String representation of the category."""
        return f"<Category(id={self.id}, name='{self.name}', type={self.transaction_type})>"


class Transaction(BaseModel):
    """Transaction model for tracking income and expenses."""
    
    __tablename__ = "transactions"
    
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
    )
    
    # Transaction information
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    transaction_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    
    # Transaction type
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType),
        nullable=False,
    )
    
    # Account information
    account_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Additional fields
    merchant: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Comma-separated tags",
    )
    
    # Import tracking
    import_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Unique identifier from CSV import",
    )
    is_recurring: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    
    # Relationships
    user = relationship("User", backref="transactions")
    category = relationship("Category", back_populates="transactions")
    
    def __repr__(self) -> str:
        """String representation of the transaction."""
        return f"<Transaction(id={self.id}, amount={self.amount}, date={self.transaction_date})>"


class TransactionRule(BaseModel):
    """Transaction rule model for automatic categorization."""
    
    __tablename__ = "transaction_rules"
    
    # Foreign keys
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Rule information
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Pattern matching fields
    description_pattern: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Regex pattern to match transaction description",
    )
    merchant_pattern: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Regex pattern to match merchant name",
    )
    amount_min: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    amount_max: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    
    # Rule conditions
    transaction_type: Mapped[Optional[TransactionType]] = mapped_column(
        Enum(TransactionType),
        nullable=True,
    )
    
    # Rule priority
    priority: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Higher priority rules are applied first",
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    
    # Relationships
    user = relationship("User", backref="transaction_rules")
    category = relationship("Category", back_populates="transaction_rules")
    
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="_user_rule_uc"),
    )
    
    def __repr__(self) -> str:
        """String representation of the rule."""
        return f"<TransactionRule(id={self.id}, name='{self.name}', priority={self.priority})>"