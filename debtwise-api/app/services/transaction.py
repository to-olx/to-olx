"""
Service layer for transaction-related business logic.
"""

import csv
import io
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.transaction import (
    Category,
    Transaction,
    TransactionRule,
    TransactionType,
)
from app.schemas.transaction import (
    CategoryCreate,
    CategoryUpdate,
    CSVImportRequest,
    TransactionCreate,
    TransactionFilter,
    TransactionRuleCreate,
    TransactionRuleUpdate,
    TransactionUpdate,
)


class TransactionService:
    """Service for managing transactions."""
    
    @staticmethod
    def create_transaction(
        db: Session,
        user_id: int,
        transaction_data: TransactionCreate,
    ) -> Transaction:
        """Create a new transaction."""
        # Check if category belongs to user
        if transaction_data.category_id:
            category = db.query(Category).filter(
                Category.id == transaction_data.category_id,
                Category.user_id == user_id,
            ).first()
            if not category:
                raise ValueError("Category not found or does not belong to user")
        
        # Create transaction
        db_transaction = Transaction(
            user_id=user_id,
            **transaction_data.model_dump(),
        )
        
        # Auto-categorize if no category provided
        if not db_transaction.category_id:
            db_transaction.category_id = TransactionService._apply_rules(
                db, user_id, db_transaction
            )
        
        db.add(db_transaction)
        db.commit()
        db.refresh(db_transaction)
        return db_transaction
    
    @staticmethod
    def update_transaction(
        db: Session,
        user_id: int,
        transaction_id: int,
        transaction_data: TransactionUpdate,
    ) -> Transaction:
        """Update an existing transaction."""
        # Get transaction
        db_transaction = db.query(Transaction).filter(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
        ).first()
        if not db_transaction:
            raise ValueError("Transaction not found")
        
        # Check if new category belongs to user
        if transaction_data.category_id is not None:
            if transaction_data.category_id:  # Only check if not None
                category = db.query(Category).filter(
                    Category.id == transaction_data.category_id,
                    Category.user_id == user_id,
                ).first()
                if not category:
                    raise ValueError("Category not found or does not belong to user")
        
        # Update fields
        for field, value in transaction_data.model_dump(exclude_unset=True).items():
            setattr(db_transaction, field, value)
        
        db.commit()
        db.refresh(db_transaction)
        return db_transaction
    
    @staticmethod
    def delete_transaction(
        db: Session,
        user_id: int,
        transaction_id: int,
    ) -> bool:
        """Delete a transaction."""
        db_transaction = db.query(Transaction).filter(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
        ).first()
        if not db_transaction:
            return False
        
        db.delete(db_transaction)
        db.commit()
        return True
    
    @staticmethod
    def get_transactions(
        db: Session,
        user_id: int,
        filters: Optional[TransactionFilter] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[Transaction], int]:
        """Get transactions with optional filters."""
        query = db.query(Transaction).filter(Transaction.user_id == user_id)
        
        if filters:
            if filters.start_date:
                query = query.filter(Transaction.transaction_date >= filters.start_date)
            if filters.end_date:
                query = query.filter(Transaction.transaction_date <= filters.end_date)
            if filters.category_ids:
                query = query.filter(Transaction.category_id.in_(filters.category_ids))
            if filters.transaction_type:
                query = query.filter(Transaction.transaction_type == filters.transaction_type)
            if filters.min_amount is not None:
                query = query.filter(Transaction.amount >= filters.min_amount)
            if filters.max_amount is not None:
                query = query.filter(Transaction.amount <= filters.max_amount)
            if filters.search_text:
                search_pattern = f"%{filters.search_text}%"
                query = query.filter(
                    or_(
                        Transaction.description.ilike(search_pattern),
                        Transaction.merchant.ilike(search_pattern),
                    )
                )
            if filters.tags:
                # Filter by any of the provided tags
                tag_conditions = []
                for tag in filters.tags:
                    tag_conditions.append(Transaction.tags.contains(tag))
                query = query.filter(or_(*tag_conditions))
            if filters.account_names:
                query = query.filter(Transaction.account_name.in_(filters.account_names))
            if filters.is_recurring is not None:
                query = query.filter(Transaction.is_recurring == filters.is_recurring)
        
        # Get total count
        total = query.count()
        
        # Get paginated results
        transactions = (
            query.options(joinedload(Transaction.category))
            .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        
        return transactions, total
    
    @staticmethod
    def _apply_rules(
        db: Session,
        user_id: int,
        transaction: Transaction,
    ) -> Optional[int]:
        """Apply transaction rules to categorize a transaction."""
        # Get active rules for user, ordered by priority
        rules = db.query(TransactionRule).filter(
            TransactionRule.user_id == user_id,
            TransactionRule.is_active == True,
        ).order_by(TransactionRule.priority.desc()).all()
        
        for rule in rules:
            # Check transaction type
            if rule.transaction_type and rule.transaction_type != transaction.transaction_type:
                continue
            
            # Check amount range
            if rule.amount_min and transaction.amount < rule.amount_min:
                continue
            if rule.amount_max and transaction.amount > rule.amount_max:
                continue
            
            # Check description pattern
            if rule.description_pattern:
                try:
                    if not re.search(rule.description_pattern, transaction.description, re.IGNORECASE):
                        continue
                except re.error:
                    continue
            
            # Check merchant pattern
            if rule.merchant_pattern and transaction.merchant:
                try:
                    if not re.search(rule.merchant_pattern, transaction.merchant, re.IGNORECASE):
                        continue
                except re.error:
                    continue
            elif rule.merchant_pattern and not transaction.merchant:
                continue
            
            # All conditions match, apply this rule
            return rule.category_id
        
        return None
    
    @staticmethod
    def import_csv(
        db: Session,
        user_id: int,
        file_content: str,
        import_config: CSVImportRequest,
    ) -> Dict[str, Any]:
        """Import transactions from CSV file."""
        results = {
            "total_rows": 0,
            "imported_count": 0,
            "skipped_count": 0,
            "error_count": 0,
            "errors": [],
            "imported_transactions": [],
        }
        
        # Get user's categories for mapping
        categories = db.query(Category).filter(Category.user_id == user_id).all()
        category_map = {cat.name.lower(): cat.id for cat in categories}
        
        # Parse CSV
        csv_file = io.StringIO(file_content)
        reader = csv.DictReader(csv_file)
        
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
            results["total_rows"] += 1
            
            try:
                # Parse date
                date_str = row.get(import_config.date_column)
                if not date_str:
                    raise ValueError(f"Missing date in column '{import_config.date_column}'")
                transaction_date = datetime.strptime(date_str.strip(), import_config.date_format).date()
                
                # Parse amount
                amount_str = row.get(import_config.amount_column)
                if not amount_str:
                    raise ValueError(f"Missing amount in column '{import_config.amount_column}'")
                
                # Clean amount string
                amount_str = amount_str.strip().replace(",", "").replace("$", "")
                amount = Decimal(amount_str)
                
                # Determine transaction type based on amount
                if amount < 0:
                    transaction_type = TransactionType.EXPENSE
                    amount = abs(amount)
                else:
                    transaction_type = TransactionType.INCOME
                
                # Get description
                description = row.get(import_config.description_column, "").strip()
                if not description:
                    raise ValueError(f"Missing description in column '{import_config.description_column}'")
                
                # Optional fields
                merchant = row.get(import_config.merchant_column, "").strip() if import_config.merchant_column else None
                account_name = row.get(import_config.account_column, "").strip() if import_config.account_column else import_config.default_account
                tags = row.get(import_config.tags_column, "").strip() if import_config.tags_column else None
                
                # Category mapping
                category_id = None
                if import_config.category_column:
                    category_name = row.get(import_config.category_column, "").strip().lower()
                    if category_name:
                        category_id = category_map.get(category_name)
                
                # Create import_id from row data
                import_id = f"{transaction_date}_{amount}_{description[:50]}"
                
                # Check for duplicates
                if import_config.skip_duplicates:
                    existing = db.query(Transaction).filter(
                        Transaction.user_id == user_id,
                        Transaction.import_id == import_id,
                    ).first()
                    if existing:
                        results["skipped_count"] += 1
                        continue
                
                # Create transaction data
                transaction_data = TransactionCreate(
                    amount=amount,
                    transaction_date=transaction_date,
                    description=description,
                    transaction_type=transaction_type,
                    category_id=category_id,
                    account_name=account_name,
                    merchant=merchant,
                    tags=tags,
                    import_id=import_id,
                )
                
                # Create transaction
                db_transaction = Transaction(
                    user_id=user_id,
                    **transaction_data.model_dump(),
                )
                
                # Auto-categorize if enabled and no category
                if import_config.auto_categorize and not db_transaction.category_id:
                    db_transaction.category_id = TransactionService._apply_rules(
                        db, user_id, db_transaction
                    )
                
                db.add(db_transaction)
                results["imported_transactions"].append(db_transaction)
                results["imported_count"] += 1
                
            except Exception as e:
                results["error_count"] += 1
                results["errors"].append(f"Row {row_num}: {str(e)}")
                if len(results["errors"]) >= 50:  # Limit error messages
                    results["errors"].append("... additional errors omitted")
                    break
        
        # Commit all transactions
        if results["imported_count"] > 0:
            db.commit()
            # Refresh transactions to get IDs
            for trans in results["imported_transactions"]:
                db.refresh(trans)
        
        return results


class CategoryService:
    """Service for managing categories."""
    
    @staticmethod
    def create_category(
        db: Session,
        user_id: int,
        category_data: CategoryCreate,
    ) -> Category:
        """Create a new category."""
        # Check if parent category exists and belongs to user
        if category_data.parent_id:
            parent = db.query(Category).filter(
                Category.id == category_data.parent_id,
                Category.user_id == user_id,
            ).first()
            if not parent:
                raise ValueError("Parent category not found or does not belong to user")
        
        # Check for duplicate name
        existing = db.query(Category).filter(
            Category.user_id == user_id,
            Category.name == category_data.name,
            Category.parent_id == category_data.parent_id,
        ).first()
        if existing:
            raise ValueError("Category with this name already exists")
        
        # Create category
        db_category = Category(
            user_id=user_id,
            **category_data.model_dump(),
        )
        db.add(db_category)
        db.commit()
        db.refresh(db_category)
        return db_category
    
    @staticmethod
    def update_category(
        db: Session,
        user_id: int,
        category_id: int,
        category_data: CategoryUpdate,
    ) -> Category:
        """Update an existing category."""
        # Get category
        db_category = db.query(Category).filter(
            Category.id == category_id,
            Category.user_id == user_id,
        ).first()
        if not db_category:
            raise ValueError("Category not found")
        
        # Check if new parent category exists and belongs to user
        if category_data.parent_id is not None:
            if category_data.parent_id:  # Only check if not None and not 0
                parent = db.query(Category).filter(
                    Category.id == category_data.parent_id,
                    Category.user_id == user_id,
                ).first()
                if not parent:
                    raise ValueError("Parent category not found or does not belong to user")
                
                # Prevent circular references
                if category_data.parent_id == category_id:
                    raise ValueError("Category cannot be its own parent")
        
        # Check for duplicate name if name is being changed
        if category_data.name and category_data.name != db_category.name:
            existing = db.query(Category).filter(
                Category.user_id == user_id,
                Category.name == category_data.name,
                Category.parent_id == (
                    category_data.parent_id 
                    if category_data.parent_id is not None 
                    else db_category.parent_id
                ),
                Category.id != category_id,
            ).first()
            if existing:
                raise ValueError("Category with this name already exists")
        
        # Update fields
        for field, value in category_data.model_dump(exclude_unset=True).items():
            setattr(db_category, field, value)
        
        db.commit()
        db.refresh(db_category)
        return db_category
    
    @staticmethod
    def delete_category(
        db: Session,
        user_id: int,
        category_id: int,
    ) -> bool:
        """Delete a category."""
        db_category = db.query(Category).filter(
            Category.id == category_id,
            Category.user_id == user_id,
        ).first()
        if not db_category:
            return False
        
        # Check if category has transactions
        transaction_count = db.query(Transaction).filter(
            Transaction.category_id == category_id,
        ).count()
        if transaction_count > 0:
            raise ValueError(f"Cannot delete category with {transaction_count} transactions")
        
        # Check if category has subcategories
        subcategory_count = db.query(Category).filter(
            Category.parent_id == category_id,
        ).count()
        if subcategory_count > 0:
            raise ValueError(f"Cannot delete category with {subcategory_count} subcategories")
        
        db.delete(db_category)
        db.commit()
        return True
    
    @staticmethod
    def get_categories(
        db: Session,
        user_id: int,
        include_inactive: bool = False,
    ) -> List[Category]:
        """Get all categories for a user."""
        query = db.query(Category).filter(Category.user_id == user_id)
        
        if not include_inactive:
            query = query.filter(Category.is_active == True)
        
        categories = query.order_by(
            Category.transaction_type,
            Category.parent_id,
            Category.name,
        ).all()
        
        return categories
    
    @staticmethod
    def create_default_categories(db: Session, user_id: int) -> List[Category]:
        """Create default categories for a new user."""
        default_categories = [
            # Income categories
            {"name": "Salary", "transaction_type": TransactionType.INCOME, "icon": "💰"},
            {"name": "Freelance", "transaction_type": TransactionType.INCOME, "icon": "💻"},
            {"name": "Investment", "transaction_type": TransactionType.INCOME, "icon": "📈"},
            {"name": "Other Income", "transaction_type": TransactionType.INCOME, "icon": "💵"},
            
            # Expense categories
            {"name": "Food & Dining", "transaction_type": TransactionType.EXPENSE, "icon": "🍔", "budget_amount": 500},
            {"name": "Transportation", "transaction_type": TransactionType.EXPENSE, "icon": "🚗", "budget_amount": 300},
            {"name": "Shopping", "transaction_type": TransactionType.EXPENSE, "icon": "🛍️", "budget_amount": 200},
            {"name": "Entertainment", "transaction_type": TransactionType.EXPENSE, "icon": "🎬", "budget_amount": 150},
            {"name": "Bills & Utilities", "transaction_type": TransactionType.EXPENSE, "icon": "📱", "budget_amount": 400},
            {"name": "Healthcare", "transaction_type": TransactionType.EXPENSE, "icon": "🏥", "budget_amount": 200},
            {"name": "Education", "transaction_type": TransactionType.EXPENSE, "icon": "📚", "budget_amount": 100},
            {"name": "Home", "transaction_type": TransactionType.EXPENSE, "icon": "🏠", "budget_amount": 300},
            {"name": "Insurance", "transaction_type": TransactionType.EXPENSE, "icon": "🛡️", "budget_amount": 200},
            {"name": "Personal Care", "transaction_type": TransactionType.EXPENSE, "icon": "💅", "budget_amount": 100},
            {"name": "Gifts & Donations", "transaction_type": TransactionType.EXPENSE, "icon": "🎁", "budget_amount": 100},
            {"name": "Other", "transaction_type": TransactionType.EXPENSE, "icon": "📌", "budget_amount": 100},
        ]
        
        created_categories = []
        for cat_data in default_categories:
            db_category = Category(user_id=user_id, **cat_data)
            db.add(db_category)
            created_categories.append(db_category)
        
        db.commit()
        return created_categories


class TransactionRuleService:
    """Service for managing transaction rules."""
    
    @staticmethod
    def create_rule(
        db: Session,
        user_id: int,
        rule_data: TransactionRuleCreate,
    ) -> TransactionRule:
        """Create a new transaction rule."""
        # Check if category belongs to user
        category = db.query(Category).filter(
            Category.id == rule_data.category_id,
            Category.user_id == user_id,
        ).first()
        if not category:
            raise ValueError("Category not found or does not belong to user")
        
        # Check for duplicate name
        existing = db.query(TransactionRule).filter(
            TransactionRule.user_id == user_id,
            TransactionRule.name == rule_data.name,
        ).first()
        if existing:
            raise ValueError("Rule with this name already exists")
        
        # Validate regex patterns
        if rule_data.description_pattern:
            try:
                re.compile(rule_data.description_pattern)
            except re.error as e:
                raise ValueError(f"Invalid description pattern: {e}")
        
        if rule_data.merchant_pattern:
            try:
                re.compile(rule_data.merchant_pattern)
            except re.error as e:
                raise ValueError(f"Invalid merchant pattern: {e}")
        
        # Create rule
        db_rule = TransactionRule(
            user_id=user_id,
            **rule_data.model_dump(),
        )
        db.add(db_rule)
        db.commit()
        db.refresh(db_rule)
        return db_rule
    
    @staticmethod
    def update_rule(
        db: Session,
        user_id: int,
        rule_id: int,
        rule_data: TransactionRuleUpdate,
    ) -> TransactionRule:
        """Update an existing rule."""
        # Get rule
        db_rule = db.query(TransactionRule).filter(
            TransactionRule.id == rule_id,
            TransactionRule.user_id == user_id,
        ).first()
        if not db_rule:
            raise ValueError("Rule not found")
        
        # Check if new category belongs to user
        if rule_data.category_id is not None:
            category = db.query(Category).filter(
                Category.id == rule_data.category_id,
                Category.user_id == user_id,
            ).first()
            if not category:
                raise ValueError("Category not found or does not belong to user")
        
        # Check for duplicate name if name is being changed
        if rule_data.name and rule_data.name != db_rule.name:
            existing = db.query(TransactionRule).filter(
                TransactionRule.user_id == user_id,
                TransactionRule.name == rule_data.name,
                TransactionRule.id != rule_id,
            ).first()
            if existing:
                raise ValueError("Rule with this name already exists")
        
        # Validate regex patterns
        if rule_data.description_pattern is not None:
            if rule_data.description_pattern:  # Only validate if not empty
                try:
                    re.compile(rule_data.description_pattern)
                except re.error as e:
                    raise ValueError(f"Invalid description pattern: {e}")
        
        if rule_data.merchant_pattern is not None:
            if rule_data.merchant_pattern:  # Only validate if not empty
                try:
                    re.compile(rule_data.merchant_pattern)
                except re.error as e:
                    raise ValueError(f"Invalid merchant pattern: {e}")
        
        # Update fields
        for field, value in rule_data.model_dump(exclude_unset=True).items():
            setattr(db_rule, field, value)
        
        db.commit()
        db.refresh(db_rule)
        return db_rule
    
    @staticmethod
    def delete_rule(
        db: Session,
        user_id: int,
        rule_id: int,
    ) -> bool:
        """Delete a rule."""
        db_rule = db.query(TransactionRule).filter(
            TransactionRule.id == rule_id,
            TransactionRule.user_id == user_id,
        ).first()
        if not db_rule:
            return False
        
        db.delete(db_rule)
        db.commit()
        return True
    
    @staticmethod
    def get_rules(
        db: Session,
        user_id: int,
        include_inactive: bool = False,
    ) -> List[TransactionRule]:
        """Get all rules for a user."""
        query = db.query(TransactionRule).filter(
            TransactionRule.user_id == user_id
        ).options(joinedload(TransactionRule.category))
        
        if not include_inactive:
            query = query.filter(TransactionRule.is_active == True)
        
        rules = query.order_by(
            TransactionRule.priority.desc(),
            TransactionRule.name,
        ).all()
        
        return rules
    
    @staticmethod
    def apply_rules_to_existing(
        db: Session,
        user_id: int,
        override_existing: bool = False,
    ) -> Dict[str, int]:
        """Apply rules to existing transactions."""
        results = {
            "processed": 0,
            "categorized": 0,
            "skipped": 0,
        }
        
        # Get transactions to process
        query = db.query(Transaction).filter(
            Transaction.user_id == user_id
        )
        
        if not override_existing:
            query = query.filter(Transaction.category_id == None)
        
        transactions = query.all()
        results["processed"] = len(transactions)
        
        for transaction in transactions:
            new_category_id = TransactionService._apply_rules(
                db, user_id, transaction
            )
            
            if new_category_id:
                transaction.category_id = new_category_id
                results["categorized"] += 1
            else:
                results["skipped"] += 1
        
        db.commit()
        return results