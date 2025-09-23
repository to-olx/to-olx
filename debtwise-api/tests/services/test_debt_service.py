"""
Tests for debt service functionality.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debt import Debt, DebtPayment, DebtStatus, DebtType
from app.models.user import User
from app.schemas.debt import DebtCreate, DebtUpdate, DebtPaymentCreate, PayoffStrategy
from app.services.debt import DebtService


@pytest.mark.asyncio
async def test_calculate_payoff_time(db_session: AsyncSession) -> None:
    """Test debt payoff time calculation."""
    service = DebtService(db_session)
    
    # Test normal payoff
    months, interest = service.calculate_payoff_time(
        balance=Decimal("1000"),
        interest_rate=Decimal("12"),  # 1% monthly
        payment_amount=Decimal("100"),
    )
    
    assert months == 11  # Should take 11 months
    assert interest > 0
    assert interest < Decimal("100")  # Total interest should be reasonable
    
    # Test payment equals interest (never pays off)
    months, interest = service.calculate_payoff_time(
        balance=Decimal("10000"),
        interest_rate=Decimal("12"),
        payment_amount=Decimal("100"),  # Exactly 1% of 10000
    )
    
    assert months == -1
    assert interest == Decimal("-1")
    
    # Test very high payment (pays off in 1 month)
    months, interest = service.calculate_payoff_time(
        balance=Decimal("100"),
        interest_rate=Decimal("12"),
        payment_amount=Decimal("200"),
    )
    
    assert months == 1
    assert interest < Decimal("2")  # Very little interest


@pytest.mark.asyncio
async def test_calculate_payment_split(db_session: AsyncSession) -> None:
    """Test payment split calculation between principal and interest."""
    service = DebtService(db_session)
    
    # Test normal payment
    principal, interest = service._calculate_payment_split(
        balance=Decimal("1000"),
        annual_rate=Decimal("12"),  # 1% monthly
        payment=Decimal("50"),
    )
    
    assert interest == Decimal("10.00")  # 1% of 1000
    assert principal == Decimal("40.00")  # 50 - 10
    
    # Test payment less than interest
    principal, interest = service._calculate_payment_split(
        balance=Decimal("10000"),
        annual_rate=Decimal("24"),  # 2% monthly
        payment=Decimal("100"),
    )
    
    assert interest == Decimal("100.00")  # Payment all goes to interest
    assert principal == Decimal("0.00")
    
    # Test payment exceeds balance
    principal, interest = service._calculate_payment_split(
        balance=Decimal("50"),
        annual_rate=Decimal("12"),
        payment=Decimal("100"),
    )
    
    assert principal == Decimal("50.00")  # Can't pay more than balance
    assert interest == Decimal("50.00")  # Remainder


@pytest.mark.asyncio
async def test_create_and_get_debt(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test creating and retrieving a debt."""
    service = DebtService(db_session)
    
    debt_data = DebtCreate(
        name="Test Credit Card",
        debt_type=DebtType.CREDIT_CARD,
        original_amount=Decimal("5000"),
        current_balance=Decimal("4000"),
        interest_rate=Decimal("18.99"),
        minimum_payment=Decimal("120"),
        due_date=15,
    )
    
    # Create debt
    debt = await service.create_debt(test_user.id, debt_data)
    assert debt.id is not None
    assert debt.name == "Test Credit Card"
    assert debt.user_id == test_user.id
    
    # Get debt
    retrieved = await service.get_debt(debt.id, test_user.id)
    assert retrieved is not None
    assert retrieved.id == debt.id
    
    # Try to get debt with wrong user ID
    wrong_user = await service.get_debt(debt.id, test_user.id + 1)
    assert wrong_user is None


@pytest.mark.asyncio
async def test_update_debt(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test updating a debt."""
    service = DebtService(db_session)
    
    # Create debt
    debt = Debt(
        user_id=test_user.id,
        name="Original Name",
        debt_type=DebtType.PERSONAL_LOAN,
        original_amount=Decimal("10000"),
        current_balance=Decimal("8000"),
        interest_rate=Decimal("10.00"),
        minimum_payment=Decimal("200"),
    )
    db_session.add(debt)
    await db_session.commit()
    await db_session.refresh(debt)
    
    # Update debt
    update_data = DebtUpdate(
        name="Updated Name",
        current_balance=Decimal("7500"),
        status=DebtStatus.ACTIVE,
    )
    
    updated = await service.update_debt(debt.id, test_user.id, update_data)
    assert updated is not None
    assert updated.name == "Updated Name"
    assert updated.current_balance == Decimal("7500")
    assert updated.interest_rate == Decimal("10.00")  # Unchanged


@pytest.mark.asyncio
async def test_record_payment_updates_balance(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test that recording a payment updates the debt balance correctly."""
    service = DebtService(db_session)
    
    # Create debt
    debt = Debt(
        user_id=test_user.id,
        name="Test Debt",
        debt_type=DebtType.CREDIT_CARD,
        original_amount=Decimal("5000"),
        current_balance=Decimal("2000"),
        interest_rate=Decimal("18.00"),  # 1.5% monthly
        minimum_payment=Decimal("60"),
    )
    db_session.add(debt)
    await db_session.commit()
    await db_session.refresh(debt)
    
    # Record payment
    payment_data = DebtPaymentCreate(
        debt_id=debt.id,
        amount=Decimal("500"),
        payment_date=date.today(),
        is_extra_payment=True,
    )
    
    payment = await service.record_payment(test_user.id, payment_data)
    assert payment is not None
    
    # Check payment details
    assert payment.amount == Decimal("500")
    assert payment.interest_amount == Decimal("30.00")  # 2000 * 0.015
    assert payment.principal_amount == Decimal("470.00")  # 500 - 30
    
    # Check updated balance
    await db_session.refresh(debt)
    assert debt.current_balance == Decimal("1530.00")  # 2000 - 470


@pytest.mark.asyncio
async def test_payoff_debt_with_payment(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test paying off a debt completely."""
    service = DebtService(db_session)
    
    # Create small debt
    debt = Debt(
        user_id=test_user.id,
        name="Small Debt",
        debt_type=DebtType.PERSONAL_LOAN,
        original_amount=Decimal("500"),
        current_balance=Decimal("100"),
        interest_rate=Decimal("12.00"),
        minimum_payment=Decimal("25"),
    )
    db_session.add(debt)
    await db_session.commit()
    await db_session.refresh(debt)
    
    # Make payment to pay off debt
    payment_data = DebtPaymentCreate(
        debt_id=debt.id,
        amount=Decimal("101"),  # Slightly more than balance + interest
        payment_date=date.today(),
    )
    
    await service.record_payment(test_user.id, payment_data)
    
    # Check debt is paid off
    await db_session.refresh(debt)
    assert debt.current_balance == Decimal("0.00")
    assert debt.status == DebtStatus.PAID_OFF


@pytest.mark.asyncio
async def test_get_debt_summary(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test getting debt summary statistics."""
    service = DebtService(db_session)
    
    # Create multiple debts with payments
    active_debt = Debt(
        user_id=test_user.id,
        name="Active Debt",
        debt_type=DebtType.CREDIT_CARD,
        original_amount=Decimal("5000"),
        current_balance=Decimal("3000"),
        interest_rate=Decimal("20.00"),
        minimum_payment=Decimal("100"),
        status=DebtStatus.ACTIVE,
    )
    
    paid_debt = Debt(
        user_id=test_user.id,
        name="Paid Off Debt",
        debt_type=DebtType.AUTO_LOAN,
        original_amount=Decimal("15000"),
        current_balance=Decimal("0"),
        interest_rate=Decimal("5.00"),
        minimum_payment=Decimal("0"),
        status=DebtStatus.PAID_OFF,
    )
    
    db_session.add_all([active_debt, paid_debt])
    await db_session.commit()
    
    # Add some payments
    payment = DebtPayment(
        debt_id=active_debt.id,
        user_id=test_user.id,
        amount=Decimal("500"),
        payment_date=date.today(),
        principal_amount=Decimal("450"),
        interest_amount=Decimal("50"),
    )
    db_session.add(payment)
    await db_session.commit()
    
    # Get summary
    summary = await service.get_debt_summary(test_user.id)
    
    assert summary.total_debt == Decimal("3000")
    assert summary.total_original_debt == Decimal("20000")
    assert summary.total_paid == Decimal("500")
    assert summary.total_interest_paid == Decimal("50")
    assert summary.active_debts_count == 1
    assert summary.paid_off_debts_count == 1
    assert summary.average_interest_rate == Decimal("20.00")
    assert summary.total_minimum_payment == Decimal("100")


@pytest.mark.asyncio
async def test_snowball_strategy_sorting(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test that snowball strategy sorts by balance (smallest first)."""
    service = DebtService(db_session)
    
    # Create debts with different balances
    large_debt = Debt(
        user_id=test_user.id,
        name="Large Debt",
        debt_type=DebtType.STUDENT_LOAN,
        original_amount=Decimal("20000"),
        current_balance=Decimal("15000"),
        interest_rate=Decimal("6.00"),
        minimum_payment=Decimal("200"),
    )
    
    small_debt = Debt(
        user_id=test_user.id,
        name="Small Debt",
        debt_type=DebtType.CREDIT_CARD,
        original_amount=Decimal("3000"),
        current_balance=Decimal("1000"),  # Smallest
        interest_rate=Decimal("22.00"),  # Highest rate
        minimum_payment=Decimal("50"),
    )
    
    medium_debt = Debt(
        user_id=test_user.id,
        name="Medium Debt",
        debt_type=DebtType.PERSONAL_LOAN,
        original_amount=Decimal("8000"),
        current_balance=Decimal("5000"),
        interest_rate=Decimal("12.00"),
        minimum_payment=Decimal("150"),
    )
    
    db_session.add_all([large_debt, small_debt, medium_debt])
    await db_session.commit()
    
    # Generate snowball plan
    plan = await service.generate_payoff_plan(
        user_id=test_user.id,
        strategy=PayoffStrategy.SNOWBALL,
        extra_payment=Decimal("200"),
    )
    
    # Check order (smallest balance first)
    assert len(plan["debts"]) == 3
    assert plan["debts"][0]["debt_name"] == "Small Debt"
    assert plan["debts"][1]["debt_name"] == "Medium Debt"
    assert plan["debts"][2]["debt_name"] == "Large Debt"


@pytest.mark.asyncio
async def test_avalanche_strategy_sorting(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Test that avalanche strategy sorts by interest rate (highest first)."""
    service = DebtService(db_session)
    
    # Create debts with different interest rates
    low_rate = Debt(
        user_id=test_user.id,
        name="Low Rate Debt",
        debt_type=DebtType.MORTGAGE,
        original_amount=Decimal("200000"),
        current_balance=Decimal("180000"),
        interest_rate=Decimal("3.50"),  # Lowest rate
        minimum_payment=Decimal("1200"),
    )
    
    high_rate = Debt(
        user_id=test_user.id,
        name="High Rate Debt",
        debt_type=DebtType.CREDIT_CARD,
        original_amount=Decimal("5000"),
        current_balance=Decimal("4000"),
        interest_rate=Decimal("24.99"),  # Highest rate
        minimum_payment=Decimal("120"),
    )
    
    medium_rate = Debt(
        user_id=test_user.id,
        name="Medium Rate Debt",
        debt_type=DebtType.PERSONAL_LOAN,
        original_amount=Decimal("10000"),
        current_balance=Decimal("7000"),
        interest_rate=Decimal("12.00"),
        minimum_payment=Decimal("250"),
    )
    
    db_session.add_all([low_rate, high_rate, medium_rate])
    await db_session.commit()
    
    # Generate avalanche plan
    plan = await service.generate_payoff_plan(
        user_id=test_user.id,
        strategy=PayoffStrategy.AVALANCHE,
        extra_payment=Decimal("300"),
    )
    
    # Check order (highest rate first)
    assert len(plan["debts"]) == 3
    assert plan["debts"][0]["debt_name"] == "High Rate Debt"
    assert plan["debts"][1]["debt_name"] == "Medium Rate Debt"
    assert plan["debts"][2]["debt_name"] == "Low Rate Debt"


@pytest.mark.asyncio
async def test_interest_calculator_monthly_breakdown(
    db_session: AsyncSession,
) -> None:
    """Test interest calculator with monthly breakdown."""
    service = DebtService(db_session)
    
    result = service.calculate_interest_breakdown(
        principal=Decimal("5000"),
        interest_rate=Decimal("15.00"),  # 1.25% monthly
        payment_amount=Decimal("200"),
    )
    
    assert "error" not in result
    assert result["months_to_payoff"] > 0
    assert len(result["monthly_breakdown"]) == 12
    
    # Verify first month
    first = result["monthly_breakdown"][0]
    assert first["month"] == 1
    assert abs(first["interest"] - 62.50) < 0.01  # 5000 * 0.0125
    assert abs(first["principal"] - 137.50) < 0.01  # 200 - 62.50
    
    # Verify decreasing balance
    for i in range(1, len(result["monthly_breakdown"])):
        assert result["monthly_breakdown"][i]["remaining_balance"] < \
               result["monthly_breakdown"][i-1]["remaining_balance"]