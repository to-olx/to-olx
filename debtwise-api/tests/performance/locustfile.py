"""
Performance testing for DebtWise API using Locust.
"""

import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from locust import HttpUser, between, task


class DebtWiseUser(HttpUser):
    """Simulated DebtWise API user for load testing."""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.access_token: Optional[str] = None
        self.user_id: Optional[int] = None
        self.transaction_ids: List[int] = []
        self.debt_ids: List[int] = []
        self.budget_ids: List[int] = []
    
    def on_start(self):
        """Called when a simulated user starts."""
        # Register and login
        self.register_user()
        self.login()
    
    def on_stop(self):
        """Called when a simulated user stops."""
        # Cleanup can be added here if needed
        pass
    
    def register_user(self):
        """Register a new user account."""
        username = f"perf_user_{random.randint(100000, 999999)}"
        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": f"{username}@example.com",
                "password": "TestPassword123!",
                "full_name": f"Performance Test User {username}",
            }
        )
        
        if response.status_code == 201:
            data = response.json()
            self.user_id = data.get("id")
    
    def login(self):
        """Login to get access token."""
        if not self.user_id:
            return
        
        username = f"perf_user_{self.user_id}"
        response = self.client.post(
            "/api/v1/auth/login",
            data={
                "username": f"{username}@example.com",
                "password": "TestPassword123!",
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            self.access_token = data.get("access_token")
            # Update client headers with auth token
            self.client.headers.update({
                "Authorization": f"Bearer {self.access_token}"
            })
    
    # Health Check Tasks
    
    @task(1)
    def check_health(self):
        """Check API health endpoint."""
        self.client.get("/api/v1/health", name="/health")
    
    # Authentication Tasks
    
    @task(2)
    def refresh_token(self):
        """Refresh access token."""
        if not self.access_token:
            return
        
        # In a real scenario, we'd use the refresh token
        # For now, just simulate the endpoint call
        self.client.post(
            "/api/v1/auth/refresh",
            name="/auth/refresh"
        )
    
    @task(1)
    def get_profile(self):
        """Get user profile."""
        if not self.access_token:
            return
        
        self.client.get("/api/v1/users/profile", name="/users/profile")
    
    # Transaction Tasks
    
    @task(10)
    def create_transaction(self):
        """Create a new transaction."""
        if not self.access_token:
            return
        
        categories = ["Food", "Transport", "Shopping", "Entertainment", "Bills", "Healthcare"]
        
        transaction_data = {
            "amount": round(random.uniform(10, 500), 2),
            "category": random.choice(categories),
            "description": f"Test transaction {random.randint(1000, 9999)}",
            "date": (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat(),
            "type": random.choice(["expense", "income"]),
            "tags": random.sample(["recurring", "essential", "discretionary"], k=random.randint(0, 2)),
        }
        
        response = self.client.post(
            "/api/v1/transactions",
            json=transaction_data,
            name="/transactions [CREATE]"
        )
        
        if response.status_code == 201:
            data = response.json()
            transaction_id = data.get("id")
            if transaction_id:
                self.transaction_ids.append(transaction_id)
    
    @task(15)
    def list_transactions(self):
        """List user transactions with various filters."""
        if not self.access_token:
            return
        
        # Random query parameters
        params = {}
        
        if random.random() < 0.5:
            params["category"] = random.choice(["Food", "Transport", "Shopping"])
        
        if random.random() < 0.3:
            params["start_date"] = (datetime.now() - timedelta(days=30)).date().isoformat()
            params["end_date"] = datetime.now().date().isoformat()
        
        if random.random() < 0.4:
            params["limit"] = random.choice([10, 20, 50])
        
        self.client.get(
            "/api/v1/transactions",
            params=params,
            name="/transactions [LIST]"
        )
    
    @task(5)
    def get_transaction(self):
        """Get a specific transaction."""
        if not self.access_token or not self.transaction_ids:
            return
        
        transaction_id = random.choice(self.transaction_ids)
        self.client.get(
            f"/api/v1/transactions/{transaction_id}",
            name="/transactions/[id]"
        )
    
    @task(3)
    def update_transaction(self):
        """Update an existing transaction."""
        if not self.access_token or not self.transaction_ids:
            return
        
        transaction_id = random.choice(self.transaction_ids)
        update_data = {
            "amount": round(random.uniform(10, 500), 2),
            "description": f"Updated transaction {random.randint(1000, 9999)}",
        }
        
        self.client.put(
            f"/api/v1/transactions/{transaction_id}",
            json=update_data,
            name="/transactions/[id] [UPDATE]"
        )
    
    @task(1)
    def delete_transaction(self):
        """Delete a transaction."""
        if not self.access_token or not self.transaction_ids:
            return
        
        transaction_id = self.transaction_ids.pop()
        self.client.delete(
            f"/api/v1/transactions/{transaction_id}",
            name="/transactions/[id] [DELETE]"
        )
    
    # Debt Management Tasks
    
    @task(5)
    def create_debt(self):
        """Create a new debt."""
        if not self.access_token:
            return
        
        debt_data = {
            "name": f"Test Debt {random.randint(1000, 9999)}",
            "type": random.choice(["credit_card", "loan", "mortgage"]),
            "original_amount": round(random.uniform(1000, 50000), 2),
            "current_balance": round(random.uniform(500, 40000), 2),
            "interest_rate": round(random.uniform(3.0, 25.0), 2),
            "minimum_payment": round(random.uniform(50, 500), 2),
            "due_date": (datetime.now() + timedelta(days=random.randint(1, 28))).date().isoformat(),
        }
        
        response = self.client.post(
            "/api/v1/debts",
            json=debt_data,
            name="/debts [CREATE]"
        )
        
        if response.status_code == 201:
            data = response.json()
            debt_id = data.get("id")
            if debt_id:
                self.debt_ids.append(debt_id)
    
    @task(8)
    def list_debts(self):
        """List user debts."""
        if not self.access_token:
            return
        
        self.client.get("/api/v1/debts", name="/debts [LIST]")
    
    @task(3)
    def update_debt(self):
        """Update debt balance."""
        if not self.access_token or not self.debt_ids:
            return
        
        debt_id = random.choice(self.debt_ids)
        update_data = {
            "current_balance": round(random.uniform(100, 40000), 2),
        }
        
        self.client.put(
            f"/api/v1/debts/{debt_id}",
            json=update_data,
            name="/debts/[id] [UPDATE]"
        )
    
    # Budget Tasks
    
    @task(4)
    def create_budget(self):
        """Create a new budget."""
        if not self.access_token:
            return
        
        categories = ["Food", "Transport", "Shopping", "Entertainment", "Bills"]
        
        budget_data = {
            "name": f"Budget for {random.choice(categories)}",
            "category": random.choice(categories),
            "amount": round(random.uniform(200, 2000), 2),
            "period": random.choice(["monthly", "weekly", "yearly"]),
            "start_date": datetime.now().date().isoformat(),
        }
        
        response = self.client.post(
            "/api/v1/budgets",
            json=budget_data,
            name="/budgets [CREATE]"
        )
        
        if response.status_code == 201:
            data = response.json()
            budget_id = data.get("id")
            if budget_id:
                self.budget_ids.append(budget_id)
    
    @task(10)
    def list_budgets(self):
        """List user budgets with status."""
        if not self.access_token:
            return
        
        self.client.get(
            "/api/v1/budgets",
            params={"include_status": True},
            name="/budgets [LIST]"
        )
    
    @task(2)
    def get_budget_status(self):
        """Get budget status."""
        if not self.access_token or not self.budget_ids:
            return
        
        budget_id = random.choice(self.budget_ids)
        self.client.get(
            f"/api/v1/budgets/{budget_id}/status",
            name="/budgets/[id]/status"
        )
    
    # Analytics Tasks
    
    @task(8)
    def get_spending_summary(self):
        """Get spending summary analytics."""
        if not self.access_token:
            return
        
        period = random.choice(["daily", "weekly", "monthly"])
        
        self.client.get(
            "/api/v1/analytics/spending-summary",
            params={
                "period": period,
                "start_date": (datetime.now() - timedelta(days=30)).date().isoformat(),
                "end_date": datetime.now().date().isoformat(),
            },
            name=f"/analytics/spending-summary [{period}]"
        )
    
    @task(6)
    def get_category_breakdown(self):
        """Get category breakdown analytics."""
        if not self.access_token:
            return
        
        self.client.get(
            "/api/v1/analytics/category-breakdown",
            params={
                "start_date": (datetime.now() - timedelta(days=30)).date().isoformat(),
                "end_date": datetime.now().date().isoformat(),
            },
            name="/analytics/category-breakdown"
        )
    
    @task(4)
    def get_insights(self):
        """Get AI-generated insights."""
        if not self.access_token:
            return
        
        self.client.get(
            "/api/v1/insights",
            params={"limit": 5},
            name="/insights"
        )
    
    # Search Tasks
    
    @task(5)
    def search_transactions(self):
        """Search transactions."""
        if not self.access_token:
            return
        
        search_terms = ["food", "transport", "shopping", "bill", "subscription"]
        
        self.client.get(
            "/api/v1/search/transactions",
            params={
                "q": random.choice(search_terms),
                "limit": 20,
            },
            name="/search/transactions"
        )


class AdminUser(HttpUser):
    """Simulated admin user for testing admin endpoints."""
    
    wait_time = between(2, 5)
    
    def on_start(self):
        """Admin login."""
        # Admin would have different authentication
        pass
    
    @task
    def get_system_stats(self):
        """Get system statistics (admin endpoint)."""
        self.client.get(
            "/api/v1/admin/stats",
            name="/admin/stats"
        )


# Example of running Locust programmatically
if __name__ == "__main__":
    # Can be run with: locust -f locustfile.py
    # Or with web UI: locust -f locustfile.py --web-port 8089
    # Or headless: locust -f locustfile.py --headless -u 100 -r 10 -t 5m
    pass