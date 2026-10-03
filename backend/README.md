# PulseOps Backend Service

FastAPI async backend service for telemetry ingestion, metric aggregation, alert evaluation, incident tracking, and advisory AI analysis.

## Structure

- `alembic/`: Database migration scripts and configuration
- `app/api/`: REST API route endpoints (Auth, Health, dependencies)
- `app/core/`: Application settings, security utilities, audit logging, brute-force protection
- `app/db/`: Database session management (`session.py`), metadata loader (`base.py`), seed script (`seed.py`), and repositories (`repositories/user_repository.py`)
- `app/models/`: SQLAlchemy 2.0 ORM database models (`user`, `service`, `telemetry`, `alert`, `incident`)
- `app/schemas/`: Pydantic request/response payload contracts
- `app/services/`: Core domain business logic
- `app/middleware/`: Request ID correlation, HTTP logging, Security Headers, Max Payload Size middleware
- `app/main.py`: FastAPI application factory entry point

## Database Integration & Setup (PostgreSQL + SQLAlchemy 2.0 Async + Alembic)

PulseOps uses PostgreSQL with SQLAlchemy 2.0 Async Engine (`asyncpg`) for operational persistence.

### 1. Environment Configuration
Environment settings are loaded via `.env` (never hardcoded in source code):
- `DATABASE_URL`: `postgresql+asyncpg://pulseops:pulseops_dev_pass@localhost:5432/pulseops_db`
- `POSTGRES_USER`: `pulseops`
- `POSTGRES_PASSWORD`: `pulseops_dev_pass`
- `POSTGRES_DB`: `pulseops_db`

### 2. Running Database Migrations
Apply Alembic migrations to construct database schema:
```bash
# Upgrade database to head revision
alembic upgrade head

# Rollback last migration
alembic downgrade -1
```

### 3. Development Seed Data
Seed initial development accounts, default monitored service (`demo-app`), and alert rules:
```bash
# Run seed script using environment variables for seed credentials
python -m app.db.seed
```
*Note: Seed credentials (`SEED_ADMIN_PASSWORD`, `SEED_USER_PASSWORD`) are for local development ONLY. Production deployments must not use default seed passwords.*

### 4. Running Automated Tests
The backend test suite uses isolated async database sessions with full foreign-key constraints and schema validation:
```bash
# Run all backend unit and database tests
pytest backend/tests
```

### 5. Common Setup Errors & Troubleshooting
- **`ModuleNotFoundError: No module named 'passlib'` or `asyncpg`**: Ensure virtual environment is activated (`venv\Scripts\activate` or `source venv/bin/activate`).
- **`asyncpg.exceptions.CannotConnectNowError`**: Verify PostgreSQL container or service is running on specified host and port.
- **`alembic.util.exc.CommandError: Can't locate revision`**: Run `alembic upgrade head` from `backend/` working directory.

