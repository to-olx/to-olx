"""
User database model.
"""

from typing import Optional

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class User(BaseModel):
    """User model for authentication and profile management."""
    
    __tablename__ = "users"
    
    # Authentication fields
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Profile fields
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Status fields
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Additional fields
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    # Relationships
    debts = relationship(
        "Debt",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    debt_payments = relationship(
        "DebtPayment",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        """String representation of the user."""
        return f"<User(id={self.id}, email={self.email}, username={self.username})>"