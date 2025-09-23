"""
Example script demonstrating budget management in DebtWise.

This script shows how to:
1. Create budgets with different period types
2. Set up budget alerts
3. Process budget rollovers
4. Get budget summaries and analytics
"""

import asyncio
import json
from datetime import date, timedelta
from decimal import Decimal

import httpx
from pydantic import BaseModel


class BudgetExample:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()
        self.token = None
        
    async def close(self):
        await self.client.aclose()
        
    async def authenticate(self, username: str, password: str):
        """Authenticate and get access token."""
        response = await self.client.post(
            f"{self.base_url}/api/v1/auth/token",
            data={"username": username, "password": password}
        )
        response.raise_for_status()
        data = response.json()
        self.token = data["access_token"]
        self.client.headers.update({"Authorization": f"Bearer {self.token}"})
        print(f"✓ Authenticated as {username}")
        
    async def create_category(self, name: str, transaction_type: str = "expense"):
        """Create a spending category."""
        response = await self.client.post(
            f"{self.base_url}/api/v1/spending/categories",
            json={
                "name": name,
                "transaction_type": transaction_type,
                "is_active": True
            }
        )
        response.raise_for_status()
        return response.json()
        
    async def create_budget(self, budget_data: dict):
        """Create a new budget."""
        response = await self.client.post(
            f"{self.base_url}/api/v1/budgets/budgets",
            json=budget_data
        )
        response.raise_for_status()
        return response.json()
        
    async def create_budget_alert(self, budget_id: int, threshold: int):
        """Create a budget alert."""
        response = await self.client.post(
            f"{self.base_url}/api/v1/budgets/budgets/{budget_id}/alerts",
            json={
                "threshold_percentage": threshold,
                "alert_message": f"Budget has reached {threshold}% of limit",
                "is_enabled": True,
                "send_email": True
            }
        )
        response.raise_for_status()
        return response.json()
        
    async def add_transaction(self, transaction_data: dict):
        """Add a transaction."""
        response = await self.client.post(
            f"{self.base_url}/api/v1/spending/transactions",
            json=transaction_data
        )
        response.raise_for_status()
        return response.json()
        
    async def get_budget_summary(self, budget_id: int):
        """Get budget summary."""
        response = await self.client.get(
            f"{self.base_url}/api/v1/budgets/budgets/{budget_id}/summary"
        )
        response.raise_for_status()
        return response.json()
        
    async def get_budget_overview(self):
        """Get overall budget overview."""
        response = await self.client.get(
            f"{self.base_url}/api/v1/budgets/budgets/summary/overview"
        )
        response.raise_for_status()
        return response.json()
        
    async def process_rollover(self, budget_id: int):
        """Process budget rollover."""
        response = await self.client.post(
            f"{self.base_url}/api/v1/budgets/budgets/rollover",
            json={"budget_id": budget_id}
        )
        response.raise_for_status()
        return response.json()


async def run_budget_examples():
    """Run budget management examples."""
    example = BudgetExample()
    
    try:
        # 1. Authenticate (you'll need to create a user first)
        print("\n1. AUTHENTICATION")
        await example.authenticate("testuser", "testpass123")
        
        # 2. Create categories
        print("\n2. CREATING CATEGORIES")
        groceries = await example.create_category("Groceries")
        print(f"✓ Created category: {groceries['name']} (ID: {groceries['id']})")
        
        entertainment = await example.create_category("Entertainment")
        print(f"✓ Created category: {entertainment['name']} (ID: {entertainment['id']})")
        
        utilities = await example.create_category("Utilities")
        print(f"✓ Created category: {utilities['name']} (ID: {utilities['id']})")
        
        # 3. Create budgets with different settings
        print("\n3. CREATING BUDGETS")
        
        # Monthly budget with rollover
        groceries_budget = await example.create_budget({
            "name": "Monthly Groceries",
            "description": "Budget for grocery shopping",
            "category_id": groceries["id"],
            "period_type": "monthly",
            "start_date": date.today().isoformat(),
            "amount": "500.00",
            "allow_rollover": True,
            "max_rollover_periods": 3,
            "max_rollover_amount": "150.00",
            "is_active": True
        })
        print(f"✓ Created budget: {groceries_budget['name']}")
        
        # Weekly entertainment budget without rollover
        entertainment_budget = await example.create_budget({
            "name": "Weekly Entertainment",
            "description": "Budget for entertainment and dining out",
            "category_id": entertainment["id"],
            "period_type": "weekly",
            "start_date": date.today().isoformat(),
            "amount": "100.00",
            "allow_rollover": False,
            "is_active": True
        })
        print(f"✓ Created budget: {entertainment_budget['name']}")
        
        # Total monthly budget (across all categories)
        total_budget = await example.create_budget({
            "name": "Total Monthly Budget",
            "description": "Overall spending limit",
            "category_id": None,  # No specific category
            "period_type": "monthly",
            "start_date": date.today().isoformat(),
            "amount": "2000.00",
            "allow_rollover": False,
            "is_active": True
        })
        print(f"✓ Created budget: {total_budget['name']}")
        
        # 4. Set up budget alerts
        print("\n4. SETTING UP ALERTS")
        
        # Alert at 80% for groceries
        await example.create_budget_alert(groceries_budget["id"], 80)
        print(f"✓ Created 80% alert for {groceries_budget['name']}")
        
        # Alert at 90% for total budget
        await example.create_budget_alert(total_budget["id"], 90)
        print(f"✓ Created 90% alert for {total_budget['name']}")
        
        # 5. Add some transactions
        print("\n5. ADDING TRANSACTIONS")
        
        # Grocery transactions
        await example.add_transaction({
            "amount": "125.50",
            "transaction_date": date.today().isoformat(),
            "description": "Weekly grocery shopping",
            "transaction_type": "expense",
            "category_id": groceries["id"],
            "merchant": "SuperMart"
        })
        print("✓ Added grocery transaction: $125.50")
        
        await example.add_transaction({
            "amount": "45.25",
            "transaction_date": (date.today() - timedelta(days=2)).isoformat(),
            "description": "Fruit and vegetables",
            "transaction_type": "expense",
            "category_id": groceries["id"],
            "merchant": "Fresh Market"
        })
        print("✓ Added grocery transaction: $45.25")
        
        # Entertainment transaction
        await example.add_transaction({
            "amount": "65.00",
            "transaction_date": date.today().isoformat(),
            "description": "Dinner with friends",
            "transaction_type": "expense",
            "category_id": entertainment["id"],
            "merchant": "The Bistro"
        })
        print("✓ Added entertainment transaction: $65.00")
        
        # 6. Get budget summaries
        print("\n6. BUDGET SUMMARIES")
        
        # Individual budget summary
        grocery_summary = await example.get_budget_summary(groceries_budget["id"])
        print(f"\n{grocery_summary['budget_name']}:")
        print(f"  - Total Budget: ${grocery_summary['total_budgeted']}")
        print(f"  - Spent: ${grocery_summary['total_spent']} ({grocery_summary['percentage_used']:.1f}%)")
        print(f"  - Remaining: ${grocery_summary['total_remaining']}")
        print(f"  - Days Remaining: {grocery_summary['days_remaining']}")
        
        if grocery_summary.get('projected_end_of_period'):
            print(f"  - Projected End of Period: ${grocery_summary['projected_end_of_period']}")
        
        # Overall budget overview
        overview = await example.get_budget_overview()
        print(f"\nOVERALL BUDGET OVERVIEW:")
        print(f"  - Total Budgets: {overview['total_budgets']}")
        print(f"  - Active Budgets: {overview['active_budgets']}")
        print(f"  - Total Budgeted: ${overview['total_budgeted_amount']}")
        print(f"  - Total Spent: ${overview['total_spent_amount']} ({overview['overall_percentage_used']:.1f}%)")
        print(f"  - Total Remaining: ${overview['total_remaining_amount']}")
        
        if overview.get('unbudgeted_spending'):
            print(f"  - Unbudgeted Spending: ${overview['unbudgeted_spending']}")
            
        # 7. Process rollover (if needed)
        print("\n7. BUDGET ROLLOVER")
        # This would typically be done at the end of a period
        # For demo purposes, we'll just show how it works
        try:
            rollover_result = await example.process_rollover(groceries_budget["id"])
            print(f"✓ Processed rollover for {groceries_budget['name']}")
            print(f"  - Periods processed: {rollover_result['periods_processed']}")
            print(f"  - Rollover amount: ${rollover_result['rollover_amount']}")
        except httpx.HTTPStatusError:
            print("  - No rollover needed (current period not ended)")
            
    except httpx.HTTPStatusError as e:
        print(f"❌ Error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    finally:
        await example.close()


def main():
    """Main entry point."""
    print("=" * 60)
    print("DebtWise Budget Management Example")
    print("=" * 60)
    print("\nThis example demonstrates:")
    print("• Creating budgets with different period types")
    print("• Setting up budget alerts")
    print("• Tracking spending against budgets")
    print("• Budget rollovers")
    print("• Budget summaries and analytics")
    
    asyncio.run(run_budget_examples())
    
    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()