"""
API endpoints for transaction management.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_active_user, get_db
from app.models.user import User
from app.models.transaction import TransactionType
from app.schemas.transaction import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    CSVImportRequest,
    CSVImportResponse,
    SpendingByCategoryResponse,
    SpendingTrendResponse,
    TransactionCreate,
    TransactionFilter,
    TransactionResponse,
    TransactionRuleCreate,
    TransactionRuleResponse,
    TransactionRuleUpdate,
    TransactionUpdate,
)
from app.services.transaction import (
    CategoryService,
    TransactionRuleService,
    TransactionService,
)

router = APIRouter()


# Transaction endpoints
@router.post("/transactions", response_model=TransactionResponse)
def create_transaction(
    transaction: TransactionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Create a new transaction.
    """
    try:
        db_transaction = TransactionService.create_transaction(
            db=db,
            user_id=current_user.id,
            transaction_data=transaction,
        )
        return db_transaction
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/transactions", response_model=dict)
def get_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category_ids: Optional[List[int]] = Query(None),
    transaction_type: Optional[TransactionType] = None,
    min_amount: Optional[float] = Query(None, ge=0),
    max_amount: Optional[float] = Query(None, ge=0),
    search_text: Optional[str] = None,
    tags: Optional[List[str]] = Query(None),
    account_names: Optional[List[str]] = Query(None),
    is_recurring: Optional[bool] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get transactions with optional filters.
    """
    # Create filter object
    filters = TransactionFilter(
        start_date=start_date,
        end_date=end_date,
        category_ids=category_ids,
        transaction_type=transaction_type,
        min_amount=min_amount,
        max_amount=max_amount,
        search_text=search_text,
        tags=tags,
        account_names=account_names,
        is_recurring=is_recurring,
    )
    
    transactions, total = TransactionService.get_transactions(
        db=db,
        user_id=current_user.id,
        filters=filters,
        skip=skip,
        limit=limit,
    )
    
    return {
        "transactions": transactions,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/transactions/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get a specific transaction.
    """
    from app.models.transaction import Transaction
    
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id,
    ).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    return transaction


@router.patch("/transactions/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: int,
    transaction_update: TransactionUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update a transaction.
    """
    try:
        db_transaction = TransactionService.update_transaction(
            db=db,
            user_id=current_user.id,
            transaction_id=transaction_id,
            transaction_data=transaction_update,
        )
        return db_transaction
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/transactions/{transaction_id}")
def delete_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Delete a transaction.
    """
    success = TransactionService.delete_transaction(
        db=db,
        user_id=current_user.id,
        transaction_id=transaction_id,
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    return {"message": "Transaction deleted successfully"}


# Category endpoints
@router.post("/categories", response_model=CategoryResponse)
def create_category(
    category: CategoryCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Create a new category.
    """
    try:
        db_category = CategoryService.create_category(
            db=db,
            user_id=current_user.id,
            category_data=category,
        )
        return db_category
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories", response_model=List[CategoryResponse])
def get_categories(
    include_inactive: bool = Query(False),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get all categories for the current user.
    """
    categories = CategoryService.get_categories(
        db=db,
        user_id=current_user.id,
        include_inactive=include_inactive,
    )
    return categories


@router.get("/categories/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get a specific category.
    """
    from app.models.transaction import Category
    
    category = db.query(Category).filter(
        Category.id == category_id,
        Category.user_id == current_user.id,
    ).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    return category


@router.patch("/categories/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    category_update: CategoryUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update a category.
    """
    try:
        db_category = CategoryService.update_category(
            db=db,
            user_id=current_user.id,
            category_id=category_id,
            category_data=category_update,
        )
        return db_category
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/categories/{category_id}")
def delete_category(
    category_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Delete a category.
    """
    try:
        success = CategoryService.delete_category(
            db=db,
            user_id=current_user.id,
            category_id=category_id,
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Category not found")
        
        return {"message": "Category deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/categories/defaults", response_model=List[CategoryResponse])
def create_default_categories(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Create default categories for the current user.
    """
    try:
        categories = CategoryService.create_default_categories(
            db=db,
            user_id=current_user.id,
        )
        return categories
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Transaction Rule endpoints
@router.post("/rules", response_model=TransactionRuleResponse)
def create_rule(
    rule: TransactionRuleCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Create a new transaction rule.
    """
    try:
        db_rule = TransactionRuleService.create_rule(
            db=db,
            user_id=current_user.id,
            rule_data=rule,
        )
        return db_rule
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rules", response_model=List[TransactionRuleResponse])
def get_rules(
    include_inactive: bool = Query(False),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get all transaction rules for the current user.
    """
    rules = TransactionRuleService.get_rules(
        db=db,
        user_id=current_user.id,
        include_inactive=include_inactive,
    )
    return rules


@router.get("/rules/{rule_id}", response_model=TransactionRuleResponse)
def get_rule(
    rule_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get a specific transaction rule.
    """
    from app.models.transaction import TransactionRule
    
    rule = db.query(TransactionRule).filter(
        TransactionRule.id == rule_id,
        TransactionRule.user_id == current_user.id,
    ).first()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return rule


@router.patch("/rules/{rule_id}", response_model=TransactionRuleResponse)
def update_rule(
    rule_id: int,
    rule_update: TransactionRuleUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update a transaction rule.
    """
    try:
        db_rule = TransactionRuleService.update_rule(
            db=db,
            user_id=current_user.id,
            rule_id=rule_id,
            rule_data=rule_update,
        )
        return db_rule
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/rules/{rule_id}")
def delete_rule(
    rule_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Delete a transaction rule.
    """
    success = TransactionRuleService.delete_rule(
        db=db,
        user_id=current_user.id,
        rule_id=rule_id,
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return {"message": "Rule deleted successfully"}


@router.post("/rules/apply", response_model=dict)
def apply_rules_to_existing(
    override_existing: bool = Query(False, description="Override existing categories"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Apply transaction rules to existing transactions.
    """
    try:
        results = TransactionRuleService.apply_rules_to_existing(
            db=db,
            user_id=current_user.id,
            override_existing=override_existing,
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# CSV Import endpoint
@router.post("/transactions/import", response_model=CSVImportResponse)
async def import_transactions_csv(
    file: UploadFile = File(...),
    date_format: str = Form("%Y-%m-%d"),
    date_column: str = Form("Date"),
    amount_column: str = Form("Amount"),
    description_column: str = Form("Description"),
    merchant_column: Optional[str] = Form(None),
    category_column: Optional[str] = Form(None),
    account_column: Optional[str] = Form(None),
    tags_column: Optional[str] = Form(None),
    skip_duplicates: bool = Form(True),
    auto_categorize: bool = Form(True),
    default_account: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Import transactions from a CSV file.
    """
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
    
    # Read file content
    try:
        content = await file.read()
        file_content = content.decode('utf-8')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")
    
    # Create import config
    import_config = CSVImportRequest(
        date_format=date_format,
        date_column=date_column,
        amount_column=amount_column,
        description_column=description_column,
        merchant_column=merchant_column,
        category_column=category_column,
        account_column=account_column,
        tags_column=tags_column,
        skip_duplicates=skip_duplicates,
        auto_categorize=auto_categorize,
        default_account=default_account,
    )
    
    try:
        results = TransactionService.import_csv(
            db=db,
            user_id=current_user.id,
            file_content=file_content,
            import_config=import_config,
        )
        return CSVImportResponse(**results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Analytics endpoints
@router.get("/analytics/spending-by-category", response_model=List[SpendingByCategoryResponse])
def get_spending_by_category(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    transaction_type: Optional[TransactionType] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get spending analytics grouped by category.
    """
    from datetime import datetime
    from decimal import Decimal
    from sqlalchemy import func
    
    from app.models.transaction import Category, Transaction
    
    # Build query
    query = db.query(
        Transaction.category_id,
        Category.name.label("category_name"),
        func.sum(Transaction.amount).label("total_amount"),
        func.count(Transaction.id).label("transaction_count"),
        Category.budget_amount,
    ).join(
        Category,
        Transaction.category_id == Category.id,
    ).filter(
        Transaction.user_id == current_user.id,
    )
    
    # Apply filters
    if start_date:
        query = query.filter(Transaction.transaction_date >= start_date)
    if end_date:
        query = query.filter(Transaction.transaction_date <= end_date)
    if transaction_type:
        query = query.filter(Transaction.transaction_type == transaction_type)
    
    # Group by category
    results = query.group_by(
        Transaction.category_id,
        Category.name,
        Category.budget_amount,
    ).all()
    
    # Calculate total for percentages
    total_amount = sum(r.total_amount for r in results)
    
    # Format response
    response = []
    for r in results:
        percentage = float(r.total_amount / total_amount * 100) if total_amount > 0 else 0
        budget_percentage = None
        if r.budget_amount and r.budget_amount > 0:
            budget_percentage = float(r.total_amount / r.budget_amount * 100)
        
        response.append(SpendingByCategoryResponse(
            category_id=r.category_id,
            category_name=r.category_name,
            total_amount=r.total_amount,
            transaction_count=r.transaction_count,
            percentage=round(percentage, 2),
            budget_amount=r.budget_amount,
            budget_percentage=round(budget_percentage, 2) if budget_percentage else None,
        ))
    
    # Sort by total amount descending
    response.sort(key=lambda x: x.total_amount, reverse=True)
    
    return response


@router.get("/analytics/spending-trend", response_model=List[SpendingTrendResponse])
def get_spending_trend(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    group_by: str = Query("month", regex="^(day|week|month|year)$"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get spending trend over time.
    """
    from datetime import datetime
    from decimal import Decimal
    from sqlalchemy import extract, func
    
    from app.models.transaction import Transaction
    
    # Base query
    base_query = db.query(Transaction).filter(
        Transaction.user_id == current_user.id,
    )
    
    # Apply date filters
    if start_date:
        base_query = base_query.filter(Transaction.transaction_date >= start_date)
    if end_date:
        base_query = base_query.filter(Transaction.transaction_date <= end_date)
    
    # Determine grouping
    if group_by == "day":
        date_format = "%Y-%m-%d"
        group_clause = [
            extract('year', Transaction.transaction_date),
            extract('month', Transaction.transaction_date),
            extract('day', Transaction.transaction_date),
        ]
    elif group_by == "week":
        date_format = "%Y-W%U"
        group_clause = [
            extract('year', Transaction.transaction_date),
            extract('week', Transaction.transaction_date),
        ]
    elif group_by == "month":
        date_format = "%Y-%m"
        group_clause = [
            extract('year', Transaction.transaction_date),
            extract('month', Transaction.transaction_date),
        ]
    else:  # year
        date_format = "%Y"
        group_clause = [extract('year', Transaction.transaction_date)]
    
    # Get income and expense totals by period
    results = []
    
    # Query for each transaction type
    for transaction_type in [TransactionType.INCOME, TransactionType.EXPENSE]:
        type_query = base_query.filter(
            Transaction.transaction_type == transaction_type
        ).with_entities(
            *group_clause,
            func.sum(Transaction.amount).label("total_amount"),
        ).group_by(*group_clause)
        
        for row in type_query.all():
            # Construct period string based on grouping
            if group_by == "day":
                period = f"{row[0]}-{row[1]:02d}-{row[2]:02d}"
            elif group_by == "week":
                period = f"{row[0]}-W{row[1]:02d}"
            elif group_by == "month":
                period = f"{row[0]}-{row[1]:02d}"
            else:  # year
                period = str(row[0])
            
            # Find or create period entry
            period_entry = next((r for r in results if r["period"] == period), None)
            if not period_entry:
                period_entry = {
                    "period": period,
                    "income": Decimal(0),
                    "expenses": Decimal(0),
                }
                results.append(period_entry)
            
            # Update amounts
            if transaction_type == TransactionType.INCOME:
                period_entry["income"] = row[-1] or Decimal(0)
            else:
                period_entry["expenses"] = row[-1] or Decimal(0)
    
    # Calculate net and format response
    response = []
    for r in results:
        # Get category breakdown for this period
        category_breakdown = get_spending_by_category(
            start_date=r["period"] if group_by != "year" else f"{r['period']}-01-01",
            end_date=None,  # Will get all transactions in the period
            transaction_type=TransactionType.EXPENSE,
            current_user=current_user,
            db=db,
        )
        
        response.append(SpendingTrendResponse(
            period=r["period"],
            income=r["income"],
            expenses=r["expenses"],
            net=r["income"] - r["expenses"],
            category_breakdown=category_breakdown[:5],  # Top 5 categories
        ))
    
    # Sort by period
    response.sort(key=lambda x: x.period)
    
    return response