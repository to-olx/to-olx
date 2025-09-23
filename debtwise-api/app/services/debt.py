"""
Debt management service with CRUD operations and calculators.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.debt import Debt, DebtPayment, DebtStatus, DebtType
from app.models.user import User
from app.schemas.debt import (
    DebtCreate,
    DebtPaymentCreate,
    DebtSummary,
    DebtUpdate,
    PayoffStrategy,
)

logger = logging.getLogger(__name__)


class DebtService:
    """Service for managing debts and payments."""
    
    def __init__(self, db: AsyncSession):
        """Initialize the debt service."""
        self.db = db
    
    async def create_debt(self, user_id: int, debt_data: DebtCreate) -> Debt:
        """Create a new debt for a user."""
        debt = Debt(
            user_id=user_id,
            **debt_data.model_dump(),
        )
        self.db.add(debt)
        await self.db.commit()
        await self.db.refresh(debt)
        
        logger.info(f"Created debt {debt.id} for user {user_id}")
        return debt
    
    async def get_debt(self, debt_id: int, user_id: int) -> Optional[Debt]:
        """Get a specific debt by ID for a user."""
        result = await self.db.execute(
            select(Debt)
            .where(and_(Debt.id == debt_id, Debt.user_id == user_id))
            .options(selectinload(Debt.payments))
        )
        return result.scalar_one_or_none()
    
    async def get_user_debts(
        self,
        user_id: int,
        include_inactive: bool = False,
        debt_type: Optional[DebtType] = None,
    ) -> List[Debt]:
        """Get all debts for a user."""
        query = select(Debt).where(Debt.user_id == user_id)
        
        if not include_inactive:
            query = query.where(Debt.is_active == True)
        
        if debt_type:
            query = query.where(Debt.debt_type == debt_type)
        
        query = query.options(selectinload(Debt.payments))
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_debt(
        self,
        debt_id: int,
        user_id: int,
        debt_update: DebtUpdate,
    ) -> Optional[Debt]:
        """Update a debt."""
        debt = await self.get_debt(debt_id, user_id)
        if not debt:
            return None
        
        update_data = debt_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(debt, field, value)
        
        await self.db.commit()
        await self.db.refresh(debt)
        
        logger.info(f"Updated debt {debt_id} for user {user_id}")
        return debt
    
    async def delete_debt(self, debt_id: int, user_id: int) -> bool:
        """Delete a debt (soft delete by setting is_active to False)."""
        debt = await self.get_debt(debt_id, user_id)
        if not debt:
            return False
        
        debt.is_active = False
        await self.db.commit()
        
        logger.info(f"Soft deleted debt {debt_id} for user {user_id}")
        return True
    
    async def record_payment(
        self,
        user_id: int,
        payment_data: DebtPaymentCreate,
    ) -> Optional[DebtPayment]:
        """Record a payment towards a debt."""
        # Verify the debt belongs to the user
        debt = await self.get_debt(payment_data.debt_id, user_id)
        if not debt or debt.status == DebtStatus.PAID_OFF:
            return None
        
        # Calculate principal and interest portions
        principal, interest = self._calculate_payment_split(
            debt.current_balance,
            debt.interest_rate,
            payment_data.amount,
        )
        
        # Create payment record
        payment = DebtPayment(
            debt_id=payment_data.debt_id,
            user_id=user_id,
            amount=payment_data.amount,
            payment_date=payment_data.payment_date,
            principal_amount=principal,
            interest_amount=interest,
            notes=payment_data.notes,
            is_extra_payment=payment_data.is_extra_payment,
        )
        self.db.add(payment)
        
        # Update debt balance
        debt.current_balance -= principal
        if debt.current_balance <= 0:
            debt.current_balance = Decimal("0.00")
            debt.status = DebtStatus.PAID_OFF
        
        await self.db.commit()
        await self.db.refresh(payment)
        
        logger.info(f"Recorded payment {payment.id} for debt {debt.id}")
        return payment
    
    async def get_debt_summary(self, user_id: int) -> DebtSummary:
        """Get summary statistics for user's debts."""
        debts = await self.get_user_debts(user_id, include_inactive=True)
        
        if not debts:
            return DebtSummary(
                total_debt=Decimal("0"),
                total_original_debt=Decimal("0"),
                total_paid=Decimal("0"),
                total_interest_paid=Decimal("0"),
                active_debts_count=0,
                paid_off_debts_count=0,
                average_interest_rate=Decimal("0"),
                total_minimum_payment=Decimal("0"),
                debts_by_type={},
            )
        
        # Calculate totals
        total_debt = Decimal("0")
        total_original = Decimal("0")
        total_paid = Decimal("0")
        total_interest_paid = Decimal("0")
        total_minimum = Decimal("0")
        active_count = 0
        paid_off_count = 0
        weighted_rate_sum = Decimal("0")
        debts_by_type = {}
        
        for debt in debts:
            total_original += debt.original_amount
            
            if debt.status == DebtStatus.ACTIVE:
                total_debt += debt.current_balance
                total_minimum += debt.minimum_payment
                active_count += 1
                weighted_rate_sum += debt.interest_rate * debt.current_balance
            elif debt.status == DebtStatus.PAID_OFF:
                paid_off_count += 1
            
            # Count by type
            if debt.debt_type not in debts_by_type:
                debts_by_type[debt.debt_type] = 0
            debts_by_type[debt.debt_type] += 1
            
            # Sum payments
            for payment in debt.payments:
                total_paid += payment.amount
                total_interest_paid += payment.interest_amount
        
        # Calculate weighted average interest rate
        avg_rate = (
            (weighted_rate_sum / total_debt).quantize(Decimal("0.01"))
            if total_debt > 0
            else Decimal("0")
        )
        
        return DebtSummary(
            total_debt=total_debt,
            total_original_debt=total_original,
            total_paid=total_paid,
            total_interest_paid=total_interest_paid,
            active_debts_count=active_count,
            paid_off_debts_count=paid_off_count,
            average_interest_rate=avg_rate,
            total_minimum_payment=total_minimum,
            debts_by_type=debts_by_type,
        )
    
    def calculate_payoff_time(
        self,
        balance: Decimal,
        interest_rate: Decimal,
        payment_amount: Decimal,
    ) -> Tuple[int, Decimal]:
        """
        Calculate time to pay off a debt and total interest.
        
        Returns:
            Tuple of (months_to_payoff, total_interest)
        """
        if balance <= 0 or payment_amount <= 0:
            return 0, Decimal("0")
        
        monthly_rate = interest_rate / 100 / 12
        
        # Check if payment covers interest
        min_payment = balance * monthly_rate
        if payment_amount <= min_payment:
            return -1, Decimal("-1")  # Will never pay off
        
        months = 0
        remaining_balance = balance
        total_interest = Decimal("0")
        
        while remaining_balance > 0 and months < 1000:  # Safety limit
            interest_charge = remaining_balance * monthly_rate
            principal_payment = payment_amount - interest_charge
            
            if principal_payment > remaining_balance:
                principal_payment = remaining_balance
                interest_charge = remaining_balance * monthly_rate * (
                    remaining_balance / payment_amount
                )
            
            remaining_balance -= principal_payment
            total_interest += interest_charge
            months += 1
        
        # If we hit the safety limit, the debt won't be paid off
        if months >= 1000:
            return -1, Decimal("-1")
        
        return months, total_interest.quantize(Decimal("0.01"))
    
    async def generate_payoff_plan(
        self,
        user_id: int,
        strategy: PayoffStrategy,
        extra_payment: Decimal = Decimal("0"),
        debt_ids: Optional[List[int]] = None,
    ) -> dict:
        """Generate a debt payoff plan based on the selected strategy."""
        # Get active debts
        debts = await self.get_user_debts(user_id)
        
        if debt_ids:
            debts = [d for d in debts if d.id in debt_ids]
        
        if not debts:
            return {
                "strategy": strategy,
                "extra_monthly_payment": extra_payment,
                "total_months": 0,
                "payoff_date": date.today(),
                "total_interest_saved": Decimal("0"),
                "time_saved_months": 0,
                "debts": [],
            }
        
        # Sort debts based on strategy
        if strategy == PayoffStrategy.SNOWBALL:
            # Pay smallest balance first
            debts.sort(key=lambda d: d.current_balance)
        elif strategy == PayoffStrategy.AVALANCHE:
            # Pay highest interest rate first
            debts.sort(key=lambda d: d.interest_rate, reverse=True)
        
        # Calculate payoff projections
        projections = []
        total_months = 0
        current_date = date.today()
        available_extra = extra_payment
        
        for i, debt in enumerate(debts):
            payment = debt.minimum_payment
            
            # First debt gets all extra payment
            if i == 0:
                payment += available_extra
            
            months, total_interest = self.calculate_payoff_time(
                debt.current_balance,
                debt.interest_rate,
                payment,
            )
            
            if months == -1:
                # Payment doesn't cover interest
                continue
            
            payoff_date = current_date + timedelta(days=months * 30)
            
            projections.append({
                "debt_id": debt.id,
                "debt_name": debt.name,
                "current_balance": debt.current_balance,
                "payoff_order": i + 1,
                "months_to_payoff": months,
                "payoff_date": payoff_date,
                "total_interest": total_interest,
                "total_payments": debt.current_balance + total_interest,
            })
            
            # For subsequent debts, add this debt's payment to extra
            if i == 0:
                available_extra += debt.minimum_payment
            
            total_months = max(total_months, months)
        
        # Calculate savings compared to minimum payments only
        min_only_months = 0
        min_only_interest = Decimal("0")
        
        for debt in debts:
            months, interest = self.calculate_payoff_time(
                debt.current_balance,
                debt.interest_rate,
                debt.minimum_payment,
            )
            if months > 0:
                min_only_months = max(min_only_months, months)
                min_only_interest += interest
        
        total_plan_interest = sum(p["total_interest"] for p in projections)
        interest_saved = min_only_interest - total_plan_interest
        time_saved = min_only_months - total_months
        
        return {
            "strategy": strategy,
            "extra_monthly_payment": extra_payment,
            "total_months": total_months,
            "payoff_date": current_date + timedelta(days=total_months * 30),
            "total_interest_saved": interest_saved.quantize(Decimal("0.01")),
            "time_saved_months": max(0, time_saved),
            "debts": projections,
        }
    
    def calculate_interest_breakdown(
        self,
        principal: Decimal,
        interest_rate: Decimal,
        payment_amount: Decimal,
    ) -> dict:
        """Calculate detailed interest breakdown for a loan."""
        monthly_rate = interest_rate / 100 / 12
        months, total_interest = self.calculate_payoff_time(
            principal, interest_rate, payment_amount
        )
        
        if months == -1:
            return {
                "error": "Payment amount is too low to cover interest"
            }
        
        # Calculate first 12 months breakdown
        monthly_breakdown = []
        remaining = principal
        
        for month in range(min(12, months)):
            interest_charge = remaining * monthly_rate
            principal_payment = payment_amount - interest_charge
            
            if principal_payment > remaining:
                principal_payment = remaining
            
            remaining -= principal_payment
            
            monthly_breakdown.append({
                "month": month + 1,
                "payment": float(payment_amount),
                "principal": float(principal_payment),
                "interest": float(interest_charge),
                "remaining_balance": float(remaining),
            })
        
        total_payments = payment_amount * months
        interest_percentage = (total_interest / total_payments * 100).quantize(
            Decimal("0.01")
        )
        
        return {
            "months_to_payoff": months,
            "total_payments": total_payments,
            "total_interest": total_interest,
            "interest_percentage": interest_percentage,
            "monthly_breakdown": monthly_breakdown,
        }
    
    def _calculate_payment_split(
        self,
        balance: Decimal,
        annual_rate: Decimal,
        payment: Decimal,
    ) -> Tuple[Decimal, Decimal]:
        """Calculate how a payment is split between principal and interest."""
        monthly_rate = annual_rate / 100 / 12
        interest = (balance * monthly_rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        # Ensure interest doesn't exceed payment
        if interest > payment:
            interest = payment
            principal = Decimal("0")
        else:
            principal = payment - interest
        
        # Ensure principal doesn't exceed balance
        if principal > balance:
            principal = balance
            # Recalculate interest for partial payment
            interest = payment - principal
        
        return principal, interest