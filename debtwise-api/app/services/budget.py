"""
Service layer for budget-related business logic.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple

from dateutil.relativedelta import relativedelta
from sqlalchemy import and_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.budget import Budget, BudgetAlert, BudgetPeriod, BudgetPeriodType
from app.models.transaction import Category, Transaction, TransactionType
from app.schemas.budget import (
    BudgetAlertCreate,
    BudgetAlertUpdate,
    BudgetCreate,
    BudgetRolloverRequest,
    BudgetUpdate,
)


class BudgetService:
    """Service for managing budgets."""
    
    @staticmethod
    def create_budget(
        db: Session,
        user_id: int,
        budget_data: BudgetCreate,
    ) -> Budget:
        """Create a new budget with optional alerts."""
        # Check if category belongs to user
        if budget_data.category_id:
            category = db.query(Category).filter(
                Category.id == budget_data.category_id,
                Category.user_id == user_id,
            ).first()
            if not category:
                raise ValueError("Category not found or does not belong to user")
        
        # Check for duplicate budget name
        existing = db.query(Budget).filter(
            Budget.user_id == user_id,
            Budget.name == budget_data.name,
        ).first()
        if existing:
            raise ValueError("Budget with this name already exists")
        
        # Create budget
        alerts_data = budget_data.alerts or []
        budget_dict = budget_data.model_dump(exclude={"alerts"})
        db_budget = Budget(
            user_id=user_id,
            **budget_dict,
        )
        
        db.add(db_budget)
        db.flush()  # Get the budget ID
        
        # Create initial budget period
        BudgetService._create_initial_period(db, db_budget)
        
        # Create alerts
        for alert_data in alerts_data:
            db_alert = BudgetAlert(
                budget_id=db_budget.id,
                **alert_data.model_dump(),
            )
            db.add(db_alert)
        
        db.commit()
        db.refresh(db_budget)
        return db_budget
    
    @staticmethod
    def update_budget(
        db: Session,
        user_id: int,
        budget_id: int,
        budget_data: BudgetUpdate,
    ) -> Budget:
        """Update an existing budget."""
        # Get budget
        db_budget = db.query(Budget).filter(
            Budget.id == budget_id,
            Budget.user_id == user_id,
        ).first()
        if not db_budget:
            raise ValueError("Budget not found")
        
        # Check for duplicate name
        if budget_data.name and budget_data.name != db_budget.name:
            existing = db.query(Budget).filter(
                Budget.user_id == user_id,
                Budget.name == budget_data.name,
            ).first()
            if existing:
                raise ValueError("Budget with this name already exists")
        
        # Update fields
        for field, value in budget_data.model_dump(exclude_unset=True).items():
            setattr(db_budget, field, value)
        
        # If amount changed, update current period
        if budget_data.amount:
            current_period = BudgetService.get_current_period(db, db_budget)
            if current_period and not current_period.is_closed:
                current_period.base_amount = budget_data.amount
                current_period.total_amount = current_period.base_amount + current_period.rollover_amount
                BudgetService._update_period_spent_amount(db, current_period)
        
        db.commit()
        db.refresh(db_budget)
        return db_budget
    
    @staticmethod
    def delete_budget(db: Session, user_id: int, budget_id: int) -> bool:
        """Delete a budget."""
        db_budget = db.query(Budget).filter(
            Budget.id == budget_id,
            Budget.user_id == user_id,
        ).first()
        if not db_budget:
            raise ValueError("Budget not found")
        
        db.delete(db_budget)
        db.commit()
        return True
    
    @staticmethod
    def get_budget(
        db: Session,
        user_id: int,
        budget_id: int,
        include_current_period: bool = True,
    ) -> Optional[Budget]:
        """Get a budget by ID."""
        query = db.query(Budget).filter(
            Budget.id == budget_id,
            Budget.user_id == user_id,
        )
        
        if include_current_period:
            query = query.options(joinedload(Budget.budget_periods))
        
        return query.first()
    
    @staticmethod
    def get_user_budgets(
        db: Session,
        user_id: int,
        active_only: bool = True,
        category_id: Optional[int] = None,
    ) -> List[Budget]:
        """Get all budgets for a user."""
        query = db.query(Budget).filter(Budget.user_id == user_id)
        
        if active_only:
            query = query.filter(Budget.is_active == True)
        
        if category_id is not None:
            query = query.filter(Budget.category_id == category_id)
        
        return query.all()
    
    @staticmethod
    def get_current_period(db: Session, budget: Budget) -> Optional[BudgetPeriod]:
        """Get the current period for a budget."""
        today = date.today()
        return db.query(BudgetPeriod).filter(
            BudgetPeriod.budget_id == budget.id,
            BudgetPeriod.start_date <= today,
            BudgetPeriod.end_date >= today,
        ).first()
    
    @staticmethod
    def process_rollover(
        db: Session,
        user_id: int,
        rollover_request: BudgetRolloverRequest,
    ) -> dict:
        """Process budget rollover for a specific budget."""
        # Get budget
        db_budget = db.query(Budget).filter(
            Budget.id == rollover_request.budget_id,
            Budget.user_id == user_id,
        ).first()
        if not db_budget:
            raise ValueError("Budget not found")
        
        if not db_budget.allow_rollover:
            raise ValueError("Rollover is not enabled for this budget")
        
        target_date = rollover_request.period_date or date.today()
        periods_processed = 0
        
        # Get or create all periods up to the target date
        while True:
            # Get the latest period
            latest_period = db.query(BudgetPeriod).filter(
                BudgetPeriod.budget_id == db_budget.id
            ).order_by(BudgetPeriod.end_date.desc()).first()
            
            if latest_period and latest_period.end_date >= target_date:
                break
            
            # Create next period
            if latest_period:
                new_period = BudgetService._create_next_period(
                    db, db_budget, latest_period
                )
            else:
                new_period = BudgetService._create_initial_period(db, db_budget)
            
            periods_processed += 1
        
        # Get the current period
        current_period = BudgetService.get_current_period(db, db_budget)
        
        # Get the previous period for rollover details
        previous_period = None
        if current_period:
            previous_period = db.query(BudgetPeriod).filter(
                BudgetPeriod.budget_id == db_budget.id,
                BudgetPeriod.end_date < current_period.start_date
            ).order_by(BudgetPeriod.end_date.desc()).first()
        
        db.commit()
        
        return {
            "budget_id": db_budget.id,
            "periods_processed": periods_processed,
            "previous_period": previous_period,
            "new_period": current_period,
            "rollover_amount": current_period.rollover_amount if current_period else Decimal("0"),
            "success": True,
            "message": f"Processed {periods_processed} periods with rollover",
        }
    
    @staticmethod
    def get_budget_summary(
        db: Session,
        user_id: int,
        budget_id: Optional[int] = None,
    ) -> dict:
        """Get budget summary with spending analysis."""
        if budget_id:
            budgets = [BudgetService.get_budget(db, user_id, budget_id)]
            if not budgets[0]:
                raise ValueError("Budget not found")
        else:
            budgets = BudgetService.get_user_budgets(db, user_id)
        
        summaries = []
        total_budgeted = Decimal("0")
        total_spent = Decimal("0")
        total_remaining = Decimal("0")
        
        for budget in budgets:
            current_period = BudgetService.get_current_period(db, budget)
            if not current_period:
                continue
            
            # Update spent amount
            BudgetService._update_period_spent_amount(db, current_period)
            
            # Calculate days remaining
            today = date.today()
            days_remaining = (current_period.end_date - today).days + 1
            
            # Calculate percentage used
            percentage_used = float(
                (current_period.spent_amount / current_period.total_amount * 100)
                if current_period.total_amount > 0 else 0
            )
            
            # Get category name
            category_name = None
            if budget.category_id:
                category = db.query(Category).filter(
                    Category.id == budget.category_id
                ).first()
                category_name = category.name if category else None
            
            # Check alerts
            active_alerts = []
            for alert in budget.alerts:
                if alert.is_enabled and percentage_used >= alert.threshold_percentage:
                    active_alerts.append(
                        alert.alert_message or f"Budget is {percentage_used:.1f}% used"
                    )
            
            summary = {
                "budget_id": budget.id,
                "budget_name": budget.name,
                "category_id": budget.category_id,
                "category_name": category_name,
                "period_type": budget.period_type,
                "current_period": current_period,
                "total_budgeted": current_period.total_amount,
                "total_spent": current_period.spent_amount,
                "total_remaining": current_period.remaining_amount,
                "percentage_used": percentage_used,
                "days_remaining": days_remaining,
                "active_alerts": active_alerts,
                "is_over_budget": current_period.spent_amount > current_period.total_amount,
            }
            
            # Add trend data
            summary["average_monthly_spending"] = BudgetService._calculate_average_spending(
                db, budget, user_id
            )
            
            # Project end of period spending
            if days_remaining > 0 and current_period.spent_amount > 0:
                days_elapsed = (today - current_period.start_date).days + 1
                daily_rate = current_period.spent_amount / days_elapsed
                summary["projected_end_of_period"] = daily_rate * (
                    (current_period.end_date - current_period.start_date).days + 1
                )
            else:
                summary["projected_end_of_period"] = current_period.spent_amount
            
            summaries.append(summary)
            total_budgeted += current_period.total_amount
            total_spent += current_period.spent_amount
            total_remaining += current_period.remaining_amount
        
        # Get unbudgeted spending
        unbudgeted_spending = BudgetService._get_unbudgeted_spending(db, user_id)
        
        return {
            "total_budgets": len(budgets),
            "active_budgets": len([b for b in budgets if b.is_active]),
            "total_budgeted_amount": total_budgeted,
            "total_spent_amount": total_spent,
            "total_remaining_amount": total_remaining,
            "overall_percentage_used": float(
                (total_spent / total_budgeted * 100) if total_budgeted > 0 else 0
            ),
            "budgets": summaries,
            "unbudgeted_spending": unbudgeted_spending["amount"],
            "unbudgeted_categories": unbudgeted_spending["categories"],
        }
    
    # Alert management methods
    @staticmethod
    def create_alert(
        db: Session,
        user_id: int,
        budget_id: int,
        alert_data: BudgetAlertCreate,
    ) -> BudgetAlert:
        """Create a budget alert."""
        # Verify budget ownership
        budget = db.query(Budget).filter(
            Budget.id == budget_id,
            Budget.user_id == user_id,
        ).first()
        if not budget:
            raise ValueError("Budget not found")
        
        # Check for duplicate threshold
        existing = db.query(BudgetAlert).filter(
            BudgetAlert.budget_id == budget_id,
            BudgetAlert.threshold_percentage == alert_data.threshold_percentage,
        ).first()
        if existing:
            raise ValueError("Alert with this threshold already exists")
        
        db_alert = BudgetAlert(
            budget_id=budget_id,
            **alert_data.model_dump(),
        )
        db.add(db_alert)
        db.commit()
        db.refresh(db_alert)
        return db_alert
    
    @staticmethod
    def update_alert(
        db: Session,
        user_id: int,
        alert_id: int,
        alert_data: BudgetAlertUpdate,
    ) -> BudgetAlert:
        """Update a budget alert."""
        # Get alert with budget
        db_alert = db.query(BudgetAlert).join(Budget).filter(
            BudgetAlert.id == alert_id,
            Budget.user_id == user_id,
        ).first()
        if not db_alert:
            raise ValueError("Alert not found")
        
        # Update fields
        for field, value in alert_data.model_dump(exclude_unset=True).items():
            setattr(db_alert, field, value)
        
        db.commit()
        db.refresh(db_alert)
        return db_alert
    
    @staticmethod
    def delete_alert(db: Session, user_id: int, alert_id: int) -> bool:
        """Delete a budget alert."""
        db_alert = db.query(BudgetAlert).join(Budget).filter(
            BudgetAlert.id == alert_id,
            Budget.user_id == user_id,
        ).first()
        if not db_alert:
            raise ValueError("Alert not found")
        
        db.delete(db_alert)
        db.commit()
        return True
    
    # Private helper methods
    @staticmethod
    def _create_initial_period(db: Session, budget: Budget) -> BudgetPeriod:
        """Create the initial budget period."""
        start_date = budget.start_date
        end_date = BudgetService._calculate_period_end_date(
            start_date, budget.period_type
        )
        
        period = BudgetPeriod(
            budget_id=budget.id,
            start_date=start_date,
            end_date=end_date,
            base_amount=budget.amount,
            rollover_amount=Decimal("0"),
            total_amount=budget.amount,
            spent_amount=Decimal("0"),
            remaining_amount=budget.amount,
        )
        
        db.add(period)
        db.flush()
        
        # Update spent amount
        BudgetService._update_period_spent_amount(db, period)
        
        return period
    
    @staticmethod
    def _create_next_period(
        db: Session,
        budget: Budget,
        previous_period: BudgetPeriod,
    ) -> BudgetPeriod:
        """Create the next budget period with rollover."""
        # Close previous period if not already closed
        if not previous_period.is_closed:
            BudgetService._update_period_spent_amount(db, previous_period)
            previous_period.is_closed = True
            db.flush()
        
        # Calculate new period dates
        start_date = previous_period.end_date + timedelta(days=1)
        end_date = BudgetService._calculate_period_end_date(
            start_date, budget.period_type
        )
        
        # Calculate rollover amount
        rollover_amount = Decimal("0")
        if budget.allow_rollover and previous_period.remaining_amount > 0:
            rollover_amount = previous_period.remaining_amount
            
            # Apply rollover limits
            if budget.max_rollover_periods:
                # Count previous rollovers
                periods_with_rollover = db.query(BudgetPeriod).filter(
                    BudgetPeriod.budget_id == budget.id,
                    BudgetPeriod.rollover_amount > 0,
                    BudgetPeriod.end_date < start_date,
                ).count()
                
                if periods_with_rollover >= budget.max_rollover_periods:
                    rollover_amount = Decimal("0")
            
            if budget.max_rollover_amount and rollover_amount > budget.max_rollover_amount:
                rollover_amount = budget.max_rollover_amount
        
        # Create new period
        period = BudgetPeriod(
            budget_id=budget.id,
            start_date=start_date,
            end_date=end_date,
            base_amount=budget.amount,
            rollover_amount=rollover_amount,
            total_amount=budget.amount + rollover_amount,
            spent_amount=Decimal("0"),
            remaining_amount=budget.amount + rollover_amount,
        )
        
        db.add(period)
        db.flush()
        
        # Update spent amount
        BudgetService._update_period_spent_amount(db, period)
        
        return period
    
    @staticmethod
    def _calculate_period_end_date(start_date: date, period_type: BudgetPeriodType) -> date:
        """Calculate the end date for a budget period."""
        if period_type == BudgetPeriodType.WEEKLY:
            return start_date + timedelta(days=6)
        elif period_type == BudgetPeriodType.MONTHLY:
            return start_date + relativedelta(months=1) - timedelta(days=1)
        elif period_type == BudgetPeriodType.QUARTERLY:
            return start_date + relativedelta(months=3) - timedelta(days=1)
        elif period_type == BudgetPeriodType.YEARLY:
            return start_date + relativedelta(years=1) - timedelta(days=1)
        else:
            raise ValueError(f"Invalid period type: {period_type}")
    
    @staticmethod
    def _update_period_spent_amount(db: Session, period: BudgetPeriod) -> None:
        """Update the spent amount for a budget period."""
        budget = db.query(Budget).filter(Budget.id == period.budget_id).first()
        if not budget:
            return
        
        # Build transaction query
        query = db.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == budget.user_id,
            Transaction.transaction_type == TransactionType.EXPENSE,
            Transaction.transaction_date >= period.start_date,
            Transaction.transaction_date <= period.end_date,
        )
        
        # Filter by category if specified
        if budget.category_id:
            query = query.filter(Transaction.category_id == budget.category_id)
        
        # Get spent amount
        spent = query.scalar() or Decimal("0")
        
        # Update period
        period.spent_amount = spent
        period.remaining_amount = period.total_amount - spent
        db.flush()
    
    @staticmethod
    def _calculate_average_spending(
        db: Session,
        budget: Budget,
        user_id: int,
        months: int = 3,
    ) -> Optional[Decimal]:
        """Calculate average monthly spending for a budget category."""
        end_date = date.today()
        start_date = end_date - relativedelta(months=months)
        
        # Build query
        query = db.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id,
            Transaction.transaction_type == TransactionType.EXPENSE,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date,
        )
        
        if budget.category_id:
            query = query.filter(Transaction.category_id == budget.category_id)
        
        total = query.scalar() or Decimal("0")
        return total / months if total > 0 else None
    
    @staticmethod
    def _get_unbudgeted_spending(db: Session, user_id: int) -> dict:
        """Get spending in categories without budgets."""
        today = date.today()
        month_start = date(today.year, today.month, 1)
        
        # Get all categories with budgets
        budgeted_categories = db.query(Budget.category_id).filter(
            Budget.user_id == user_id,
            Budget.is_active == True,
            Budget.category_id.isnot(None),
        ).subquery()
        
        # Get spending in unbudgeted categories
        unbudgeted_query = db.query(
            Category.name,
            func.sum(Transaction.amount).label("total")
        ).join(
            Transaction,
            Transaction.category_id == Category.id
        ).filter(
            Transaction.user_id == user_id,
            Transaction.transaction_type == TransactionType.EXPENSE,
            Transaction.transaction_date >= month_start,
            Transaction.category_id.notin_(budgeted_categories),
        ).group_by(Category.name)
        
        results = unbudgeted_query.all()
        
        total_amount = sum(result.total for result in results)
        categories = [result.name for result in results]
        
        return {
            "amount": total_amount,
            "categories": categories,
        }