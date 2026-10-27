# Wadih — Backend API Foundation & Documentation

Backend foundation and CRUD service for **Wadih** (Future Health Digital Innovation Challenge — Fertility, Challenge 03).

Wadih is a privacy-first educational and demonstration platform that assists individuals and couples in understanding synthetic inherited-disease screening results, managing data sharing consent, testing their comprehension through teach-back assessments, and navigating simulated genetic counselling pathways.

> **Responsible Demonstration Disclaimer:**
> Wadih is an educational demonstration prototype. It uses only synthetic data scenarios and does not diagnose genetic conditions, calculate personalized medical risk probabilities with AI, or provide real-world clinical prescriptions.

---

## 1. System Architecture & Ownership Boundaries

The Wadih engineering team operates under strict modular responsibility isolation:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Wadih Application                               │
├──────────────────────┬────────────────────────┬────────────────────────┤
│ Kunal                │ Niharika               │ Saiesha                │
│ (Backend Foundation) │ (Advanced Backend)     │ (Frontend & UX)        │
├──────────────────────┼────────────────────────┼────────────────────────┤
│ • FastAPI Structure  │ • Risk Engine          │ • React / Vite / TS    │
│ • PostgreSQL/ORM     │ • Consent Lifecycle    │ • Tailwind CSS         │
│ • Alembic Migrations │ • Partner Sharing Auth │ • Dashboard UI         │
│ • Auth & Sessions    │ • Revocation Policies  │ • Result Visualizer    │
│ • User Profiles      │ • Security Auditing    │ • Consent Screens      │
│ • Synthetic Cases    │ • Clinical Escalations │ • Counsellor Portal    │
│ • Educational Content│                        │ • Client Integration   │
│ • Referral Tasks     │                        │                        │
└──────────────────────┴────────────────────────┴────────────────────────┘
```

### Kunal's Assigned Scope (Implemented & Tested)
- Application scaffolding, settings configuration, and CORS management.
- PostgreSQL database models & Alembic schema migrations.
- Demo authentication system with bcrypt password hashing and JWT token management.
- Server-side logout token revocation / blacklisting.
- Participant profile management with communication and literacy preferences.
- Synthetic screening cases & findings CRUD with strict owner-isolation.
- Versioned educational content storage and teach-back comprehension assessment engine.
- Simulated referral tasks and counsellor notes persistence.
- Standardized API error envelopes conforming to the unified error contract.
- Comprehensive automated test suite with pytest.

### Teammate Interfaces & Remaining Dependencies
- **Niharika (`niharika/advanced-backend`)**:
  - Deterministic genetic risk calculation engine (cross-carrier matching).
  - Granular recipient/resource/scope consent grant management.
  - Revocation enforcement logic.
  - Security audit log persistence.
  - Clinical escalation review policies.
  *Note: Endpoints requiring partner-sharing or clinical escalation deny unauthorized access until Niharika's policy engine is integrated.*
- **Saiesha (`saiesha/frontend`)**:
  - React/TypeScript frontend consuming the `/api/v1` endpoints documented below.

---

## 2. API Contract & Endpoints

All endpoints are prefixed with `/api/v1` and return JSON payloads.

### Standard Error Response Envelope
Every error follows the standardized envelope:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable explanation.",
    "request_id": "req_8f10f56a"
  }
}
```
Supported error codes:
- `UNAUTHENTICATED` (401)
- `FORBIDDEN` (403)
- `NOT_FOUND` (404)
- `VALIDATION_ERROR` (422)
- `CONSENT_REQUIRED` (403)
- `NEEDS_CLINICIAN_REVIEW` (403)
- `INTERNAL_ERROR` (500)

### Endpoint Inventory

| Method | Path | Auth Required | Description |
|---|---|---|---|
| `GET` | `/health` | No | System health and environment status |
| `POST` | `/api/v1/auth/login` | No | Demo login; returns JWT access token |
| `POST` | `/api/v1/auth/logout` | Yes | Revokes the current session token |
| `GET` | `/api/v1/me` | Yes | Current user identity and preferences |
| `GET` | `/api/v1/users/me` | Yes | Detailed user profile information |
| `GET` | `/api/v1/users/me/profile` | Yes | Participant profile & literacy settings |
| `PATCH` | `/api/v1/users/me/profile` | Yes | Update display name, language, or literacy |
| `GET` | `/api/v1/cases` | Yes | List synthetic screening cases owned by caller |
| `GET` | `/api/v1/cases/{case_id}` | Yes | Case details and findings (owner-isolated) |
| `GET` | `/api/v1/cases/{case_id}/explanation` | Yes | Reviewed educational content & teach-back questions |
| `POST` | `/api/v1/cases/{case_id}/knowledge-check` | Yes | Submit teach-back answers & record attempt |
| `POST` | `/api/v1/referrals` | Yes | Create simulated referral task for case |
| `GET` | `/api/v1/referrals` | Yes | List participant's referrals or counsellor's assignments |
| `GET` | `/api/v1/referrals/{referral_id}` | Yes | Referral details and counsellor notes |
| `PATCH` | `/api/v1/referrals/{referral_id}/status` | Yes | Update status (PENDING, SCHEDULED, COMPLETED, CANCELLED) |
| `POST` | `/api/v1/referrals/{referral_id}/notes` | Yes (Counsellor) | Author clinical/counselling session note |

---

## 3. Local Setup & Execution Guide

### Prerequisites
- Python 3.12+ (tested on Python 3.13)
- PostgreSQL (or built-in SQLite for zero-setup local dev & tests)

### Step 1: Virtual Environment
```bash
cd backend
python -m venv .venv

# On Windows:
.venv\Scripts\activate

# On Linux/macOS:
source .venv/bin/activate
```

### Step 2: Install Dependencies
```bash
pip install -e ".[dev]"
```

### Step 3: Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Default `.env` configuration uses SQLite (`sqlite:///./wadih_dev.db`). For PostgreSQL:
```ini
DATABASE_URL="postgresql+psycopg2://user:password@localhost:5432/wadih_db"
```

### Step 4: Run Migrations
```bash
alembic upgrade head
```

### Step 5: Seed Demo Accounts & Synthetic Cases
```bash
python -m app.seed.seed_demo
```
This populates three demo accounts:
- **Patient A (Carrier)**: `patient.a@wadih.demo` / `DemoPassword123!` (Beta Thalassemia carrier finding)
- **Patient B (Partner)**: `patient.b@wadih.demo` / `DemoPassword123!` (Negative screen)
- **Genetic Counsellor**: `counsellor@wadih.demo` / `DemoPassword123!` (Dr. Sarah Chen, MS CGC)

### Step 6: Start Development Server
```bash
uvicorn app.main:app --reload --port 8000
```
Interactive documentation:
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Step 7: Run Automated Tests
```bash
pytest
```
