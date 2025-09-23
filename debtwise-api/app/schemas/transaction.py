"""
Schemas for transaction and category operations.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.transaction import TransactionType


# Category Schemas
class CategoryBase(BaseModel):
    """Base category schema."""
    
    name: str = Field(..., max_length=100, description="Category name")
    parent_id: Optional[int] = Field(None, description="Parent category ID for subcategories")
    icon: Optional[str] = Field(None, max_length=50, description="Icon name or emoji")
    color: Optional[str] = Field(None, max_length=7, pattern="^#[0-9A-Fa-f]{6}$", description="Hex color code")
    transaction_type: TransactionType = Field(TransactionType.EXPENSE, description="Type of transactions")
    budget_amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2, description="Monthly budget amount")
    is_active: bool = Field(True, description="Whether the category is active")


class CategoryCreate(CategoryBase):
    """Schema for creating a category."""
    pass


class CategoryUpdate(BaseModel):
    """Schema for updating a category."""
    
    name: Optional[str] = Field(None, max_length=100)
    parent_id: Optional[int] = None
    icon: Optional[str] = Field(None, max_length=50)
    color: Optional[str] = Field(None, max_length=7, pattern="^#[0-9A-Fa-f]{6}$")
    transaction_type: Optional[TransactionType] = None
    budget_amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    is_active: Optional[bool] = None


class CategoryResponse(CategoryBase):
    """Schema for category response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    
    # Optional nested data
    subcategories: Optional[List["CategoryResponse"]] = None
    transaction_count: Optional[int] = None
    current_month_spending: Optional[Decimal] = None


# Transaction Schemas
class TransactionBase(BaseModel):
    """Base transaction schema."""
    
    amount: Decimal = Field(..., gt=0, decimal_places=2, description="Transaction amount")
    transaction_date: date = Field(..., description="Date of the transaction")
    description: str = Field(..., max_length=500, description="Transaction description")
    transaction_type: TransactionType = Field(..., description="Type of transaction")
    category_id: Optional[int] = Field(None, description="Category ID")
    account_name: Optional[str] = Field(None, max_length=100, description="Account name")
    merchant: Optional[str] = Field(None, max_length=255, description="Merchant name")
    notes: Optional[str] = Field(None, description="Additional notes")
    tags: Optional[str] = Field(None, max_length=500, description="Comma-separated tags")
    is_recurring: bool = Field(False, description="Whether this is a recurring transaction")
    
    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: Optional[str]) -> Optional[str]:
        """Validate and clean tags."""
        if v:
            # Clean and deduplicate tags
            tags = [tag.strip() for tag in v.split(",") if tag.strip()]
            return ",".join(sorted(set(tags)))
        return v


class TransactionCreate(TransactionBase):
    """Schema for creating a transaction."""
    
    import_id: Optional[str] = Field(None, max_length=100, description="Unique ID from import source")


class TransactionUpdate(BaseModel):
    """Schema for updating a transaction."""
    
    amount: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    transaction_date: Optional[date] = None
    description: Optional[str] = Field(None, max_length=500)
    transaction_type: Optional[TransactionType] = None
    category_id: Optional[int] = None
    account_name: Optional[str] = Field(None, max_length=100)
    merchant: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None
    tags: Optional[str] = Field(None, max_length=500)
    is_recurring: Optional[bool] = None


class TransactionResponse(TransactionBase):
    """Schema for transaction response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    import_id: Optional[str] = None
    
    # Optional nested data
    category: Optional[CategoryResponse] = None


class TransactionFilter(BaseModel):
    """Schema for filtering transactions."""
    
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    category_ids: Optional[List[int]] = None
    transaction_type: Optional[TransactionType] = None
    min_amount: Optional[Decimal] = Field(None, ge=0)
    max_amount: Optional[Decimal] = Field(None, ge=0)
    search_text: Optional[str] = Field(None, description="Search in description and merchant")
    tags: Optional[List[str]] = None
    account_names: Optional[List[str]] = None
    is_recurring: Optional[bool] = None


# Transaction Rule Schemas
class TransactionRuleBase(BaseModel):
    """Base transaction rule schema."""
    
    name: str = Field(..., max_length=100, description="Rule name")
    category_id: int = Field(..., description="Category to assign")
    description_pattern: Optional[str] = Field(None, max_length=500, description="Regex pattern for description")
    merchant_pattern: Optional[str] = Field(None, max_length=500, description="Regex pattern for merchant")
    amount_min: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    amount_max: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    transaction_type: Optional[TransactionType] = None
    priority: int = Field(0, ge=0, le=1000, description="Rule priority (0-1000)")
    is_active: bool = Field(True)


class TransactionRuleCreate(TransactionRuleBase):
    """Schema for creating a transaction rule."""
    pass


class TransactionRuleUpdate(BaseModel):
    """Schema for updating a transaction rule."""
    
    name: Optional[str] = Field(None, max_length=100)
    category_id: Optional[int] = None
    description_pattern: Optional[str] = Field(None, max_length=500)
    merchant_pattern: Optional[str] = Field(None, max_length=500)
    amount_min: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    amount_max: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    transaction_type: Optional[TransactionType] = None
    priority: Optional[int] = Field(None, ge=0, le=1000)
    is_active: Optional[bool] = None


class TransactionRuleResponse(TransactionRuleBase):
    """Schema for transaction rule response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    
    # Optional nested data
    category: Optional[CategoryResponse] = None
    matched_count: Optional[int] = None


# CSV Import Schemas
class CSVImportRequest(BaseModel):
    """Schema for CSV import request."""
    
    date_format: str = Field("%Y-%m-%d", description="Date format in the CSV")
    date_column: str = Field("Date", description="Column name for transaction date")
    amount_column: str = Field("Amount", description="Column name for amount")
    description_column: str = Field("Description", description="Column name for description")
    merchant_column: Optional[str] = Field(None, description="Column name for merchant")
    category_column: Optional[str] = Field(None, description="Column name for category")
    account_column: Optional[str] = Field(None, description="Column name for account")
    tags_column: Optional[str] = Field(None, description="Column name for tags")
    
    # Import options
    skip_duplicates: bool = Field(True, description="Skip transactions with duplicate import_ids")
    auto_categorize: bool = Field(True, description="Apply transaction rules for categorization")
    default_account: Optional[str] = Field(None, description="Default account name if not in CSV")


class CSVImportResponse(BaseModel):
    """Schema for CSV import response."""
    
    total_rows: int = Field(..., description="Total rows processed")
    imported_count: int = Field(..., description="Number of transactions imported")
    skipped_count: int = Field(..., description="Number of transactions skipped")
    error_count: int = Field(..., description="Number of rows with errors")
    errors: List[str] = Field(default_factory=list, description="List of error messages")
    imported_transactions: List[TransactionResponse] = Field(default_factory=list)


# Analytics Schemas
class SpendingByCategoryResponse(BaseModel):
    """Schema for spending by category analytics."""
    
    category_id: int
    category_name: str
    total_amount: Decimal
    transaction_count: int
    percentage: float
    budget_amount: Optional[Decimal] = None
    budget_percentage: Optional[float] = None


class SpendingTrendResponse(BaseModel):
    """Schema for spending trend analytics."""
    
    period: str  # e.g., "2024-01"
    income: Decimal
    expenses: Decimal
    net: Decimal
    category_breakdown: List[SpendingByCategoryResponse]