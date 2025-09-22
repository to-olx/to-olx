"""
Tests for user management endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.models.user import User


@pytest.mark.user
class TestUsers:
    """Test user management endpoints."""
    
    def test_read_user_me(self, client: TestClient, auth_headers: dict, test_user: User):
        """Test reading current user profile."""
        response = client.get("/api/v1/users/me", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == test_user.id
        assert data["email"] == test_user.email
        assert data["username"] == test_user.username
        assert data["full_name"] == test_user.full_name
        assert "hashed_password" not in data
    
    def test_read_user_me_unauthorized(self, client: TestClient):
        """Test reading user profile without authentication."""
        response = client.get("/api/v1/users/me")
        assert response.status_code == 401
    
    def test_update_user_me(self, client: TestClient, auth_headers: dict):
        """Test updating current user profile."""
        update_data = {
            "full_name": "Updated Name",
            "phone_number": "+1234567890",
        }
        
        response = client.put(
            "/api/v1/users/me",
            json=update_data,
            headers=auth_headers,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["full_name"] == update_data["full_name"]
        assert data["phone_number"] == update_data["phone_number"]
    
    def test_update_user_email(self, client: TestClient, auth_headers: dict):
        """Test updating user email."""
        update_data = {"email": "newemail@example.com"}
        
        response = client.put(
            "/api/v1/users/me",
            json=update_data,
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["email"] == update_data["email"]
    
    def test_update_user_duplicate_email(
        self, client: TestClient, auth_headers: dict, test_superuser: User
    ):
        """Test updating user with duplicate email."""
        update_data = {"email": test_superuser.email}
        
        response = client.put(
            "/api/v1/users/me",
            json=update_data,
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]
    
    def test_read_users_as_superuser(
        self, client: TestClient, superuser_auth_headers: dict
    ):
        """Test reading all users as superuser."""
        response = client.get("/api/v1/users/", headers=superuser_auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1  # At least the superuser exists
    
    def test_read_users_as_normal_user(self, client: TestClient, auth_headers: dict):
        """Test reading all users as normal user (should fail)."""
        response = client.get("/api/v1/users/", headers=auth_headers)
        assert response.status_code == 403
    
    def test_read_user_by_id_own_profile(
        self, client: TestClient, auth_headers: dict, test_user: User
    ):
        """Test reading own user profile by ID."""
        response = client.get(
            f"/api/v1/users/{test_user.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["id"] == test_user.id
    
    def test_read_user_by_id_other_user(
        self, client: TestClient, auth_headers: dict, test_superuser: User
    ):
        """Test reading other user profile by ID (should fail)."""
        response = client.get(
            f"/api/v1/users/{test_superuser.id}",
            headers=auth_headers,
        )
        assert response.status_code == 403
    
    def test_read_user_by_id_as_superuser(
        self, client: TestClient, superuser_auth_headers: dict, test_user: User
    ):
        """Test reading any user profile by ID as superuser."""
        response = client.get(
            f"/api/v1/users/{test_user.id}",
            headers=superuser_auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["id"] == test_user.id
    
    def test_read_nonexistent_user(
        self, client: TestClient, superuser_auth_headers: dict
    ):
        """Test reading nonexistent user."""
        response = client.get("/api/v1/users/9999", headers=superuser_auth_headers)
        assert response.status_code == 404
    
    def test_delete_user_me(self, client: TestClient, auth_headers: dict):
        """Test deleting own user account."""
        response = client.delete("/api/v1/users/me", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "User deleted successfully"
        
        # Verify user is deleted by trying to access profile
        response = client.get("/api/v1/users/me", headers=auth_headers)
        assert response.status_code == 401
    
    def test_delete_user_as_superuser(
        self, client: TestClient, superuser_auth_headers: dict, test_user: User
    ):
        """Test deleting a user as superuser."""
        response = client.delete(
            f"/api/v1/users/{test_user.id}",
            headers=superuser_auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["message"] == "User deleted successfully"
    
    def test_delete_user_as_normal_user(
        self, client: TestClient, auth_headers: dict, test_superuser: User
    ):
        """Test deleting another user as normal user (should fail)."""
        response = client.delete(
            f"/api/v1/users/{test_superuser.id}",
            headers=auth_headers,
        )
        assert response.status_code == 403
    
    def test_delete_nonexistent_user(
        self, client: TestClient, superuser_auth_headers: dict
    ):
        """Test deleting nonexistent user."""
        response = client.delete(
            "/api/v1/users/9999",
            headers=superuser_auth_headers,
        )
        assert response.status_code == 404