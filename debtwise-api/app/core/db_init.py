"""
Database initialization module.
Create tables and initial data.
"""

import asyncio
import logging

from sqlalchemy import text

from app.core.database import engine
from app.models.base import Base
# Import all models to ensure they are registered
from app.models.user import User
from app.models.debt import Debt, DebtPayment
from app.models.transaction import Transaction, Category, TransactionRule
from app.models.budget import Budget, BudgetPeriod, BudgetAlert

logger = logging.getLogger(__name__)


async def init_db() -> None:
    """Initialize database by creating all tables."""
    try:
        async with engine.begin() as conn:
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
            
            # Verify tables exist
            result = await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' "
                    "ORDER BY table_name"
                )
            )
            tables = [row[0] for row in result]
            logger.info(f"Tables in database: {tables}")
            
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise


async def drop_db() -> None:
    """Drop all database tables. Use with caution!"""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            logger.info("Database tables dropped successfully")
    except Exception as e:
        logger.error(f"Error dropping database tables: {e}")
        raise


if __name__ == "__main__":
    # Run initialization when module is called directly
    logging.basicConfig(level=logging.INFO)
    asyncio.run(init_db())