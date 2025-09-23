#!/usr/bin/env python3
"""
Example usage of the DebtWise spending tracking features.

This script demonstrates how to use the API to:
1. Create categories
2. Add transactions
3. Set up auto-categorization rules
4. Import transactions from CSV
5. View spending analytics
"""

import asyncio
from datetime import date, timedelta
from decimal import Decimal

import httpx


async def main():
    """Run the example."""
    base_url = "http://localhost:8000/api/v1"
    
    # First, we need to authenticate
    print("🔐 Authenticating...")
    async with httpx.AsyncClient() as client:
        # Login to get access token
        login_response = await client.post(
            f"{base_url}/auth/login",
            data={
                "username": "testuser",
                "password": "testpass123",
            },
        )
        
        if login_response.status_code != 200:
            print("❌ Failed to login. Make sure you have a test user created.")
            return
        
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        print("✅ Authentication successful!")
        
        # Step 1: Create default categories
        print("\n📁 Creating default categories...")
        categories_response = await client.post(
            f"{base_url}/spending/categories/defaults",
            headers=headers,
        )
        
        if categories_response.status_code == 200:
            categories = categories_response.json()
            print(f"✅ Created {len(categories)} default categories")
            
            # Show some categories
            for cat in categories[:5]:
                print(f"  - {cat['icon']} {cat['name']} ({cat['transaction_type']})")
        else:
            # Categories might already exist, get them
            categories_response = await client.get(
                f"{base_url}/spending/categories",
                headers=headers,
            )
            categories = categories_response.json()
            print(f"ℹ️  Found {len(categories)} existing categories")
        
        # Find specific categories for our examples
        food_category = next((c for c in categories if "Food" in c["name"]), None)
        transport_category = next((c for c in categories if "Transportation" in c["name"]), None)
        salary_category = next((c for c in categories if "Salary" in c["name"]), None)
        
        # Step 2: Add some transactions
        print("\n💳 Adding sample transactions...")
        
        transactions_data = [
            {
                "amount": 45.99,
                "transaction_date": str(date.today()),
                "description": "Grocery shopping at Whole Foods",
                "transaction_type": "expense",
                "category_id": food_category["id"] if food_category else None,
                "merchant": "Whole Foods",
                "tags": "groceries,organic",
            },
            {
                "amount": 35.00,
                "transaction_date": str(date.today() - timedelta(days=1)),
                "description": "Gas station fill-up",
                "transaction_type": "expense",
                "category_id": transport_category["id"] if transport_category else None,
                "merchant": "Shell",
                "tags": "gas,car",
            },
            {
                "amount": 3500.00,
                "transaction_date": str(date.today() - timedelta(days=5)),
                "description": "Monthly salary deposit",
                "transaction_type": "income",
                "category_id": salary_category["id"] if salary_category else None,
                "tags": "salary,income",
            },
        ]
        
        for trans_data in transactions_data:
            response = await client.post(
                f"{base_url}/spending/transactions",
                headers=headers,
                json=trans_data,
            )
            if response.status_code == 200:
                trans = response.json()
                print(f"  ✅ Added: ${trans['amount']} - {trans['description']}")
        
        # Step 3: Create an auto-categorization rule
        print("\n🤖 Setting up auto-categorization rules...")
        
        if food_category:
            rule_data = {
                "name": "Coffee Shop Rule",
                "category_id": food_category["id"],
                "description_pattern": "COFFEE|STARBUCKS|DUNKIN|CAFE",
                "merchant_pattern": "STARBUCKS|DUNKIN",
                "amount_min": 2.00,
                "amount_max": 20.00,
                "priority": 100,
            }
            
            rule_response = await client.post(
                f"{base_url}/spending/rules",
                headers=headers,
                json=rule_data,
            )
            
            if rule_response.status_code == 200:
                print("  ✅ Created rule: Coffee Shop Rule")
        
        # Step 4: Test the rule with a new transaction
        print("\n☕ Testing auto-categorization...")
        
        coffee_transaction = {
            "amount": 5.75,
            "transaction_date": str(date.today()),
            "description": "Morning coffee at STARBUCKS",
            "transaction_type": "expense",
            "merchant": "STARBUCKS",
            # No category_id - should be auto-categorized
        }
        
        response = await client.post(
            f"{base_url}/spending/transactions",
            headers=headers,
            json=coffee_transaction,
        )
        
        if response.status_code == 200:
            trans = response.json()
            if trans.get("category_id"):
                category_name = trans.get("category", {}).get("name", "Unknown")
                print(f"  ✅ Transaction auto-categorized as: {category_name}")
        
        # Step 5: Import transactions from CSV
        print("\n📤 Importing transactions from CSV...")
        
        csv_content = """Date,Description,Amount,Merchant
2024-01-10,Restaurant lunch,-25.50,Local Bistro
2024-01-11,Online shopping,-89.99,Amazon
2024-01-12,Freelance payment,500.00,Client ABC
2024-01-13,Coffee and pastry,-8.75,Starbucks
2024-01-14,Grocery shopping,-125.30,Trader Joe's"""
        
        files = {"file": ("transactions.csv", csv_content, "text/csv")}
        data = {
            "date_format": "%Y-%m-%d",
            "date_column": "Date",
            "amount_column": "Amount",
            "description_column": "Description",
            "merchant_column": "Merchant",
            "skip_duplicates": "true",
            "auto_categorize": "true",
        }
        
        import_response = await client.post(
            f"{base_url}/spending/transactions/import",
            headers=headers,
            files=files,
            data=data,
        )
        
        if import_response.status_code == 200:
            result = import_response.json()
            print(f"  ✅ Imported {result['imported_count']} transactions")
            print(f"  ℹ️  Skipped {result['skipped_count']} duplicates")
            if result['error_count'] > 0:
                print(f"  ⚠️  {result['error_count']} errors")
        
        # Step 6: View spending analytics
        print("\n📊 Spending Analytics...")
        
        # Get spending by category for the current month
        start_date = date.today().replace(day=1).isoformat()
        
        analytics_response = await client.get(
            f"{base_url}/spending/analytics/spending-by-category"
            f"?start_date={start_date}&transaction_type=expense",
            headers=headers,
        )
        
        if analytics_response.status_code == 200:
            spending_data = analytics_response.json()
            
            print("\n  💰 Spending by Category (This Month):")
            total_spending = sum(cat["total_amount"] for cat in spending_data)
            
            for cat in spending_data[:5]:  # Top 5 categories
                percentage = cat["percentage"]
                amount = cat["total_amount"]
                name = cat["category_name"]
                
                # Create a simple bar chart
                bar_length = int(percentage / 5)
                bar = "█" * bar_length
                
                print(f"    {name:20} ${amount:>8.2f} ({percentage:>5.1f}%) {bar}")
                
                if cat.get("budget_amount"):
                    budget_pct = cat.get("budget_percentage", 0)
                    status = "🟢" if budget_pct < 90 else "🟡" if budget_pct < 100 else "🔴"
                    print(f"    {'':20} Budget: ${cat['budget_amount']} ({budget_pct:.1f}% used) {status}")
            
            print(f"\n    {'Total':20} ${total_spending:>8.2f}")
        
        # Get spending trend
        print("\n  📈 Spending Trend (Last 3 Months):")
        
        three_months_ago = (date.today() - timedelta(days=90)).isoformat()
        
        trend_response = await client.get(
            f"{base_url}/spending/analytics/spending-trend"
            f"?start_date={three_months_ago}&group_by=month",
            headers=headers,
        )
        
        if trend_response.status_code == 200:
            trend_data = trend_response.json()
            
            for period in trend_data:
                income = period["income"]
                expenses = period["expenses"]
                net = period["net"]
                
                # Simple visualization
                net_indicator = "🟢" if net > 0 else "🔴"
                
                print(f"    {period['period']}: "
                      f"Income: ${income:>8.2f} | "
                      f"Expenses: ${expenses:>8.2f} | "
                      f"Net: ${net:>8.2f} {net_indicator}")
        
        # Step 7: List recent transactions
        print("\n📜 Recent Transactions:")
        
        recent_response = await client.get(
            f"{base_url}/spending/transactions?limit=5",
            headers=headers,
        )
        
        if recent_response.status_code == 200:
            recent_data = recent_response.json()
            
            for trans in recent_data["transactions"]:
                emoji = "💵" if trans["transaction_type"] == "income" else "💸"
                category_name = trans.get("category", {}).get("name", "Uncategorized") if trans.get("category") else "Uncategorized"
                
                print(f"    {emoji} {trans['transaction_date']} | "
                      f"${trans['amount']:>8} | "
                      f"{trans['description'][:30]:30} | "
                      f"{category_name}")
        
        print("\n✅ Example completed successfully!")
        print("\n💡 Tips:")
        print("  - Use the API documentation at http://localhost:8000/api/docs")
        print("  - Set up more rules for better auto-categorization")
        print("  - Export your bank statements as CSV for easy import")
        print("  - Set monthly budgets for categories to track spending")


if __name__ == "__main__":
    print("🚀 DebtWise Spending Tracker Example")
    print("=" * 50)
    asyncio.run(main())