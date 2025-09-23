"""Pydantic schemas package"""

from app.schemas.auth import Token, TokenData
from app.schemas.debt import (
    DebtCreate,
    DebtPaymentCreate,
    DebtPaymentResponse,
    DebtPayoffProjection,
    DebtResponse,
    DebtSummary,
    DebtUpdate,
    InterestCalculatorRequest,
    InterestCalculatorResponse,
    PayoffPlanRequest,
    PayoffPlanResponse,
    PayoffStrategy,
)
from app.schemas.user import User, UserCreate, UserInDB, UserUpdate

__all__ = [
    # Auth schemas
    "Token",
    "TokenData",
    # User schemas
    "User",
    "UserCreate",
    "UserInDB",
    "UserUpdate",
    # Debt schemas
    "DebtCreate",
    "DebtUpdate",
    "DebtResponse",
    "DebtPaymentCreate",
    "DebtPaymentResponse",
    "DebtSummary",
    "PayoffStrategy",
    "PayoffPlanRequest",
    "PayoffPlanResponse",
    "DebtPayoffProjection",
    "InterestCalculatorRequest",
    "InterestCalculatorResponse",
]