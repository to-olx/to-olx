"""
Predictive insights and forecasting endpoints.
"""

from datetime import date, timedelta
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.api.dependencies import get_current_active_user, get_db
from app.models import User, PredictiveInsight, InsightStatus
from app.schemas.insight import (
    CashflowForecastResponse,
    DashboardInsightsResponse,
    GenerateForecastRequest,
    InsightFilterParams,
    PredictiveInsightResponse,
    PredictiveInsightUpdate,
    SpendingAnomalyResponse,
    SpendingForecastResponse,
)
from app.services.insights import get_insights_service

router = APIRouter()


@router.post("/forecasts/generate", response_model=dict)
async def generate_forecasts(
    request: GenerateForecastRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Generate spending or cash flow forecasts.
    """
    insights_service = get_insights_service(db)
    
    # Determine date range
    if request.time_period == "custom":
        if not request.start_date or not request.end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date and end_date required for custom time period",
            )
        start_date = request.start_date
        end_date = request.end_date
    else:
        start_date = date.today()
        if request.time_period == "7d":
            end_date = start_date + timedelta(days=7)
        elif request.time_period == "30d":
            end_date = start_date + timedelta(days=30)
        elif request.time_period == "90d":
            end_date = start_date + timedelta(days=90)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid time period: {request.time_period}",
            )
    
    results = {}
    
    # Generate spending forecast
    if request.forecast_type in ["spending", "all"]:
        if request.category_ids:
            spending_forecasts = []
            for category_id in request.category_ids:
                forecast = await insights_service.generate_spending_forecast(
                    current_user.id,
                    start_date,
                    end_date,
                    category_id,
                )
                spending_forecasts.append(forecast)
            results["spending_forecasts"] = spending_forecasts
        else:
            forecast = await insights_service.generate_spending_forecast(
                current_user.id,
                start_date,
                end_date,
            )
            results["spending_forecast"] = forecast
    
    # Generate cash flow forecast
    if request.forecast_type in ["cashflow", "all"]:
        cashflow_forecast = await insights_service.generate_cashflow_forecast(
            current_user.id,
            end_date,
        )
        results["cashflow_forecast"] = cashflow_forecast
    
    return results


@router.get("/forecasts/spending", response_model=List[SpendingForecastResponse])
async def get_spending_forecasts(
    category_id: int = Query(None, description="Filter by category"),
    start_date: date = Query(None, description="Filter by start date"),
    end_date: date = Query(None, description="Filter by end date"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get spending forecasts for the current user.
    """
    from app.models import SpendingForecast, Category
    
    query = select(SpendingForecast).where(
        SpendingForecast.user_id == current_user.id
    ).options(selectinload(SpendingForecast.category))
    
    if category_id:
        query = query.where(SpendingForecast.category_id == category_id)
    if start_date:
        query = query.where(SpendingForecast.start_date >= start_date)
    if end_date:
        query = query.where(SpendingForecast.end_date <= end_date)
    
    query = query.order_by(SpendingForecast.created_at.desc())
    
    result = await db.execute(query)
    forecasts = result.scalars().all()
    
    # Convert to response model with category names
    response = []
    for forecast in forecasts:
        forecast_dict = {
            "id": forecast.id,
            "user_id": forecast.user_id,
            "category_id": forecast.category_id,
            "category_name": forecast.category.name if forecast.category else None,
            "start_date": forecast.start_date,
            "end_date": forecast.end_date,
            "predicted_amount": forecast.predicted_amount,
            "confidence_level": forecast.confidence_level,
            "prediction_std_dev": forecast.prediction_std_dev,
            "lower_bound": forecast.lower_bound,
            "upper_bound": forecast.upper_bound,
            "model_type": forecast.model_type,
            "model_params": forecast.model_params,
            "historical_avg": forecast.historical_avg,
            "trend_direction": forecast.trend_direction,
            "trend_percentage": forecast.trend_percentage,
            "actual_amount": forecast.actual_amount,
            "accuracy_score": forecast.accuracy_score,
            "created_at": forecast.created_at,
            "updated_at": forecast.updated_at,
        }
        response.append(SpendingForecastResponse(**forecast_dict))
    
    return response


@router.get("/forecasts/cashflow", response_model=List[CashflowForecastResponse])
async def get_cashflow_forecasts(
    forecast_date: date = Query(None, description="Filter by forecast date"),
    account_name: str = Query(None, description="Filter by account name"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get cash flow forecasts for the current user.
    """
    from app.models import CashflowForecast
    
    query = select(CashflowForecast).where(
        CashflowForecast.user_id == current_user.id
    )
    
    if forecast_date:
        query = query.where(CashflowForecast.forecast_date == forecast_date)
    if account_name:
        query = query.where(CashflowForecast.account_name == account_name)
    
    query = query.order_by(CashflowForecast.forecast_date.desc())
    
    result = await db.execute(query)
    forecasts = result.scalars().all()
    
    return forecasts


@router.get("/insights", response_model=List[PredictiveInsightResponse])
async def get_insights(
    params: InsightFilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get predictive insights for the current user.
    """
    query = select(PredictiveInsight).where(
        PredictiveInsight.user_id == current_user.id
    ).options(
        selectinload(PredictiveInsight.category),
        selectinload(PredictiveInsight.budget)
    )
    
    # Apply filters
    if params.insight_type:
        query = query.where(PredictiveInsight.insight_type == params.insight_type)
    if params.severity:
        query = query.where(PredictiveInsight.severity == params.severity)
    if params.status:
        query = query.where(PredictiveInsight.status == params.status)
    if params.category_id:
        query = query.where(PredictiveInsight.category_id == params.category_id)
    if params.budget_id:
        query = query.where(PredictiveInsight.budget_id == params.budget_id)
    if params.date_from:
        query = query.where(PredictiveInsight.created_at >= params.date_from)
    if params.date_to:
        query = query.where(PredictiveInsight.created_at <= params.date_to)
    
    # Order by severity and creation date
    query = query.order_by(
        PredictiveInsight.severity.desc(),
        PredictiveInsight.created_at.desc()
    )
    
    # Apply pagination
    query = query.limit(params.limit).offset(params.offset)
    
    result = await db.execute(query)
    insights = result.scalars().all()
    
    # Convert to response model with related names
    response = []
    for insight in insights:
        insight_dict = {
            "id": insight.id,
            "user_id": insight.user_id,
            "insight_type": insight.insight_type,
            "title": insight.title,
            "description": insight.description,
            "severity": insight.severity,
            "status": insight.status,
            "insight_data": insight.insight_data,
            "category_id": insight.category_id,
            "category_name": insight.category.name if insight.category else None,
            "budget_id": insight.budget_id,
            "budget_name": insight.budget.name if insight.budget else None,
            "transaction_ids": insight.transaction_ids,
            "recommendation": insight.recommendation,
            "action_items": insight.action_items,
            "potential_savings": insight.potential_savings,
            "risk_score": insight.risk_score,
            "valid_until": insight.valid_until,
            "acknowledged_at": insight.acknowledged_at,
            "dismissed_at": insight.dismissed_at,
            "created_at": insight.created_at,
            "updated_at": insight.updated_at,
        }
        response.append(PredictiveInsightResponse(**insight_dict))
    
    return response


@router.post("/insights/generate", response_model=List[PredictiveInsightResponse])
async def generate_insights(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Generate new predictive insights for the current user.
    """
    insights_service = get_insights_service(db)
    
    # Generate insights
    insights = await insights_service.generate_insights(current_user.id)
    
    # Convert to response model
    response = []
    for insight in insights:
        # Reload with relationships
        await db.refresh(insight, ["category", "budget"])
        
        insight_dict = {
            "id": insight.id,
            "user_id": insight.user_id,
            "insight_type": insight.insight_type,
            "title": insight.title,
            "description": insight.description,
            "severity": insight.severity,
            "status": insight.status,
            "insight_data": insight.insight_data,
            "category_id": insight.category_id,
            "category_name": insight.category.name if insight.category else None,
            "budget_id": insight.budget_id,
            "budget_name": insight.budget.name if insight.budget else None,
            "transaction_ids": insight.transaction_ids,
            "recommendation": insight.recommendation,
            "action_items": insight.action_items,
            "potential_savings": insight.potential_savings,
            "risk_score": insight.risk_score,
            "valid_until": insight.valid_until,
            "acknowledged_at": insight.acknowledged_at,
            "dismissed_at": insight.dismissed_at,
            "created_at": insight.created_at,
            "updated_at": insight.updated_at,
        }
        response.append(PredictiveInsightResponse(**insight_dict))
    
    return response


@router.patch("/insights/{insight_id}", response_model=PredictiveInsightResponse)
async def update_insight(
    insight_id: int,
    update_data: PredictiveInsightUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Update an insight (acknowledge, dismiss, etc).
    """
    # Get insight
    query = select(PredictiveInsight).where(
        and_(
            PredictiveInsight.id == insight_id,
            PredictiveInsight.user_id == current_user.id,
        )
    ).options(
        selectinload(PredictiveInsight.category),
        selectinload(PredictiveInsight.budget)
    )
    
    result = await db.execute(query)
    insight = result.scalar_one_or_none()
    
    if not insight:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insight not found",
        )
    
    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(insight, field, value)
    
    await db.commit()
    await db.refresh(insight)
    
    # Convert to response model
    insight_dict = {
        "id": insight.id,
        "user_id": insight.user_id,
        "insight_type": insight.insight_type,
        "title": insight.title,
        "description": insight.description,
        "severity": insight.severity,
        "status": insight.status,
        "insight_data": insight.insight_data,
        "category_id": insight.category_id,
        "category_name": insight.category.name if insight.category else None,
        "budget_id": insight.budget_id,
        "budget_name": insight.budget.name if insight.budget else None,
        "transaction_ids": insight.transaction_ids,
        "recommendation": insight.recommendation,
        "action_items": insight.action_items,
        "potential_savings": insight.potential_savings,
        "risk_score": insight.risk_score,
        "valid_until": insight.valid_until,
        "acknowledged_at": insight.acknowledged_at,
        "dismissed_at": insight.dismissed_at,
        "created_at": insight.created_at,
        "updated_at": insight.updated_at,
    }
    
    return PredictiveInsightResponse(**insight_dict)


@router.get("/anomalies", response_model=List[SpendingAnomalyResponse])
async def get_anomalies(
    days: int = Query(7, ge=1, le=90, description="Days to look back"),
    confirmed: bool = Query(None, description="Filter by confirmation status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get detected spending anomalies.
    """
    insights_service = get_insights_service(db)
    
    # Detect new anomalies
    anomalies = await insights_service.detect_spending_anomalies(current_user.id, days)
    
    # Also get existing anomalies from database
    from app.models import SpendingAnomaly, Transaction
    
    query = select(SpendingAnomaly).where(
        and_(
            SpendingAnomaly.user_id == current_user.id,
            SpendingAnomaly.created_at >= date.today() - timedelta(days=days),
        )
    ).options(selectinload(SpendingAnomaly.transaction))
    
    if confirmed is not None:
        query = query.where(SpendingAnomaly.is_confirmed == confirmed)
    
    result = await db.execute(query)
    existing_anomalies = result.scalars().all()
    
    # Combine and deduplicate
    all_anomalies = list(existing_anomalies)
    existing_ids = {a.transaction_id for a in existing_anomalies}
    
    for anomaly in anomalies:
        if anomaly.transaction_id not in existing_ids:
            all_anomalies.append(anomaly)
    
    # Convert to response model
    response = []
    for anomaly in all_anomalies:
        if anomaly.transaction:
            transaction_description = anomaly.transaction.description
            transaction_date = anomaly.transaction.transaction_date
            merchant = anomaly.transaction.merchant
            category_name = anomaly.transaction.category.name if anomaly.transaction.category else None
        else:
            # Load transaction if not already loaded
            t_query = select(Transaction).where(Transaction.id == anomaly.transaction_id)
            t_result = await db.execute(t_query)
            transaction = t_result.scalar_one_or_none()
            
            transaction_description = transaction.description if transaction else None
            transaction_date = transaction.transaction_date if transaction else None
            merchant = transaction.merchant if transaction else None
            category_name = transaction.category.name if transaction and transaction.category else None
        
        anomaly_dict = {
            "id": anomaly.id,
            "user_id": anomaly.user_id,
            "transaction_id": anomaly.transaction_id,
            "anomaly_score": anomaly.anomaly_score,
            "anomaly_type": anomaly.anomaly_type,
            "expected_range_min": anomaly.expected_range_min,
            "expected_range_max": anomaly.expected_range_max,
            "actual_amount": anomaly.actual_amount,
            "detection_method": anomaly.detection_method,
            "confidence": anomaly.confidence,
            "context_data": anomaly.context_data,
            "is_confirmed": anomaly.is_confirmed,
            "user_notes": anomaly.user_notes,
            "created_at": anomaly.created_at,
            "transaction_description": transaction_description,
            "transaction_date": transaction_date,
            "merchant": merchant,
            "category_name": category_name,
        }
        response.append(SpendingAnomalyResponse(**anomaly_dict))
    
    # Sort by score descending
    response.sort(key=lambda x: x.anomaly_score, reverse=True)
    
    return response


@router.get("/dashboard", response_model=DashboardInsightsResponse)
async def get_dashboard_insights(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get dashboard insights summary.
    """
    insights_service = get_insights_service(db)
    
    # Get dashboard data
    dashboard_data = await insights_service.get_dashboard_insights(current_user.id)
    
    return DashboardInsightsResponse(**dashboard_data)