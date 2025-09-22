"""
Tests for authentication endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, create_refresh_token
from app.models.user import User


@pytest.mark.auth
class TestAuth:
    """Test authentication endpoints."""
    
    def test_register_new_user(self, client: TestClient):
        """Test user registration."""
        user_data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "newpassword123",
            "full_name": "New User",
        }
        
        response = client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["username"] == user_data["username"]
        assert data["full_name"] == user_data["full_name"]
        assert data["is_active"] is True
        assert data["is_verified"] is False
        assert "id" in data
        assert "hashed_password" not in data
    
    def test_register_duplicate_email(self, client: TestClient, test_user: User):
        """Test registration with duplicate email."""
        user_data = {
            "email": test_user.email,
            "username": "anotheruser",
            "password": "password123",
        }
        
        response = client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]
    
    def test_register_duplicate_username(self, client: TestClient, test_user: User):
        """Test registration with duplicate username."""
        user_data = {
            "email": "another@example.com",
            "username": test_user.username,
            "password": "password123",
        }
        
        response = client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]
    
    def test_login_with_username(self, client: TestClient, test_user: User):
        """Test login with username."""
        login_data = {
            "username": test_user.username,
            "password": "testpassword123",
        }
        
        response = client.post("/api/v1/auth/login", data=login_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    
    def test_login_with_email(self, client: TestClient, test_user: User):
        """Test login with email."""
        login_data = {
            "username": test_user.email,  # OAuth2 form uses "username" field for both
            "password": "testpassword123",
        }
        
        response = client.post("/api/v1/auth/login", data=login_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
    
    def test_login_incorrect_password(self, client: TestClient, test_user: User):
        """Test login with incorrect password."""
        login_data = {
            "username": test_user.username,
            "password": "wrongpassword",
        }
        
        response = client.post("/api/v1/auth/login", data=login_data)
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]
    
    def test_login_nonexistent_user(self, client: TestClient):
        """Test login with nonexistent user."""
        login_data = {
            "username": "nonexistent",
            "password": "password123",
        }
        
        response = client.post("/api/v1/auth/login", data=login_data)
        assert response.status_code == 401
    
    def test_refresh_token(self, client: TestClient, test_user: User):
        """Test token refresh."""
        refresh_token = create_refresh_token(subject=test_user.id)
        
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    
    def test_refresh_with_invalid_token(self, client: TestClient):
        """Test refresh with invalid token."""
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"}
        )
        assert response.status_code == 401
    
    def test_refresh_with_access_token(self, client: TestClient, test_user: User):
        """Test refresh with access token instead of refresh token."""
        access_token = create_access_token(subject=test_user.id)
        
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token}
        )
        assert response.status_code == 401
    
    def test_change_password(self, client: TestClient, auth_headers: dict):
        """Test password change."""
        password_data = {
            "current_password": "testpassword123",
            "new_password": "newpassword456",
        }
        
        response = client.post(
            "/api/v1/auth/change-password",
            json=password_data,
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Password updated successfully"
    
    def test_change_password_incorrect_current(
        self, client: TestClient, auth_headers: dict
    ):
        """Test password change with incorrect current password."""
        password_data = {
            "current_password": "wrongpassword",
            "new_password": "newpassword456",
        }
        
        response = client.post(
            "/api/v1/auth/change-password",
            json=password_data,
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "Incorrect password" in response.json()["detail"]
    
    def test_logout(self, client: TestClient, auth_headers: dict):
        """Test logout."""
        response = client.post("/api/v1/auth/logout", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Successfully logged out"
    
    @pytest.mark.asyncio
    async def test_inactive_user_login(
        self, async_client: AsyncClient, test_db: AsyncSession
    ):
        """Test login with inactive user."""
        from app.core.security import get_password_hash
        
        # Create inactive user
        inactive_user = User(
            email="inactive@example.com",
            username="inactive",
            hashed_password=get_password_hash("password123"),
            is_active=False,
        )
        test_db.add(inactive_user)
        await test_db.commit()
        
        login_data = {
            "username": "inactive",
            "password": "password123",
        }
        
        response = await async_client.post("/api/v1/auth/login", data=login_data)
        assert response.status_code == 400
        assert "Inactive user" in response.json()["detail"]