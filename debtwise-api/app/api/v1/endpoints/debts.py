"""
Debt management API endpoints.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user, get_db
from app.models.debt import DebtType
from app.models.user import User
from app.schemas.debt import (
    DebtCreate,
    DebtPaymentCreate,
    DebtPaymentResponse,
    DebtResponse,
    DebtSummary,
    DebtUpdate,
    InterestCalculatorRequest,
    InterestCalculatorResponse,
    PayoffPlanRequest,
    PayoffPlanResponse,
)
from app.services.analytics import analytics_service, EventType
from app.services.debt import DebtService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/summary", response_model=DebtSummary)
async def get_debt_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DebtSummary:
    """Get summary statistics for user's debts."""
    service = DebtService(db)
    summary = await service.get_debt_summary(current_user.id)
    
    await analytics_service.track_event(
        EventType.PAGE_VIEW,
        user_id=current_user.id,
        metadata={"page": "debt_summary"},
    )
    
    return summary


@router.get("/", response_model=List[DebtResponse])
async def get_debts(
    include_inactive: bool = Query(False, description="Include inactive debts"),
    debt_type: DebtType = Query(None, description="Filter by debt type"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[DebtResponse]:
    """Get all debts for the current user."""
    service = DebtService(db)
    debts = await service.get_user_debts(
        current_user.id,
        include_inactive=include_inactive,
        debt_type=debt_type,
    )
    
    # Calculate additional fields for response
    responses = []
    for debt in debts:
        # Calculate totals from payments
        total_paid = sum(p.amount for p in debt.payments)
        total_interest_paid = sum(p.interest_amount for p in debt.payments)
        
        # Calculate months to payoff
        months_to_payoff = None
        if debt.current_balance > 0:
            months, _ = service.calculate_payoff_time(
                debt.current_balance,
                debt.interest_rate,
                debt.minimum_payment,
            )
            months_to_payoff = months if months > 0 else None
        
        # Calculate next payment date
        next_payment_date = None
        if debt.due_date and debt.status == "active":
            from datetime import date, timedelta
            today = date.today()
            
            # Find next occurrence of due_date
            if today.day <= debt.due_date:
                next_payment_date = today.replace(day=debt.due_date)
            else:
                # Next month
                if today.month == 12:
                    next_payment_date = date(today.year + 1, 1, debt.due_date)
                else:
                    next_payment_date = today.replace(
                        month=today.month + 1,
                        day=debt.due_date,
                    )
        
        response = DebtResponse.model_validate(debt)
        response.total_paid = total_paid
        response.total_interest_paid = total_interest_paid
        response.months_to_payoff = months_to_payoff
        response.next_payment_date = next_payment_date
        
        responses.append(response)
    
    return responses


@router.get("/{debt_id}", response_model=DebtResponse)
async def get_debt(
    debt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DebtResponse:
    """Get a specific debt by ID."""
    service = DebtService(db)
    debt = await service.get_debt(debt_id, current_user.id)
    
    if not debt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debt not found",
        )
    
    # Calculate additional fields
    total_paid = sum(p.amount for p in debt.payments)
    total_interest_paid = sum(p.interest_amount for p in debt.payments)
    
    months_to_payoff = None
    if debt.current_balance > 0:
        months, _ = service.calculate_payoff_time(
            debt.current_balance,
            debt.interest_rate,
            debt.minimum_payment,
        )
        months_to_payoff = months if months > 0 else None
    
    response = DebtResponse.model_validate(debt)
    response.total_paid = total_paid
    response.total_interest_paid = total_interest_paid
    response.months_to_payoff = months_to_payoff
    
    return response


@router.post("/", response_model=DebtResponse, status_code=status.HTTP_201_CREATED)
async def create_debt(
    debt_data: DebtCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DebtResponse:
    """Create a new debt."""
    service = DebtService(db)
    debt = await service.create_debt(current_user.id, debt_data)
    
    await analytics_service.track_event(
        EventType.USER_ACTION,
        user_id=current_user.id,
        metadata={
            "action": "create_debt",
            "debt_type": debt_data.debt_type,
            "amount": float(debt_data.original_amount),
        },
    )
    
    return DebtResponse.model_validate(debt)


@router.patch("/{debt_id}", response_model=DebtResponse)
async def update_debt(
    debt_id: int,
    debt_update: DebtUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DebtResponse:
    """Update a debt."""
    service = DebtService(db)
    debt = await service.update_debt(debt_id, current_user.id, debt_update)
    
    if not debt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debt not found",
        )
    
    await analytics_service.track_event(
        EventType.USER_ACTION,
        user_id=current_user.id,
        metadata={
            "action": "update_debt",
            "debt_id": debt_id,
        },
    )
    
    return DebtResponse.model_validate(debt)


@router.delete("/{debt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_debt(
    debt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """Delete a debt (soft delete)."""
    service = DebtService(db)
    deleted = await service.delete_debt(debt_id, current_user.id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debt not found",
        )
    
    await analytics_service.track_event(
        EventType.USER_ACTION,
        user_id=current_user.id,
        metadata={
            "action": "delete_debt",
            "debt_id": debt_id,
        },
    )


@router.post("/payments", response_model=DebtPaymentResponse, status_code=status.HTTP_201_CREATED)
async def record_payment(
    payment_data: DebtPaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DebtPaymentResponse:
    """Record a payment towards a debt."""
    service = DebtService(db)
    payment = await service.record_payment(current_user.id, payment_data)
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid debt ID or debt is already paid off",
        )
    
    # Get updated debt balance
    debt = await service.get_debt(payment.debt_id, current_user.id)
    
    await analytics_service.track_event(
        EventType.USER_ACTION,
        user_id=current_user.id,
        metadata={
            "action": "record_payment",
            "debt_id": payment.debt_id,
            "amount": float(payment.amount),
            "is_extra": payment.is_extra_payment,
        },
    )
    
    response = DebtPaymentResponse.model_validate(payment)
    response.balance_after_payment = debt.current_balance
    
    return response


@router.get("/{debt_id}/payments", response_model=List[DebtPaymentResponse])
async def get_debt_payments(
    debt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[DebtPaymentResponse]:
    """Get all payments for a specific debt."""
    service = DebtService(db)
    debt = await service.get_debt(debt_id, current_user.id)
    
    if not debt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debt not found",
        )
    
    responses = []
    running_balance = debt.original_amount
    
    # Sort payments by date to calculate running balance
    sorted_payments = sorted(debt.payments, key=lambda p: p.payment_date)
    
    for payment in sorted_payments:
        running_balance -= payment.principal_amount
        response = DebtPaymentResponse.model_validate(payment)
        response.balance_after_payment = max(running_balance, 0)
        responses.append(response)
    
    return responses


@router.post("/payoff-plan", response_model=PayoffPlanResponse)
async def generate_payoff_plan(
    plan_request: PayoffPlanRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PayoffPlanResponse:
    """Generate a debt payoff plan based on selected strategy."""
    service = DebtService(db)
    
    plan_data = await service.generate_payoff_plan(
        user_id=current_user.id,
        strategy=plan_request.strategy,
        extra_payment=plan_request.extra_monthly_payment,
        debt_ids=plan_request.debt_ids,
    )
    
    await analytics_service.track_event(
        EventType.USER_ACTION,
        user_id=current_user.id,
        metadata={
            "action": "generate_payoff_plan",
            "strategy": plan_request.strategy,
            "extra_payment": float(plan_request.extra_monthly_payment),
        },
    )
    
    return PayoffPlanResponse(**plan_data)


@router.post("/calculator/interest", response_model=InterestCalculatorResponse)
async def calculate_interest(
    calc_request: InterestCalculatorRequest,
    current_user: User = Depends(get_current_active_user),
) -> InterestCalculatorResponse:
    """Calculate interest and payoff timeline for a loan."""
    service = DebtService(None)  # No DB needed for calculation
    
    result = service.calculate_interest_breakdown(
        calc_request.principal,
        calc_request.interest_rate,
        calc_request.payment_amount,
    )
    
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )
    
    await analytics_service.track_event(
        EventType.USER_ACTION,
        user_id=current_user.id,
        metadata={
            "action": "use_interest_calculator",
            "principal": float(calc_request.principal),
            "rate": float(calc_request.interest_rate),
        },
    )
    
    return InterestCalculatorResponse(**result)