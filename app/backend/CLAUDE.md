# CLAUDE.md - Backend API

FastAPI backend service that exposes REST endpoints for the AI hedge fund web application.

## Architecture

- **Framework**: FastAPI with automatic OpenAPI documentation
- **Database**: SQLAlchemy ORM with Alembic migrations
- **CORS**: Configured for frontend at localhost:5173

## Key Components

### `main.py`
FastAPI application setup with:
- CORS middleware for frontend integration
- Database table initialization
- Router registration

### `routes/`
API endpoint definitions:
- `hedge_fund.py`: Core hedge fund execution endpoints
- `flow_runs.py`: Trading run history and management
- `flows.py`: Flow configuration and templates
- `api_keys.py`: LLM API key management
- `language_models.py`: Available LLM model listings
- `ollama.py`: Local model management
- `health.py`: Health check endpoints
- `storage.py`: File storage and retrieval

### `database/`
- `models.py`: SQLAlchemy model definitions for flows, runs, API keys
- `connection.py`: Database connection configuration
- `alembic/`: Database migration management

### `repositories/`
Data access layer abstractions:
- `flow_repository.py`: Flow data operations
- `flow_run_repository.py`: Run history management  
- `api_key_repository.py`: API key CRUD operations

## Development Commands

**IMPORTANT**: All commands should be run from the project root directory, not from `app/backend/`.

### Start Development Server

**Using Poetry:**
```bash
# From project root
poetry run uvicorn app.backend.main:app --reload --host 127.0.0.1 --port 8000
```

**Using pip (Windows):**
```bash
# From project root
.venv/Scripts/python.exe -m uvicorn app.backend.main:app --reload --host 127.0.0.1 --port 8000
```

**Using pip (Mac/Linux):**
```bash
# From project root  
python -m uvicorn app.backend.main:app --reload --host 127.0.0.1 --port 8000
```

### Database Migrations

**Using Poetry:**
```bash
poetry run alembic upgrade head
poetry run alembic revision --autogenerate -m "description"
```

**Using pip (Windows):**
```bash
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m alembic revision --autogenerate -m "description"
```

### API Documentation
- Available at http://localhost:8000/docs when server is running
- Interactive Swagger UI for testing endpoints
- OpenAPI schema available at http://localhost:8000/openapi.json

## API Patterns

### Request/Response Flow
1. Frontend sends POST requests to `/hedge-fund/run`
2. Backend validates request parameters
3. Calls CLI hedge fund system via subprocess
4. Streams results back to frontend
5. Stores run results in database

### Error Handling
- Pydantic validation for request schemas
- FastAPI automatic error responses
- Custom exception handling for business logic

### Database Integration
- SQLAlchemy models with relationships
- Alembic for schema migrations
- Repository pattern for data access

## Key Endpoints

- `POST /hedge-fund/run`: Execute hedge fund analysis
- `GET /flows`: List available flow configurations
- `GET /flow-runs`: Retrieve run history
- `GET /language-models`: Available LLM models
- `POST /api-keys`: Manage LLM API keys
- `GET /health`: Service health check

## Adding New Endpoints

1. Define Pydantic schemas in `models/schemas.py`
2. Create route handler in appropriate `routes/` file
3. Add database models if needed in `database/models.py`
4. Register router in `routes/__init__.py`
5. Create migration: `alembic revision --autogenerate`