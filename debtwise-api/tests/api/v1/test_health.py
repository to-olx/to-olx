"""
Tests for health check endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient


@pytest.mark.unit
class TestHealth:
    """Test health check endpoints."""
    
    def test_health_check(self, client: TestClient):
        """Test basic health check endpoint."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["service"] == "DebtWise API"
        assert data["version"] == "0.1.0"
        assert data["environment"] == "test"
    
    def test_readiness_check(self, client: TestClient):
        """Test readiness check endpoint."""
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ready"
        assert "timestamp" in data
        assert "checks" in data
        assert data["checks"]["database"] == "healthy"
        assert data["checks"]["redis"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_health_check_async(self, async_client: AsyncClient):
        """Test health check endpoint with async client."""
        response = await async_client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"