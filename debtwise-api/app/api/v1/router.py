"""
Main API router for v1 endpoints.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, users, analytics, budgets, debts, transactions, insights

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(debts.router, prefix="/debts", tags=["debts"])
api_router.include_router(transactions.router, prefix="/spending", tags=["spending"])
api_router.include_router(budgets.router, prefix="/budgets", tags=["budgets"])
api_router.include_router(insights.router, prefix="/insights", tags=["insights"])