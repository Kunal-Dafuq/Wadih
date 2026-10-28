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

### Niharika's Assigned Scope (Implemented, Audited & Hardened)
- Deterministic genetic risk engine for Autosomal Recessive conditions:
  - Dual confirmed carriers: 25% affected, 50% carrier, 25% non-carrier per pregnancy.
  - Single carrier + negative partner: Server-controlled clinical provenance modeling (`P(affected) = r × 1/4`).
  - Zero Client-Side Provenance Trust: Client booleans or free-text source names cannot self-certify clinical provenance; residual risk must be verified against an authoritative `ClinicalResidualRiskRecord` signed off by an authorized clinician.
  - Case-Level & Couple-Referral Authorization: Ingestion (`/api/v1/clinical/provenance`) requires counsellors to be assigned to the case directly or hold an active referral for a partner participant who has an active `ConsentGrant` with the case owner. Unassigned counsellors fail closed with 403 Forbidden.
  - Strict clinical safety guardrails: Suppresses numerical probabilities (`INSUFFICIENT_DATA` / `REVIEW_REQUIRED` with `risk_estimate=null`) when residual risk `r` or provenance is unverified. Rejects zero-risk claims for negative screening panels (`EDUCATIONAL_RESULT` with `risk_estimate=null`).
  - Clinician-reviewed and sufficient-findings validation gates.
  - Automatic escalation triggers for VUS, unreviewed data, and affected phenotypes.
- Granular consent management & partner-sharing lifecycle:
  - Scopes: `carrier_status_only` (field-level redaction), `summary_only`, `full_report`.
  - Transactionally atomic consent grant, approve, and revoke operations with immediate access denial upon revocation or expiration.
  - Direct case details (`/api/v1/cases/{case_id}`) guarded by IDOR checks, permitting cross-account access only under explicit active `full_report` consent.
- Least-privilege security audit logging & immutability:
  - Automatic credential and genomic sequence sanitization (raw variant strings, passwords, tokens redacted).
  - Role-based scoping: Counsellors restricted strictly to assigned cases, referrals, or their own actions. Unrelated cases or general account actions performed by assigned participants are strictly filtered out. Patients forbidden (403); Admins retain full audit visibility.
  - Immutability: Application & ORM layer strictly prohibits updates and deletions via SQLAlchemy mapper listeners and SessionEvents.do_orm_execute bulk guards; zero modification API routes exposed. (Physical database immutability against direct SQL superusers requires database-level privilege revocation or cloud WORM sinks).
  - Atomic transaction commits ensuring business state changes and audit records persist or roll back together.

### Saiesha's Frontend Interfaces
- Saiesha (`saiesha/frontend`):
  - React/TypeScript frontend consuming the `/api/v1` endpoints documented in `docs/API_CONTRACT_NIHARIKA.md`.

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
| `POST` | `/api/v1/risk/assess` | Yes | Calculate deterministic Mendelian recurrence risk |
| `POST` | `/api/v1/risk/cases/{case_id}/assess` | Yes | Secure risk calculation via POST body (prevents log leakage; requires server provenance) |
| `GET` | `/api/v1/risk/cases/{case_id}` | Yes | Legacy risk calculation from stored case (deprecated) |
| `POST` | `/api/v1/clinical/provenance` | Yes (Counsellor/Admin) | Record authoritative clinician-reviewed residual-risk provenance |
| `POST` | `/api/v1/consents` | Yes | Create granular consent grant (carrier_status_only, summary_only, full_report) |
| `GET` | `/api/v1/consents` | Yes | List active and historical consent grants for user |
| `GET` | `/api/v1/consents/{consent_id}` | Yes | Consent grant detail (granter/grantee restricted) |
| `POST` | `/api/v1/consents/{consent_id}/approve` | Yes | Explicitly approve pending consent request (granter only) |
| `POST` | `/api/v1/consents/{consent_id}/revoke` | Yes | Immediately revoke consent grant |
| `POST` | `/api/v1/sharing/requests` | Yes | Create partner sharing invitation request (PENDING) |
| `GET` | `/api/v1/sharing/shared-cases/{case_id}` | Yes | Access shared findings strictly filtered by granted scope |
| `GET` | `/api/v1/audit/events` | Yes (Admin/Counsellor) | Inspect immutable security audit events (sanitized) |
| `POST` | `/api/v1/counselling/escalations` | Yes | Clinically escalate case to genetic counselling |
| `GET` | `/api/v1/counselling/escalations/check/{case_id}` | Yes | Deterministic escalation trigger scanner for case findings |

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
