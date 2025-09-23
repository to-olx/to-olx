"""
API endpoints for budget management.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_active_user, get_db
from app.models.user import User
from app.schemas.budget import (
    BudgetAlertCreate,
    BudgetAlertResponse,
    BudgetAlertUpdate,
    BudgetCreate,
    BudgetOverviewResponse,
    BudgetPeriodResponse,
    BudgetResponse,
    BudgetRolloverRequest,
    BudgetRolloverResponse,
    BudgetSummaryResponse,
    BudgetUpdate,
)
from app.services.budget import BudgetService

router = APIRouter()


# Budget endpoints
@router.post("/budgets", response_model=BudgetResponse)
def create_budget(
    budget: BudgetCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Create a new budget.
    """
    try:
        db_budget = BudgetService.create_budget(
            db=db,
            user_id=current_user.id,
            budget_data=budget,
        )
        return db_budget
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/budgets", response_model=List[BudgetResponse])
def get_budgets(
    active_only: bool = Query(True, description="Filter only active budgets"),
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get all budgets for the current user.
    """
    budgets = BudgetService.get_user_budgets(
        db=db,
        user_id=current_user.id,
        active_only=active_only,
        category_id=category_id,
    )
    return budgets


@router.get("/budgets/{budget_id}", response_model=BudgetResponse)
def get_budget(
    budget_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get a specific budget by ID.
    """
    budget = BudgetService.get_budget(
        db=db,
        user_id=current_user.id,
        budget_id=budget_id,
        include_current_period=True,
    )
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    return budget


@router.put("/budgets/{budget_id}", response_model=BudgetResponse)
def update_budget(
    budget_id: int,
    budget: BudgetUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update a budget.
    """
    try:
        db_budget = BudgetService.update_budget(
            db=db,
            user_id=current_user.id,
            budget_id=budget_id,
            budget_data=budget,
        )
        return db_budget
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/budgets/{budget_id}")
def delete_budget(
    budget_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Delete a budget.
    """
    try:
        BudgetService.delete_budget(
            db=db,
            user_id=current_user.id,
            budget_id=budget_id,
        )
        return {"message": "Budget deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Budget period endpoints
@router.get("/budgets/{budget_id}/current-period", response_model=BudgetPeriodResponse)
def get_current_period(
    budget_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get the current period for a budget.
    """
    budget = BudgetService.get_budget(
        db=db,
        user_id=current_user.id,
        budget_id=budget_id,
    )
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    
    current_period = BudgetService.get_current_period(db, budget)
    if not current_period:
        raise HTTPException(status_code=404, detail="No current period found")
    
    return current_period


# Budget summary endpoints
@router.get("/budgets/summary/overview", response_model=BudgetOverviewResponse)
def get_budget_overview(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get an overview of all budgets with summary statistics.
    """
    try:
        summary = BudgetService.get_budget_summary(
            db=db,
            user_id=current_user.id,
        )
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/budgets/{budget_id}/summary", response_model=BudgetSummaryResponse)
def get_budget_summary(
    budget_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get summary statistics for a specific budget.
    """
    try:
        summary = BudgetService.get_budget_summary(
            db=db,
            user_id=current_user.id,
            budget_id=budget_id,
        )
        # Extract the first (and only) budget summary
        if summary["budgets"]:
            return summary["budgets"][0]
        else:
            raise HTTPException(status_code=404, detail="Budget not found")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Budget rollover endpoints
@router.post("/budgets/rollover", response_model=BudgetRolloverResponse)
def process_budget_rollover(
    rollover_request: BudgetRolloverRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Process budget rollover for a specific budget.
    """
    try:
        result = BudgetService.process_rollover(
            db=db,
            user_id=current_user.id,
            rollover_request=rollover_request,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Budget alert endpoints
@router.post("/budgets/{budget_id}/alerts", response_model=BudgetAlertResponse)
def create_budget_alert(
    budget_id: int,
    alert: BudgetAlertCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Create a new budget alert.
    """
    try:
        db_alert = BudgetService.create_alert(
            db=db,
            user_id=current_user.id,
            budget_id=budget_id,
            alert_data=alert,
        )
        return db_alert
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/budgets/alerts/{alert_id}", response_model=BudgetAlertResponse)
def update_budget_alert(
    alert_id: int,
    alert: BudgetAlertUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update a budget alert.
    """
    try:
        db_alert = BudgetService.update_alert(
            db=db,
            user_id=current_user.id,
            alert_id=alert_id,
            alert_data=alert,
        )
        return db_alert
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/budgets/alerts/{alert_id}")
def delete_budget_alert(
    alert_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Delete a budget alert.
    """
    try:
        BudgetService.delete_alert(
            db=db,
            user_id=current_user.id,
            alert_id=alert_id,
        )
        return {"message": "Alert deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))