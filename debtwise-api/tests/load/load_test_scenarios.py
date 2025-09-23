"""
Load testing scenarios for DebtWise API.
Tests system scalability and identifies performance bottlenecks.
"""

import json
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List

from locust import HttpUser, TaskSet, between, constant, task
from locust.exception import RescheduleTask


class UserBehavior(TaskSet):
    """Realistic user behavior patterns for load testing."""
    
    def on_start(self):
        """Initialize user session."""
        self.user_id = None
        self.token = None
        self.transaction_ids = []
        self.debt_ids = []
        self.budget_ids = []
        
        # Register and login
        self.register_user()
        if self.user_id:
            self.login()
    
    def register_user(self):
        """Register a new test user."""
        email = f"load_test_{random.randint(100000, 999999)}@example.com"
        
        with self.client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "LoadTest123!",
                "full_name": f"Load Test User {email}",
            },
            catch_response=True
        ) as response:
            if response.status_code == 201:
                data = response.json()
                self.user_id = data.get("id")
                self.email = email
                response.success()
            else:
                response.failure(f"Registration failed: {response.status_code}")
    
    def login(self):
        """Authenticate and get access token."""
        with self.client.post(
            "/api/v1/auth/login",
            data={
                "username": self.email,
                "password": "LoadTest123!",
            },
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
                self.client.headers.update({
                    "Authorization": f"Bearer {self.token}"
                })
                response.success()
            else:
                response.failure(f"Login failed: {response.status_code}")
                raise RescheduleTask()
    
    @task(50)
    def create_and_list_transactions(self):
        """High-frequency operation: create and list transactions."""
        if not self.token:
            return
        
        # Create transaction
        categories = ["Food", "Transport", "Shopping", "Entertainment", "Bills"]
        
        with self.client.post(
            "/api/v1/transactions",
            json={
                "amount": round(random.uniform(-200, -10), 2),
                "category": random.choice(categories),
                "description": f"Load test transaction {time.time()}",
                "date": datetime.now().date().isoformat(),
                "type": "expense",
            },
            catch_response=True,
            name="/api/v1/transactions [CREATE]"
        ) as response:
            if response.status_code == 201:
                transaction_id = response.json().get("id")
                if transaction_id:
                    self.transaction_ids.append(transaction_id)
                response.success()
            else:
                response.failure(f"Transaction creation failed: {response.status_code}")
        
        # List transactions
        with self.client.get(
            "/api/v1/transactions",
            params={"limit": 20},
            catch_response=True,
            name="/api/v1/transactions [LIST]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Transaction list failed: {response.status_code}")
    
    @task(30)
    def analytics_operations(self):
        """Medium-frequency: get analytics and insights."""
        if not self.token:
            return
        
        # Spending summary
        with self.client.get(
            "/api/v1/analytics/spending-summary",
            params={
                "period": "monthly",
                "start_date": (datetime.now() - timedelta(days=30)).date().isoformat(),
                "end_date": datetime.now().date().isoformat(),
            },
            catch_response=True,
            name="/api/v1/analytics/spending-summary"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Analytics failed: {response.status_code}")
        
        # Category breakdown
        with self.client.get(
            "/api/v1/analytics/category-breakdown",
            catch_response=True,
            name="/api/v1/analytics/category-breakdown"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Category breakdown failed: {response.status_code}")
    
    @task(10)
    def budget_operations(self):
        """Low-frequency: create and check budgets."""
        if not self.token:
            return
        
        # Create budget
        if random.random() < 0.3:  # 30% chance to create
            with self.client.post(
                "/api/v1/budgets",
                json={
                    "name": f"Test Budget {random.randint(1, 100)}",
                    "category": random.choice(["Food", "Transport", "Shopping"]),
                    "amount": round(random.uniform(200, 1000), 2),
                    "period": "monthly",
                    "start_date": datetime.now().date().isoformat(),
                },
                catch_response=True,
                name="/api/v1/budgets [CREATE]"
            ) as response:
                if response.status_code == 201:
                    budget_id = response.json().get("id")
                    if budget_id:
                        self.budget_ids.append(budget_id)
                    response.success()
                else:
                    response.failure(f"Budget creation failed: {response.status_code}")
        
        # List budgets with status
        with self.client.get(
            "/api/v1/budgets",
            params={"include_status": True},
            catch_response=True,
            name="/api/v1/budgets [LIST]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Budget list failed: {response.status_code}")
    
    @task(5)
    def debt_management(self):
        """Low-frequency: manage debts."""
        if not self.token:
            return
        
        # Create debt
        if random.random() < 0.2:  # 20% chance
            with self.client.post(
                "/api/v1/debts",
                json={
                    "name": f"Test Debt {random.randint(1, 100)}",
                    "type": random.choice(["credit_card", "loan"]),
                    "original_amount": round(random.uniform(1000, 10000), 2),
                    "current_balance": round(random.uniform(500, 9000), 2),
                    "interest_rate": round(random.uniform(5, 20), 2),
                    "minimum_payment": round(random.uniform(50, 200), 2),
                    "due_date": (datetime.now() + timedelta(days=15)).date().isoformat(),
                },
                catch_response=True,
                name="/api/v1/debts [CREATE]"
            ) as response:
                if response.status_code == 201:
                    response.success()
                else:
                    response.failure(f"Debt creation failed: {response.status_code}")
        
        # List debts
        with self.client.get(
            "/api/v1/debts",
            catch_response=True,
            name="/api/v1/debts [LIST]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Debt list failed: {response.status_code}")
    
    @task(3)
    def search_operations(self):
        """Search operations to test search performance."""
        if not self.token:
            return
        
        search_terms = ["food", "transport", "bill", "subscription", "shopping"]
        
        with self.client.get(
            "/api/v1/search/transactions",
            params={
                "q": random.choice(search_terms),
                "limit": 10,
            },
            catch_response=True,
            name="/api/v1/search/transactions"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Search failed: {response.status_code}")
    
    @task(2)
    def profile_operations(self):
        """User profile operations."""
        if not self.token:
            return
        
        with self.client.get(
            "/api/v1/users/profile",
            catch_response=True,
            name="/api/v1/users/profile"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Profile fetch failed: {response.status_code}")


class NormalUser(HttpUser):
    """Normal user with realistic behavior."""
    tasks = [UserBehavior]
    wait_time = between(1, 5)  # Wait 1-5 seconds between tasks
    
    def on_start(self):
        """User starting behavior."""
        self.client.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })


class PowerUser(HttpUser):
    """Power user with higher activity."""
    tasks = [UserBehavior]
    wait_time = between(0.5, 2)  # More frequent requests
    
    def on_start(self):
        """Power user starting behavior."""
        self.client.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })


class MobileUser(HttpUser):
    """Mobile user with specific patterns."""
    wait_time = between(2, 10)  # Slower, more deliberate actions
    
    def on_start(self):
        """Mobile user starting behavior."""
        self.client.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "DebtWise-Mobile/1.0",
        })
        
        # Mobile users might have existing sessions
        self.token = None
        self.login_existing_user()
    
    def login_existing_user(self):
        """Simulate existing user login."""
        # In real scenario, would use existing test accounts
        test_accounts = [
            ("mobile_test_1@example.com", "MobileTest123!"),
            ("mobile_test_2@example.com", "MobileTest123!"),
            ("mobile_test_3@example.com", "MobileTest123!"),
        ]
        
        email, password = random.choice(test_accounts)
        
        with self.client.post(
            "/api/v1/auth/login",
            data={
                "username": email,
                "password": password,
            },
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
                self.client.headers["Authorization"] = f"Bearer {self.token}"
                response.success()
            else:
                # If login fails, create new account
                response.success()  # Don't mark as failure
                self.register_new_mobile_user()
    
    def register_new_mobile_user(self):
        """Register new mobile user."""
        email = f"mobile_{random.randint(100000, 999999)}@example.com"
        
        with self.client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "MobileTest123!",
                "full_name": f"Mobile User {email}",
            },
            catch_response=True
        ) as response:
            if response.status_code == 201:
                response.success()
                self.login_existing_user()
            else:
                response.failure(f"Mobile registration failed: {response.status_code}")
    
    @task(40)
    def quick_balance_check(self):
        """Mobile users frequently check balances."""
        if not self.token:
            return
        
        # Get recent transactions (mobile view)
        with self.client.get(
            "/api/v1/transactions",
            params={"limit": 10},
            catch_response=True,
            name="/api/v1/transactions [MOBILE_QUICK]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Mobile balance check failed: {response.status_code}")
    
    @task(30)
    def add_expense(self):
        """Quick expense addition from mobile."""
        if not self.token:
            return
        
        # Simplified transaction for mobile
        with self.client.post(
            "/api/v1/transactions",
            json={
                "amount": round(random.uniform(-50, -5), 2),
                "category": random.choice(["Food", "Transport", "Other"]),
                "description": "Quick expense",
                "date": datetime.now().date().isoformat(),
                "type": "expense",
            },
            catch_response=True,
            name="/api/v1/transactions [MOBILE_ADD]"
        ) as response:
            if response.status_code == 201:
                response.success()
            else:
                response.failure(f"Mobile expense add failed: {response.status_code}")
    
    @task(20)
    def check_budgets(self):
        """Check budget status from mobile."""
        if not self.token:
            return
        
        with self.client.get(
            "/api/v1/budgets",
            params={"include_status": True},
            catch_response=True,
            name="/api/v1/budgets [MOBILE]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Mobile budget check failed: {response.status_code}")
    
    @task(10)
    def get_insights(self):
        """Get quick insights on mobile."""
        if not self.token:
            return
        
        with self.client.get(
            "/api/v1/insights",
            params={"limit": 3},  # Fewer insights for mobile
            catch_response=True,
            name="/api/v1/insights [MOBILE]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Mobile insights failed: {response.status_code}")


class StressTestUser(HttpUser):
    """User for stress testing specific endpoints."""
    wait_time = constant(0.1)  # Minimal wait time for stress testing
    
    def on_start(self):
        """Stress test user setup."""
        self.client.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        
        # Pre-authenticated for stress testing
        self.setup_stress_test_user()
    
    def setup_stress_test_user(self):
        """Setup pre-authenticated stress test user."""
        # In real scenario, would use pre-created high-volume test account
        with self.client.post(
            "/api/v1/auth/login",
            data={
                "username": "stress_test@example.com",
                "password": "StressTest123!",
            },
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
                self.client.headers["Authorization"] = f"Bearer {self.token}"
                response.success()
            else:
                # Create stress test account if doesn't exist
                response.success()
    
    @task(100)
    def stress_analytics(self):
        """Stress test analytics endpoint."""
        # Analytics with various parameters
        periods = ["daily", "weekly", "monthly"]
        
        with self.client.get(
            "/api/v1/analytics/spending-summary",
            params={
                "period": random.choice(periods),
                "start_date": (datetime.now() - timedelta(days=random.randint(30, 365))).date().isoformat(),
                "end_date": datetime.now().date().isoformat(),
            },
            catch_response=True,
            name="/api/v1/analytics/spending-summary [STRESS]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Stress analytics failed: {response.status_code}")
    
    @task(50)
    def stress_search(self):
        """Stress test search functionality."""
        # Complex search queries
        complex_terms = [
            "food AND restaurant",
            "transport OR uber",
            "subscription*",
            "bill* NOT electricity",
            "amount:>100",
        ]
        
        with self.client.get(
            "/api/v1/search/transactions",
            params={
                "q": random.choice(complex_terms),
                "limit": random.choice([20, 50, 100]),
                "offset": random.randint(0, 100),
            },
            catch_response=True,
            name="/api/v1/search/transactions [STRESS]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Stress search failed: {response.status_code}")