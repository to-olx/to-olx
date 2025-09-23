"""
OpenAPI documentation configuration and customization.
"""

from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi

from app.core.config import settings


def custom_openapi(app: FastAPI) -> Dict[str, Any]:
    """
    Generate custom OpenAPI schema with enhanced documentation.
    """
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="DebtWise API",
        version=settings.app_version,
        description="""
# DebtWise API Documentation

Welcome to the DebtWise API! This API powers a comprehensive personal finance management platform.

## Features

- 🔐 **Secure Authentication**: JWT-based authentication with refresh tokens
- 💰 **Transaction Management**: Track income and expenses with categorization
- 💳 **Debt Management**: Monitor and manage various types of debt
- 📊 **Budget Planning**: Create and track budgets with real-time status
- 📈 **Analytics & Insights**: Get AI-powered financial insights
- 🔒 **Security First**: Industry-standard security practices including rate limiting and encryption

## Getting Started

1. **Register**: Create an account using the `/auth/register` endpoint
2. **Login**: Authenticate using `/auth/login` to receive access tokens
3. **Explore**: Use the access token in the `Authorization: Bearer <token>` header

## Rate Limiting

API endpoints are rate-limited based on tiers:
- **Authentication**: 5 requests per 5 minutes
- **General API**: 60 requests per minute
- **Write Operations**: 30 requests per minute
- **Sensitive Data**: 10 requests per minute

## Response Format

All responses follow a consistent format:

### Success Response
```json
{
    "data": {},
    "message": "Success",
    "status": "success"
}
```

### Error Response
```json
{
    "detail": "Error description",
    "type": "error_type",
    "status": "error"
}
```

## Authentication

DebtWise uses JWT (JSON Web Tokens) for authentication:

1. **Login** to receive an access token and refresh token
2. Include the access token in all authenticated requests:
   ```
   Authorization: Bearer <access_token>
   ```
3. **Refresh** your access token before it expires using the refresh endpoint

## Support

For API support, please contact: api-support@debtwise.com

## Terms of Service

By using this API, you agree to our [Terms of Service](https://debtwise.com/terms)
        """,
        routes=app.routes,
        tags=[
            {
                "name": "Health",
                "description": "API health check endpoints",
            },
            {
                "name": "Authentication",
                "description": "User authentication and token management",
            },
            {
                "name": "Users",
                "description": "User profile and account management",
            },
            {
                "name": "Transactions",
                "description": "Financial transaction tracking and management",
            },
            {
                "name": "Debts",
                "description": "Debt tracking and management",
            },
            {
                "name": "Budgets",
                "description": "Budget creation and monitoring",
            },
            {
                "name": "Analytics",
                "description": "Financial analytics and reporting",
            },
            {
                "name": "Insights",
                "description": "AI-powered financial insights and recommendations",
            },
        ],
        servers=[
            {
                "url": "https://api.debtwise.com",
                "description": "Production server",
            },
            {
                "url": "https://beta-api.debtwise.com",
                "description": "Beta server",
            },
            {
                "url": "http://localhost:8000",
                "description": "Development server",
            },
        ],
        contact={
            "name": "DebtWise API Support",
            "url": "https://debtwise.com/api-support",
            "email": "api-support@debtwise.com",
        },
        license_info={
            "name": "Proprietary",
            "url": "https://debtwise.com/license",
        },
    )
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "Bearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter the JWT token received from login endpoint",
        }
    }
    
    # Add global security requirement
    openapi_schema["security"] = [{"Bearer": []}]
    
    # Add response examples
    openapi_schema["components"]["responses"] = {
        "UnauthorizedError": {
            "description": "Authentication information is missing or invalid",
            "content": {
                "application/json": {
                    "schema": {
                        "$ref": "#/components/schemas/ErrorResponse"
                    },
                    "example": {
                        "detail": "Could not validate credentials",
                        "type": "authentication_error",
                        "status": "error"
                    }
                }
            }
        },
        "NotFoundError": {
            "description": "The requested resource was not found",
            "content": {
                "application/json": {
                    "schema": {
                        "$ref": "#/components/schemas/ErrorResponse"
                    },
                    "example": {
                        "detail": "Resource not found",
                        "type": "not_found",
                        "status": "error"
                    }
                }
            }
        },
        "ValidationError": {
            "description": "Invalid input data",
            "content": {
                "application/json": {
                    "schema": {
                        "$ref": "#/components/schemas/HTTPValidationError"
                    }
                }
            }
        },
        "RateLimitError": {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "schema": {
                        "$ref": "#/components/schemas/ErrorResponse"
                    },
                    "example": {
                        "detail": "Rate limit exceeded. Please try again later.",
                        "type": "rate_limit_exceeded",
                        "status": "error"
                    }
                }
            }
        },
    }
    
    # Add common schemas
    openapi_schema["components"]["schemas"]["ErrorResponse"] = {
        "type": "object",
        "properties": {
            "detail": {"type": "string"},
            "type": {"type": "string"},
            "status": {"type": "string", "enum": ["error"]},
        },
        "required": ["detail", "type", "status"],
    }
    
    # Add example data for better documentation
    add_endpoint_examples(openapi_schema)
    
    # Add webhook documentation if applicable
    add_webhook_documentation(openapi_schema)
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


def add_endpoint_examples(schema: Dict[str, Any]) -> None:
    """Add request/response examples to endpoints."""
    # Add examples for specific paths
    paths_examples = {
        "/api/v1/auth/register": {
            "post": {
                "requestBody": {
                    "content": {
                        "application/json": {
                            "example": {
                                "email": "user@example.com",
                                "password": "SecurePassword123!",
                                "full_name": "John Doe"
                            }
                        }
                    }
                },
                "responses": {
                    "201": {
                        "content": {
                            "application/json": {
                                "example": {
                                    "id": 1,
                                    "email": "user@example.com",
                                    "full_name": "John Doe",
                                    "is_active": True,
                                    "created_at": "2024-01-15T10:30:00Z"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/v1/transactions": {
            "post": {
                "requestBody": {
                    "content": {
                        "application/json": {
                            "example": {
                                "amount": 125.50,
                                "category": "Food",
                                "description": "Grocery shopping at SuperMart",
                                "date": "2024-01-15",
                                "type": "expense",
                                "tags": ["groceries", "essential"]
                            }
                        }
                    }
                }
            }
        }
    }
    
    # Merge examples into schema
    for path, methods in paths_examples.items():
        if path in schema.get("paths", {}):
            for method, content in methods.items():
                if method in schema["paths"][path]:
                    schema["paths"][path][method].update(content)


def add_webhook_documentation(schema: Dict[str, Any]) -> None:
    """Add webhook documentation if webhooks are supported."""
    # Example webhook documentation
    schema["webhooks"] = {
        "transaction.created": {
            "post": {
                "requestBody": {
                    "description": "Notification sent when a new transaction is created",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "event": {"type": "string", "example": "transaction.created"},
                                    "data": {
                                        "type": "object",
                                        "properties": {
                                            "transaction_id": {"type": "integer"},
                                            "amount": {"type": "number"},
                                            "category": {"type": "string"},
                                            "timestamp": {"type": "string", "format": "date-time"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Notification processed successfully"
                    }
                }
            }
        }
    }


def get_custom_swagger_ui_html() -> str:
    """Get customized Swagger UI HTML."""
    return get_swagger_ui_html(
        openapi_url="/api/openapi.json",
        title="DebtWise API - Swagger UI",
        oauth2_redirect_url="/api/docs/oauth2-redirect",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
    )


def get_custom_redoc_html() -> str:
    """Get customized ReDoc HTML."""
    return get_redoc_html(
        openapi_url="/api/openapi.json",
        title="DebtWise API - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
        redoc_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
        with_google_fonts=True,
    )