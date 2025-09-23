"""
Tests for OpenAPI documentation customization.
"""

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.core.openapi import (
    add_endpoint_examples,
    add_webhook_documentation,
    custom_openapi,
    get_custom_redoc_html,
    get_custom_swagger_ui_html,
)


@pytest.fixture
def sample_app():
    """Create a sample FastAPI app for testing."""
    app = FastAPI()
    
    @app.get("/api/v1/test", tags=["Test"])
    async def test_endpoint():
        """Test endpoint documentation."""
        return {"message": "test"}
    
    @app.post("/api/v1/auth/register", tags=["Authentication"])
    async def register():
        """Register endpoint."""
        return {"id": 1}
    
    @app.post("/api/v1/transactions", tags=["Transactions"])
    async def create_transaction():
        """Create transaction endpoint."""
        return {"id": 1}
    
    return app


class TestOpenAPICustomization:
    """Test OpenAPI documentation customization."""
    
    def test_custom_openapi_generation(self, sample_app):
        """Test custom OpenAPI schema generation."""
        # Generate OpenAPI schema
        schema = custom_openapi(sample_app)
        
        # Verify basic structure
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema
        
        # Verify custom info
        assert schema["info"]["title"] == "DebtWise API"
        assert "Welcome to the DebtWise API" in schema["info"]["description"]
        assert schema["info"]["contact"]["email"] == "api-support@debtwise.com"
        
        # Verify tags
        tags = [tag["name"] for tag in schema["tags"]]
        assert "Health" in tags
        assert "Authentication" in tags
        assert "Transactions" in tags
        
        # Verify servers
        assert len(schema["servers"]) >= 3
        assert any(s["description"] == "Production server" for s in schema["servers"])
        assert any(s["description"] == "Beta server" for s in schema["servers"])
        assert any(s["description"] == "Development server" for s in schema["servers"])
    
    def test_security_schemes(self, sample_app):
        """Test security schemes in OpenAPI."""
        schema = custom_openapi(sample_app)
        
        # Verify security schemes
        assert "components" in schema
        assert "securitySchemes" in schema["components"]
        assert "Bearer" in schema["components"]["securitySchemes"]
        
        # Verify Bearer auth configuration
        bearer = schema["components"]["securitySchemes"]["Bearer"]
        assert bearer["type"] == "http"
        assert bearer["scheme"] == "bearer"
        assert bearer["bearerFormat"] == "JWT"
        
        # Verify global security requirement
        assert "security" in schema
        assert {"Bearer": []} in schema["security"]
    
    def test_response_definitions(self, sample_app):
        """Test common response definitions."""
        schema = custom_openapi(sample_app)
        
        # Verify response components
        responses = schema["components"]["responses"]
        
        # Check common error responses
        assert "UnauthorizedError" in responses
        assert "NotFoundError" in responses
        assert "ValidationError" in responses
        assert "RateLimitError" in responses
        
        # Verify error response structure
        unauthorized = responses["UnauthorizedError"]
        assert unauthorized["description"] == "Authentication information is missing or invalid"
        assert "application/json" in unauthorized["content"]
        assert "example" in unauthorized["content"]["application/json"]
    
    def test_error_schema(self, sample_app):
        """Test error response schema."""
        schema = custom_openapi(sample_app)
        
        # Verify ErrorResponse schema
        assert "ErrorResponse" in schema["components"]["schemas"]
        error_schema = schema["components"]["schemas"]["ErrorResponse"]
        
        assert error_schema["type"] == "object"
        assert "detail" in error_schema["properties"]
        assert "type" in error_schema["properties"]
        assert "status" in error_schema["properties"]
        assert set(error_schema["required"]) == {"detail", "type", "status"}
    
    def test_endpoint_examples(self, sample_app):
        """Test endpoint examples are added."""
        schema = custom_openapi(sample_app)
        
        # Check if examples are added to specific endpoints
        if "/api/v1/auth/register" in schema["paths"]:
            register_endpoint = schema["paths"]["/api/v1/auth/register"]["post"]
            
            # Verify request example
            assert "requestBody" in register_endpoint
            assert "content" in register_endpoint["requestBody"]
            assert "application/json" in register_endpoint["requestBody"]["content"]
            assert "example" in register_endpoint["requestBody"]["content"]["application/json"]
            
            # Verify response example
            assert "responses" in register_endpoint
            if "201" in register_endpoint["responses"]:
                assert "content" in register_endpoint["responses"]["201"]
                assert "application/json" in register_endpoint["responses"]["201"]["content"]
                assert "example" in register_endpoint["responses"]["201"]["content"]["application/json"]
    
    def test_webhook_documentation(self, sample_app):
        """Test webhook documentation."""
        schema = custom_openapi(sample_app)
        
        # Verify webhooks section
        assert "webhooks" in schema
        assert "transaction.created" in schema["webhooks"]
        
        # Verify webhook structure
        webhook = schema["webhooks"]["transaction.created"]["post"]
        assert "requestBody" in webhook
        assert "responses" in webhook
        assert "200" in webhook["responses"]
    
    def test_add_endpoint_examples_function(self):
        """Test add_endpoint_examples function directly."""
        schema = {
            "paths": {
                "/api/v1/auth/register": {
                    "post": {}
                },
                "/api/v1/transactions": {
                    "post": {}
                }
            }
        }
        
        # Add examples
        add_endpoint_examples(schema)
        
        # Verify examples were added
        register = schema["paths"]["/api/v1/auth/register"]["post"]
        assert "requestBody" in register
        assert "example" in register["requestBody"]["content"]["application/json"]
        
        transactions = schema["paths"]["/api/v1/transactions"]["post"]
        assert "requestBody" in transactions
        assert "example" in transactions["requestBody"]["content"]["application/json"]
    
    def test_add_webhook_documentation_function(self):
        """Test add_webhook_documentation function directly."""
        schema = {}
        
        # Add webhook documentation
        add_webhook_documentation(schema)
        
        # Verify webhooks were added
        assert "webhooks" in schema
        assert "transaction.created" in schema["webhooks"]
        
        # Verify webhook content
        webhook = schema["webhooks"]["transaction.created"]["post"]
        assert webhook["requestBody"]["description"] == "Notification sent when a new transaction is created"
        assert "schema" in webhook["requestBody"]["content"]["application/json"]
    
    def test_custom_swagger_ui_html(self):
        """Test custom Swagger UI HTML generation."""
        html = get_custom_swagger_ui_html()
        
        # Verify HTML contains expected elements
        assert isinstance(html, str)
        assert "DebtWise API - Swagger UI" in html
        assert "/api/openapi.json" in html
        assert "swagger-ui.css" in html
        assert "swagger-ui-bundle.js" in html
    
    def test_custom_redoc_html(self):
        """Test custom ReDoc HTML generation."""
        html = get_custom_redoc_html()
        
        # Verify HTML contains expected elements
        assert isinstance(html, str)
        assert "DebtWise API - ReDoc" in html
        assert "/api/openapi.json" in html
        assert "redoc.standalone.js" in html
    
    def test_openapi_caching(self, sample_app):
        """Test OpenAPI schema caching."""
        # First call should generate schema
        schema1 = custom_openapi(sample_app)
        
        # Second call should return cached schema
        schema2 = custom_openapi(sample_app)
        
        # Verify same schema is returned (same object reference)
        assert schema1 is schema2
    
    def test_openapi_description_formatting(self, sample_app):
        """Test OpenAPI description formatting."""
        schema = custom_openapi(sample_app)
        
        description = schema["info"]["description"]
        
        # Verify markdown formatting is preserved
        assert "# DebtWise API Documentation" in description
        assert "## Features" in description
        assert "## Getting Started" in description
        assert "## Rate Limiting" in description
        assert "## Response Format" in description
        assert "## Authentication" in description
        assert "## Support" in description
        
        # Verify feature list
        assert "🔐 **Secure Authentication**" in description
        assert "💰 **Transaction Management**" in description
        assert "💳 **Debt Management**" in description
        assert "📊 **Budget Planning**" in description
        assert "📈 **Analytics & Insights**" in description
        assert "🔒 **Security First**" in description