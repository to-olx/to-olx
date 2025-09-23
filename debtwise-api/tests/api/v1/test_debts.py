"""
Tests for debt management endpoints.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debt import Debt, DebtStatus, DebtType
from app.models.user import User
from app.schemas.debt import PayoffStrategy


@pytest.mark.asyncio
async def test_create_debt(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict,
) -> None:
    """Test creating a new debt."""
    debt_data = {
        "name": "Credit Card",
        "description": "Chase Visa",
        "debt_type": "credit_card",
        "original_amount": "5000.00",
        "current_balance": "4500.00",
        "interest_rate": "18.99",
        "minimum_payment": "150.00",
        "due_date": 15,
    }
    
    response = await client.post(
        "/api/v1/debts/",
        json=debt_data,
        headers=auth_headers,
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Credit Card"
    assert data["debt_type"] == "credit_card"
    assert Decimal(data["current_balance"]) == Decimal("4500.00")
    assert data["user_id"] == test_user.id


@pytest.mark.asyncio
async def test_get_user_debts(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict,
) -> None:
    """Test getting all user debts."""
    # Create test debts
    debts = [
        Debt(
            user_id=test_user.id,
            name="Credit Card 1",
            debt_type=DebtType.CREDIT_CARD,
            original_amount=Decimal("5000"),
            current_balance=Decimal("3000"),
            interest_rate=Decimal("18.99"),
            minimum_payment=Decimal("100"),
        ),
        Debt(
            user_id=test_user.id,
            name="Student Loan",
            debt_type=DebtType.STUDENT_LOAN,
            original_amount=Decimal("20000"),
            current_balance=Decimal("15000"),
            interest_rate=Decimal("6.50"),
            minimum_payment=Decimal("250"),
        ),
    ]
    
    for debt in debts:
        db_session.add(debt)
    await db_session.commit()
    
    response = await client.get("/api/v1/debts/", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Credit Card 1"
    assert data[1]["name"] == "Student Loan"


@pytest.mark.asyncio
async def test_get_debt_by_id(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict,
) -> None:
    """Test getting a specific debt by ID."""
    # Create test debt
    debt = Debt(
        user_id=test_user.id,
        name="Auto Loan",
        debt_type=DebtType.AUTO_LOAN,
        original_amount=Decimal("25000"),
        current_balance=Decimal("20000"),
        interest_rate=Decimal("5.99"),
        minimum_payment=Decimal("450"),
    )
    db_session.add(debt)
    await db_session.commit()
    await db_session.refresh(debt)
    
    response = await client.get(f"/api/v1/debts/{debt.id}", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == debt.id
    assert data["name"] == "Auto Loan"
    assert Decimal(data["current_balance"]) == Decimal("20000")


@pytest.mark.asyncio
async def test_update_debt(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict,
) -> None:
    """Test updating a debt."""
    # Create test debt
    debt = Debt(
        user_id=test_user.id,
        name="Personal Loan",
        debt_type=DebtType.PERSONAL_LOAN,
        original_amount=Decimal("10000"),
        current_balance=Decimal("8000"),
        interest_rate=Decimal("12.00"),
        minimum_payment=Decimal("300"),
    )
    db_session.add(debt)
    await db_session.commit()
    await db_session.refresh(debt)
    
    update_data = {
        "current_balance": "7500.00",
        "minimum_payment": "280.00",
    }
    
    response = await client.patch(
        f"/api/v1/debts/{debt.id}",
        json=update_data,
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["current_balance"]) == Decimal("7500.00")
    assert Decimal(data["minimum_payment"]) == Decimal("280.00")


@pytest.mark.asyncio
async def test_delete_debt(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict,
) -> None:
    """Test deleting (soft delete) a debt."""
    # Create test debt
    debt = Debt(
        user_id=test_user.id,
        name="Medical Debt",
        debt_type=DebtType.MEDICAL_DEBT,
        original_amount=Decimal("2000"),
        current_balance=Decimal("1500"),
        interest_rate=Decimal("0"),
        minimum_payment=Decimal("50"),
    )
    db_session.add(debt)
    await db_session.commit()
    await db_session.refresh(debt)
    
    response = await client.delete(
        f"/api/v1/debts/{debt.id}",
        headers=auth_headers,
    )
    
    assert response.status_code == 204
    
    # Verify debt is soft deleted
    await db_session.refresh(debt)
    assert debt.is_active is False


@pytest.mark.asyncio
async def test_record_payment(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict,
) -> None:
    """Test recording a payment towards a debt."""
    # Create test debt
    debt = Debt(
        user_id=test_user.id,
        name="Credit Card",
        debt_type=DebtType.CREDIT_CARD,
        original_amount=Decimal("5000"),
        current_balance=Decimal("3000"),
        interest_rate=Decimal("18.00"),  # 1.5% monthly
        minimum_payment=Decimal("100"),
    )
    db_session.add(debt)
    await db_session.commit()
    await db_session.refresh(debt)
    
    payment_data = {
        "debt_id": debt.id,
        "amount": "500.00",
        "payment_date": date.today().isoformat(),
        "notes": "Extra payment",
        "is_extra_payment": True,
    }
    
    response = await client.post(
        "/api/v1/debts/payments",
        json=payment_data,
        headers=auth_headers,
    )
    
    assert response.status_code == 201
    data = response.json()
    assert Decimal(data["amount"]) == Decimal("500.00")
    assert data["debt_id"] == debt.id
    assert data["is_extra_payment"] is True
    
    # Verify debt balance updated
    await db_session.refresh(debt)
    # Interest for month: 3000 * 0.18 / 12 = 45
    # Principal: 500 - 45 = 455
    # New balance: 3000 - 455 = 2545
    assert debt.current_balance == Decimal("2545.00")


@pytest.mark.asyncio
async def test_get_debt_summary(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict,
) -> None:
    """Test getting debt summary statistics."""
    # Create test debts
    debts = [
        Debt(
            user_id=test_user.id,
            name="Credit Card",
            debt_type=DebtType.CREDIT_CARD,
            original_amount=Decimal("5000"),
            current_balance=Decimal("3000"),
            interest_rate=Decimal("20.00"),
            minimum_payment=Decimal("100"),
            status=DebtStatus.ACTIVE,
        ),
        Debt(
            user_id=test_user.id,
            name="Auto Loan",
            debt_type=DebtType.AUTO_LOAN,
            original_amount=Decimal("20000"),
            current_balance=Decimal("0"),
            interest_rate=Decimal("5.00"),
            minimum_payment=Decimal("0"),
            status=DebtStatus.PAID_OFF,
        ),
    ]
    
    for debt in debts:
        db_session.add(debt)
    await db_session.commit()
    
    response = await client.get("/api/v1/debts/summary", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["total_debt"]) == Decimal("3000")
    assert Decimal(data["total_original_debt"]) == Decimal("25000")
    assert data["active_debts_count"] == 1
    assert data["paid_off_debts_count"] == 1
    assert Decimal(data["average_interest_rate"]) == Decimal("20.00")


@pytest.mark.asyncio
async def test_generate_snowball_payoff_plan(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict,
) -> None:
    """Test generating a snowball payoff plan."""
    # Create test debts (snowball pays smallest balance first)
    debts = [
        Debt(
            user_id=test_user.id,
            name="Small Debt",
            debt_type=DebtType.PERSONAL_LOAN,
            original_amount=Decimal("2000"),
            current_balance=Decimal("1000"),  # Smallest balance
            interest_rate=Decimal("15.00"),
            minimum_payment=Decimal("50"),
        ),
        Debt(
            user_id=test_user.id,
            name="Large Debt",
            debt_type=DebtType.CREDIT_CARD,
            original_amount=Decimal("5000"),
            current_balance=Decimal("3000"),
            interest_rate=Decimal("20.00"),  # Higher rate
            minimum_payment=Decimal("100"),
        ),
    ]
    
    for debt in debts:
        db_session.add(debt)
    await db_session.commit()
    
    plan_data = {
        "strategy": PayoffStrategy.SNOWBALL,
        "extra_monthly_payment": "100.00",
    }
    
    response = await client.post(
        "/api/v1/debts/payoff-plan",
        json=plan_data,
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["strategy"] == PayoffStrategy.SNOWBALL
    assert len(data["debts"]) == 2
    # Small debt should be paid off first
    assert data["debts"][0]["debt_name"] == "Small Debt"
    assert data["debts"][0]["payoff_order"] == 1


@pytest.mark.asyncio
async def test_generate_avalanche_payoff_plan(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict,
) -> None:
    """Test generating an avalanche payoff plan."""
    # Create test debts (avalanche pays highest interest rate first)
    debts = [
        Debt(
            user_id=test_user.id,
            name="Low Interest Debt",
            debt_type=DebtType.AUTO_LOAN,
            original_amount=Decimal("10000"),
            current_balance=Decimal("8000"),
            interest_rate=Decimal("5.00"),  # Lower rate
            minimum_payment=Decimal("200"),
        ),
        Debt(
            user_id=test_user.id,
            name="High Interest Debt",
            debt_type=DebtType.CREDIT_CARD,
            original_amount=Decimal("3000"),
            current_balance=Decimal("2000"),
            interest_rate=Decimal("22.00"),  # Highest rate
            minimum_payment=Decimal("80"),
        ),
    ]
    
    for debt in debts:
        db_session.add(debt)
    await db_session.commit()
    
    plan_data = {
        "strategy": PayoffStrategy.AVALANCHE,
        "extra_monthly_payment": "200.00",
    }
    
    response = await client.post(
        "/api/v1/debts/payoff-plan",
        json=plan_data,
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["strategy"] == PayoffStrategy.AVALANCHE
    assert len(data["debts"]) == 2
    # High interest debt should be paid off first
    assert data["debts"][0]["debt_name"] == "High Interest Debt"
    assert data["debts"][0]["payoff_order"] == 1


@pytest.mark.asyncio
async def test_interest_calculator(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
) -> None:
    """Test the interest calculator."""
    calc_data = {
        "principal": "10000.00",
        "interest_rate": "12.00",  # 12% APR = 1% monthly
        "payment_amount": "300.00",
    }
    
    response = await client.post(
        "/api/v1/debts/calculator/interest",
        json=calc_data,
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["months_to_payoff"] > 0
    assert Decimal(data["total_interest"]) > 0
    assert len(data["monthly_breakdown"]) == 12
    
    # Check first month breakdown
    first_month = data["monthly_breakdown"][0]
    assert first_month["month"] == 1
    assert first_month["payment"] == 300.0
    # Interest: 10000 * 0.12 / 12 = 100
    assert abs(first_month["interest"] - 100.0) < 0.01
    # Principal: 300 - 100 = 200
    assert abs(first_month["principal"] - 200.0) < 0.01


@pytest.mark.asyncio
async def test_interest_calculator_payment_too_low(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
) -> None:
    """Test interest calculator with payment too low to cover interest."""
    calc_data = {
        "principal": "10000.00",
        "interest_rate": "24.00",  # 2% monthly
        "payment_amount": "150.00",  # Less than $200 monthly interest
    }
    
    response = await client.post(
        "/api/v1/debts/calculator/interest",
        json=calc_data,
        headers=auth_headers,
    )
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_debt_access_control(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict,
) -> None:
    """Test that users can only access their own debts."""
    # Create another user
    other_user = User(
        email="other@example.com",
        username="otheruser",
        hashed_password="hashed",
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)
    
    # Create debt for other user
    other_debt = Debt(
        user_id=other_user.id,
        name="Other User's Debt",
        debt_type=DebtType.CREDIT_CARD,
        original_amount=Decimal("1000"),
        current_balance=Decimal("500"),
        interest_rate=Decimal("15.00"),
        minimum_payment=Decimal("25"),
    )
    db_session.add(other_debt)
    await db_session.commit()
    await db_session.refresh(other_debt)
    
    # Try to access other user's debt
    response = await client.get(
        f"/api/v1/debts/{other_debt.id}",
        headers=auth_headers,
    )
    
    assert response.status_code == 404  # Should not find debt