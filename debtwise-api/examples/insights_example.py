"""
Example script demonstrating the predictive insights functionality.
"""

import asyncio
from datetime import date, datetime, timedelta
from decimal import Decimal
import json

# Mock database session
class MockDB:
    def __init__(self):
        self.data = []
    
    def add(self, obj):
        self.data.append(obj)
    
    async def commit(self):
        pass
    
    async def refresh(self, obj, *args):
        pass
    
    async def execute(self, query):
        # Mock result
        class Result:
            def scalars(self):
                return self
            
            def all(self):
                return []
            
            def scalar(self):
                return Decimal("5000")
            
            def scalar_one_or_none(self):
                return None
        
        return Result()


# Example demonstrating the insights functionality
async def demo_predictive_insights():
    """Demonstrate predictive insights features."""
    
    print("=== DebtWise Predictive Insights Demo ===\n")
    
    # 1. Spending Forecast Example
    print("1. SPENDING FORECAST")
    print("-" * 40)
    
    forecast_data = {
        "user_id": 1,
        "category": "Groceries",
        "period": "Next 30 days",
        "predicted_amount": 650.00,
        "confidence_level": 0.85,
        "historical_avg": 600.00,
        "trend": "increasing",
        "trend_percentage": 8.3,
        "prediction_range": {
            "lower_bound": 580.00,
            "upper_bound": 720.00
        }
    }
    
    print(f"Category: {forecast_data['category']}")
    print(f"Period: {forecast_data['period']}")
    print(f"Predicted Spending: ${forecast_data['predicted_amount']:.2f}")
    print(f"Confidence Level: {forecast_data['confidence_level']*100:.0f}%")
    print(f"Historical Average: ${forecast_data['historical_avg']:.2f}")
    print(f"Trend: {forecast_data['trend'].title()} ({forecast_data['trend_percentage']:.1f}%)")
    print(f"95% Prediction Range: ${forecast_data['prediction_range']['lower_bound']:.2f} - ${forecast_data['prediction_range']['upper_bound']:.2f}")
    
    print("\n")
    
    # 2. Cash Flow Forecast Example
    print("2. CASH FLOW FORECAST")
    print("-" * 40)
    
    cashflow_data = {
        "current_balance": 2500.00,
        "forecast_date": "2025-10-23",
        "predicted_income": 3000.00,
        "predicted_expenses": 3200.00,
        "predicted_balance": 2300.00,
        "minimum_balance": 800.00,
        "low_balance_date": "2025-10-15",
        "overdraft_risk": 0.15,
        "scheduled_bills": [
            {"name": "Rent", "amount": 1200, "date": "2025-10-01"},
            {"name": "Car Payment", "amount": 350, "date": "2025-10-15"},
            {"name": "Insurance", "amount": 150, "date": "2025-10-20"}
        ]
    }
    
    print(f"Current Balance: ${cashflow_data['current_balance']:.2f}")
    print(f"30-Day Forecast:")
    print(f"  - Predicted Income: ${cashflow_data['predicted_income']:.2f}")
    print(f"  - Predicted Expenses: ${cashflow_data['predicted_expenses']:.2f}")
    print(f"  - Predicted End Balance: ${cashflow_data['predicted_balance']:.2f}")
    print(f"  - Minimum Balance: ${cashflow_data['minimum_balance']:.2f} (on {cashflow_data['low_balance_date']})")
    print(f"  - Overdraft Risk: {cashflow_data['overdraft_risk']*100:.0f}%")
    print(f"\nScheduled Bills:")
    for bill in cashflow_data['scheduled_bills']:
        print(f"  - {bill['name']}: ${bill['amount']} on {bill['date']}")
    
    print("\n")
    
    # 3. Spending Anomalies Example
    print("3. SPENDING ANOMALIES DETECTED")
    print("-" * 40)
    
    anomalies = [
        {
            "transaction": "Amazon Purchase",
            "date": "2025-09-20",
            "amount": 450.00,
            "expected_range": [50, 150],
            "anomaly_score": 3.2,
            "category": "Shopping"
        },
        {
            "transaction": "Restaurant - The Grill",
            "date": "2025-09-18",
            "amount": 280.00,
            "expected_range": [30, 80],
            "anomaly_score": 2.8,
            "category": "Dining"
        }
    ]
    
    for anomaly in anomalies:
        print(f"⚠️  Unusual Transaction Detected:")
        print(f"   Description: {anomaly['transaction']}")
        print(f"   Date: {anomaly['date']}")
        print(f"   Amount: ${anomaly['amount']:.2f}")
        print(f"   Expected Range: ${anomaly['expected_range'][0]} - ${anomaly['expected_range'][1]}")
        print(f"   Anomaly Score: {anomaly['anomaly_score']:.1f} (higher = more unusual)")
        print(f"   Category: {anomaly['category']}")
        print()
    
    # 4. Predictive Insights Example
    print("4. PREDICTIVE INSIGHTS & RECOMMENDATIONS")
    print("-" * 40)
    
    insights = [
        {
            "type": "CRITICAL",
            "title": "Budget Overspending Alert",
            "description": "You've used 85% of your Entertainment budget but are only 50% through the month.",
            "recommendation": "Reduce entertainment spending to $5/day for the rest of the month.",
            "potential_savings": 150.00,
            "action_items": [
                "Review recent entertainment transactions",
                "Cancel unused subscriptions",
                "Look for free entertainment options"
            ]
        },
        {
            "type": "WARNING",
            "title": "Cash Flow Warning",
            "description": "Your account balance may run low in 15 days based on current spending patterns.",
            "recommendation": "Consider postponing non-essential purchases and reviewing upcoming bills.",
            "risk_score": 0.7,
            "action_items": [
                "Review scheduled bills",
                "Postpone large purchases",
                "Set up balance alerts"
            ]
        },
        {
            "type": "SUCCESS",
            "title": "Great Spending Reduction!",
            "description": "Your dining expenses are down 25% compared to last month.",
            "recommendation": "Keep up the good work! Consider saving the difference.",
            "potential_savings": 200.00,
            "action_items": [
                "Transfer savings to emergency fund",
                "Update dining budget",
                "Continue meal planning"
            ]
        }
    ]
    
    for insight in insights:
        emoji = "🔴" if insight['type'] == "CRITICAL" else "🟡" if insight['type'] == "WARNING" else "🟢"
        print(f"{emoji} {insight['type']}: {insight['title']}")
        print(f"   {insight['description']}")
        print(f"   💡 Recommendation: {insight['recommendation']}")
        if 'potential_savings' in insight:
            print(f"   💰 Potential Savings: ${insight['potential_savings']:.2f}")
        if 'risk_score' in insight:
            print(f"   ⚠️  Risk Level: {insight['risk_score']*100:.0f}%")
        print(f"   📋 Action Items:")
        for action in insight['action_items']:
            print(f"      - {action}")
        print()
    
    # 5. Dashboard Summary Example
    print("5. DASHBOARD INSIGHTS SUMMARY")
    print("-" * 40)
    
    dashboard = {
        "current_month_spending": 2850.00,
        "predicted_month_end": 4200.00,
        "budget_health": {
            "total_budgets": 8,
            "budgets_at_risk": 3,
            "overall_utilization": 72
        },
        "anomalies": {
            "count": 2,
            "total_excess": 450.00
        },
        "alerts": {
            "critical": 1,
            "warning": 2,
            "info": 3
        },
        "savings_opportunities": 500.00
    }
    
    print(f"📊 Current Month:")
    print(f"   Spent So Far: ${dashboard['current_month_spending']:.2f}")
    print(f"   Predicted End: ${dashboard['predicted_month_end']:.2f}")
    print(f"\n📈 Budget Health:")
    print(f"   Active Budgets: {dashboard['budget_health']['total_budgets']}")
    print(f"   At Risk: {dashboard['budget_health']['budgets_at_risk']}")
    print(f"   Overall Usage: {dashboard['budget_health']['overall_utilization']}%")
    print(f"\n🔍 Anomaly Detection:")
    print(f"   Unusual Transactions: {dashboard['anomalies']['count']}")
    print(f"   Excess Amount: ${dashboard['anomalies']['total_excess']:.2f}")
    print(f"\n🔔 Active Alerts:")
    print(f"   Critical: {dashboard['alerts']['critical']}")
    print(f"   Warning: {dashboard['alerts']['warning']}")
    print(f"   Info: {dashboard['alerts']['info']}")
    print(f"\n💰 Total Savings Opportunities: ${dashboard['savings_opportunities']:.2f}")
    
    print("\n" + "="*50)
    print("Demo completed! The DebtWise Predictive Insights feature provides:")
    print("- AI-powered spending forecasts")
    print("- Cash flow predictions")
    print("- Anomaly detection for unusual transactions") 
    print("- Personalized financial insights and recommendations")
    print("- Real-time dashboard with actionable alerts")


# Run the demo
if __name__ == "__main__":
    asyncio.run(demo_predictive_insights())