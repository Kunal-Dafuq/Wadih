# Wadih — Backend API

Backend foundation and CRUD service for **Wadih**, a privacy-first educational platform for synthetic inherited-disease carrier screening, consent clarity, and simulated counselling navigation.

## Architecture & Scope

This service represents the **Backend Foundation and CRUD** layer owned by **Kunal**, providing:
- FastAPI application and modular routing structure.
- PostgreSQL / SQLite SQLAlchemy ORM persistence models.
- Alembic database migration management.
- Authentication foundation (demo accounts, bcrypt password hashing, signed JWT tokens, logout invalidation).
- Participant profile management and preferences.
- Synthetic screening cases & finding records CRUD (strict owner-isolation).
- Educational content retrieval & teach-back comprehension assessments.
- Simulated referral task records and status tracking.
- Standardized API error envelopes conforming to the Wadih API contract.

### Teammate Ownership Boundaries
- **Niharika (Advanced Backend)**: Genetic risk calculation engine, advanced consent grant lifecycle, granular recipient/resource/scope sharing rules, revocation enforcement, and clinical escalation policies.
- **Saiesha (Frontend)**: React, TypeScript, Tailwind CSS, dashboard, screening result viewer, and UI components.

## Requirements

- Python 3.12+ (tested on Python 3.13)
- PostgreSQL (or SQLite for local development and automated testing)

## Setup & Local Development

1. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -e ".[dev]"
   ```

3. **Configure environment:**
   Copy `.env.example` to `.env` and adjust settings as needed:
   ```bash
   cp .env.example .env
   ```

4. **Run migrations:**
   ```bash
   alembic upgrade head
   ```

5. **Seed demo data:**
   ```bash
   python -m app.seed.seed_demo
   ```

6. **Start development server:**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

7. **Access API Documentation:**
   - Interactive Swagger UI: `http://localhost:8000/docs`
   - ReDoc: `http://localhost:8000/redoc`
   - Health Check: `http://localhost:8000/health`

## Automated Testing

Run the test suite with pytest:
```bash
pytest
```
