# DebtWise API

A modern, scalable backend API for DebtWise - a personal finance application that helps users track spending, manage debt, budget effectively, and get predictive insights.

## 🚀 Features

- **FastAPI Framework**: High-performance, async Python web framework
- **JWT Authentication**: Secure user authentication with access and refresh tokens
- **User Management**: Registration, login, profile management
- **Spending Tracking**: 
  - Transaction management with income/expense tracking
  - Hierarchical category system with budget tracking
  - Auto-categorization rules with pattern matching
  - CSV import for bulk transaction upload
  - Spending analytics and trends
- **Debt Management**: Track and manage various types of debt
- **Analytics System**: Track user interactions and API usage
- **Rate Limiting**: Protect API from abuse
- **Structured Logging**: JSON-formatted logs with request tracking
- **Docker Support**: Containerized application for easy deployment
- **Comprehensive Testing**: Unit and integration tests with PyTest
- **CI/CD Pipeline**: Automated testing and deployment with GitHub Actions

## 📋 Prerequisites

- Python 3.11+
- PostgreSQL 16+
- Redis 7+
- Docker and Docker Compose (optional)

## 🛠️ Installation

### Using uv (Recommended)

1. Install uv package manager:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Clone the repository:
```bash
git clone <repository-url>
cd debtwise-api
```

3. Install dependencies:
```bash
uv sync --all-extras
```

### Using Docker

```bash
docker-compose up -d
```

This will start:
- PostgreSQL database
- Redis server
- DebtWise API
- Adminer (database admin tool)

## ⚙️ Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Update the `.env` file with your configuration:
- Database credentials
- Redis connection
- JWT secrets
- CORS origins

### Environment Variables

Key environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `SECRET_KEY` | Application secret key | Required |
| `JWT_SECRET_KEY` | JWT signing key | Required |
| `DEBUG` | Debug mode | `false` |
| `ENVIRONMENT` | Environment name | `development` |

## 🏃‍♂️ Running the Application

### Development Server

```bash
uv run python main.py
```

Or with auto-reload:
```bash
uv run uvicorn app.main:app --reload
```

### Production Server

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Using Docker

```bash
docker-compose up
```

## 📚 API Documentation

Once the application is running, you can access:

- **Interactive API docs**: http://localhost:8000/api/docs
- **Alternative API docs**: http://localhost:8000/api/redoc
- **OpenAPI schema**: http://localhost:8000/api/openapi.json

### Feature Documentation

- **[Spending Feature](docs/SPENDING_FEATURE.md)**: Complete guide to transaction tracking, categories, rules, and CSV import
- **[Debt Management](docs/DEBT_MANAGEMENT.md)**: Guide to debt tracking and management features

## 🧪 Testing

### Run all tests

```bash
uv run pytest
```

### Run with coverage

```bash
uv run pytest --cov=app --cov-report=html
```

### Run specific test categories

```bash
# Unit tests only
uv run pytest -m unit

# Integration tests only
uv run pytest -m integration

# Authentication tests
uv run pytest -m auth
```

## 🔧 Development Tools

### Code Formatting

```bash
uv run black app tests
```

### Linting

```bash
uv run ruff check app tests
```

### Type Checking

```bash
uv run mypy app
```

### Pre-commit Hooks

Install pre-commit hooks:
```bash
uv run pre-commit install
```

## 📁 Project Structure

```
debtwise-api/
├── app/
│   ├── api/               # API endpoints
│   │   ├── dependencies.py # Auth dependencies
│   │   └── v1/            # API version 1
│   │       ├── endpoints/ # Endpoint modules
│   │       └── router.py  # Main API router
│   ├── core/              # Core functionality
│   │   ├── config.py      # Settings management
│   │   ├── database.py    # Database configuration
│   │   ├── logging.py     # Logging setup
│   │   ├── middleware.py  # Custom middleware
│   │   └── security.py    # Security utilities
│   ├── models/            # Database models
│   ├── schemas/           # Pydantic schemas
│   ├── services/          # Business logic
│   │   └── analytics.py   # Analytics service
│   └── main.py            # FastAPI app
├── tests/                 # Test suite
├── .env.example           # Environment example
├── docker-compose.yml     # Docker composition
├── Dockerfile             # Container definition
├── pyproject.toml         # Project dependencies
└── README.md             # This file
```

## 🚀 API Endpoints

### Authentication
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/refresh` - Refresh access token
- `POST /api/v1/auth/change-password` - Change password
- `POST /api/v1/auth/logout` - Logout

### Users
- `GET /api/v1/users/me` - Get current user
- `PUT /api/v1/users/me` - Update current user
- `DELETE /api/v1/users/me` - Delete current user
- `GET /api/v1/users/` - List all users (admin)
- `GET /api/v1/users/{id}` - Get user by ID

### Health
- `GET /api/v1/health` - Health check
- `GET /api/v1/health/ready` - Readiness check

### Analytics
- `GET /api/v1/analytics/user/me/events` - Get user events
- `GET /api/v1/analytics/events/count` - Event counts (admin)

## 🔐 Security Features

- **Password Hashing**: Bcrypt with automatic salt
- **JWT Tokens**: Separate access and refresh tokens
- **Rate Limiting**: Configurable per-minute limits
- **CORS**: Configurable allowed origins
- **Request ID**: Unique ID for request tracking

## 📊 Analytics

The API includes a comprehensive analytics system that tracks:

- User signups and logins
- API requests and response times
- Error rates and types
- Rate limit violations
- User activity patterns

Analytics data is stored in Redis with configurable retention periods.

## 🐳 Docker Deployment

Build the production image:

```bash
docker build --target production -t debtwise-api .
```

Run the container:

```bash
docker run -p 8000:8000 --env-file .env debtwise-api
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## 📄 License

[Add your license here]

## 👥 Team

[Add team information here]