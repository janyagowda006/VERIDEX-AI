# VERIDEX — Evidence-First AI Decision Intelligence

> **"AI for reasoning, code for correctness."**

VERIDEX is an enterprise-grade, evidence-first AI decision intelligence platform designed to investigate business questions using structured business data, execute deterministic calculation tools, present verifiable evidence taxonomy, evaluate actionable recommendations, test finding robustness under alternate assumptions, and keep final decisions under human control.

---

## 🎯 Problem Statement

Modern enterprise business users possess data spread across relational databases, data warehouses, and spreadsheets. Traditional decision analysis requires manually discovering schemas, authoring complex SQL queries, cross-checking statistical calculations, interpreting variance drivers, and drafting recommendations. Standard conversational AI tools can write plausible answers but lack a verifiable, deterministic trail back to underlying raw data.

VERIDEX solves this problem by pairing a custom single-investigator Python agent loop with typed analytical tools. The LLM selects tools and reasons over structured outputs, while deterministic Python/SQL code executes arithmetic, difference-in-differences lift estimation, driver decomposition, claim verification, and robustness testing.

---

## 🔒 Core Architectural Principles & Guardrails

```text
User Business Question
        ↓
Custom Python Investigator Loop (Single Agent)
        ↓
Typed Tool Registry
  ├── Safe Read-Only SQL Tool (SQLGlot AST Safety Validation)
  ├── Driver Decomposition Tool (Variance Breakdown across Dimensions)
  ├── Campaign Impact Tool (Difference-in-Differences Observational Lift)
  └── Numerical Claim Verification Tool (Relative Error Claim Checker)
        ↓
Evidence Assembler & Calculation Engine
        ↓
Categorized Evidence Taxonomy:
  ├── FACT (Direct database query rows & provenance metadata)
  ├── DERIVED_FACT (Deterministic mathematical formulas & outputs)
  └── INFERENCE (Qualitative LLM synthesis from evidence)
        ↓
Deterministic Decision Engine & Robustness Engine
        ↓
Structured Decision Analysis & Robustness Status:
  ├── STABLE (Findings consistent across alternate scenarios)
  ├── SENSITIVE (Recommendation changes under metric perturbation)
  └── INSUFFICIENT_EVIDENCE (Missing data or sample size N < 15)
        ↓
Actionable Recommendation & Human-in-the-Loop Review
        ↓
Human Approve / Reject / Flag (RBAC & Owner Self-Review Protection)
        ↓
Persisted Investigation & Enterprise Audit Trail
```

### Key Architectural Rules
1. **Single Investigator Loop**: Custom Python tool-calling loop (No LangGraph, no multi-agent frameworks, no microservices, no unnecessary MCP layer).
2. **Structural Evidence Taxonomy**:
   - **FACT**: Directly returned from executed tool queries (e.g., SQL output: `revenue = $4.82M`).
   - **DERIVED_FACT**: Deterministically computed from verified facts (e.g., `revenue growth = -18.2%`).
   - **INFERENCE**: Qualitative LLM interpretation linked to evidence IDs (e.g., "Decline associated with promo end").
3. **Deterministic Decision & Robustness Engine**:
   - Python code performs candidate ranking, threshold comparisons (`>=`, `<=`, `==`), scenario sensitivity analysis, and robustness classification (`STABLE`, `SENSITIVE`, `INSUFFICIENT_EVIDENCE`).
   - Zero arbitrary AI confidence percentages. Recommendations link directly to supporting evidence IDs.
4. **Strict Security & RBAC**:
   - Role-Based Access Control (`ANALYST`, `REVIEWER`, `AUDITOR`, `ADMIN`).
   - Owner self-review prevention (`403 Forbidden`).
   - Safe read-only SQL execution validated via SQLGlot AST parsing (rejects `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, and multi-statement queries).

---

## 🚀 Final Release Status: Complete (Phases 1–13 Verified)

> [!NOTE]
> **Production Readiness**: VERIDEX has completed all 13 development, integration, hardening, and release readiness phases. All 433 backend unit/integration tests pass cleanly, frontend linting reports 0 errors, production build succeeds, and end-to-end API smoke tests verify 100% functionality.

| Component | Status | Description |
| :--- | :--- | :--- |
| **Backend API** | ✅ Release Ready | FastAPI app with health, ask, investigation persistence, review, reassessment, audit logs, and tool endpoints |
| **Investigator Loop** | ✅ Release Ready | Bounded custom Python tool-calling loop with multi-turn continuation support |
| **SQL Query Tool** | ✅ Release Ready | Read-only SQL executor with SQLGlot AST safety validation & limit injection |
| **Driver Decomposition** | ✅ Release Ready | Deterministic metric variance breakdown across dimensions (region, category, segment, customer) |
| **Campaign Impact / DiD** | ✅ Release Ready | Difference-in-Differences observational lift estimation with $N \ge 15$ sample size validation |
| **Claim Verification** | ✅ Release Ready | Deterministic numerical claim checker skipping entity IDs (`ORD-101`, `CUST-202`) |
| **Decision Engine** | ✅ Release Ready | Deterministic candidate scoring, criteria weighting, and decision card generation |
| **Robustness Engine** | ✅ Release Ready | Multi-scenario perturbation testing returning `STABLE`, `SENSITIVE`, or `INSUFFICIENT_EVIDENCE` |
| **Evidence Assembler** | ✅ Release Ready | Automated extraction and provenance tagging for `FACT` and `DERIVED_FACT` items |
| **Human Review / HITL** | ✅ Release Ready | Executive review panel supporting `APPROVED`, `REJECTED`, `FLAGGED` decisions with owner self-review protection |
| **RBAC & Security** | ✅ Release Ready | JWT authentication, role enforcement, and audit log event tracking (`AuditLogger`) |
| **Frontend UI** | ✅ Release Ready | Reconstructed 11-page React SPA (Workspace, Evidence Explorer, Decision, Robustness, History, Audit Trail) |
| **Database & Docker** | ✅ Release Ready | PostgreSQL 16 schema with synthetic data generator (`seed=42`) and Docker Compose orchestration |
| **Automated Tests** | ✅ Release Ready | 433 backend Pytest unit/integration tests passing (100% pass rate) |

---

## 🛠️ Technology Stack

- **Backend**: Python 3.14+, FastAPI, Uvicorn, Pydantic 2.x, SQLAlchemy 2.0, SQLGlot, Google GenAI SDK, Psycopg2, Pandas, Pytest
- **Frontend**: React 19, Vite, JavaScript (ES2024), CSS3
- **Database**: PostgreSQL 16 (or SQLite in-memory for testing)
- **Containerization**: Docker, Docker Compose, Nginx

---

## 💻 Setup & Installation Instructions

### Prerequisites
- Python 3.10+
- Node.js 18+ & npm
- Docker & Docker Compose (optional for PostgreSQL container)

### 1. Environment Configuration
Copy `.env.example` to `backend/.env` or configure root `.env`:
```bash
# Target Database (SQLite default for quick local testing)
DATABASE_URL=sqlite:///./veridex_dev.db

# For PostgreSQL Container:
# DATABASE_URL=postgresql+psycopg2://veridex:veridex_pass@localhost:5435/veridex

# Security & Secrets
SECRET_KEY=veridex_super_secret_jwt_key_change_in_production_32bytes!
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480

# LLM Provider Configuration (mock, gemini, openai, anthropic)
LLM_PROVIDER=mock
GEMINI_API_KEY=your_gemini_api_key_here
```

### 2. Backend Setup
```bash
cd backend
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Frontend Setup
```bash
cd frontend
npm install
```

---

## 🏃 Running the Application

### Option A: Local Development Server

**1. Start Backend FastAPI Server:**
```bash
# In backend directory with virtual environment activated:
uvicorn app.main:app --reload --port 8000
```
Backend API will be available at `http://localhost:8000` (API Docs: `http://localhost:8000/docs`).

**2. Start Frontend Vite App:**
```bash
# In frontend directory:
npm run dev
```
Frontend app will be available at `http://localhost:5173`.

### Option B: Docker Compose (Full Stack)
```bash
docker-compose up --build
```
- Frontend UI: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- PostgreSQL: `localhost:5435`

---

## 🧪 Running Verification & Test Suites

### 1. Backend Test Suite (Pytest)
```bash
# Run all 433 backend unit and integration tests:
.\backend\.venv\Scripts\python.exe -m pytest backend -q
```

### 2. Frontend Linting & Type Checking
```bash
cd frontend
npm run lint
```

### 3. Frontend Production Build
```bash
cd frontend
npm run build
```

---

## 📑 API Reference Summary

| Endpoint | Method | Role Required | Description |
| :--- | :--- | :--- | :--- |
| `/health` | `GET` | Public | Public service health check |
| `/api/auth/login` | `POST` | Public | Authenticates user credentials & returns JWT token |
| `/api/auth/me` | `GET` | Authenticated | Retrieves profile of currently logged-in user |
| `/api/ask` | `POST` | `ANALYST`, `ADMIN` | Primary decision intelligence query endpoint |
| `/api/investigations` | `GET` | Authenticated | Retrieves paginated investigation history list |
| `/api/investigations/{id}` | `GET` | Authenticated | Retrieves full details & provenance of an investigation |
| `/api/investigations/{id}/reassess` | `POST` | `ANALYST`, `REVIEWER`, `ADMIN` | Recomputes multi-scenario metric robustness |
| `/api/investigations/{id}/review` | `POST` | `REVIEWER`, `ADMIN` | Submits human review (`APPROVED`, `REJECTED`, `FLAGGED`) |
| `/api/investigations/{id}/export` | `GET` | `REVIEWER`, `AUDITOR`, `ADMIN` | Exports audit report as JSON or Markdown |
| `/api/tools/decompose` | `POST` | Authenticated | Executes Driver Decomposition tool directly |
| `/api/tools/campaign-impact` | `POST` | Authenticated | Executes Campaign Impact / DiD tool directly |
| `/api/verify` | `POST` | Authenticated | Executes Numerical Claim Verification tool directly |
| `/api/v1/audit/logs` | `GET` | `AUDITOR`, `ADMIN` | Retrieves enterprise security audit log records |

---

## 🎬 Final Product Demo Workflow

To run a complete end-to-end judge demonstration:

1. **Launch App**: Open `http://localhost:5173` (or `http://localhost:3000` in Docker).
2. **Submit Business Question**: Enter `"What region should we prioritize for Q4?"` or `"Decompose revenue change between Q1 and Q2 across regions"`.
3. **Inspect Tool Execution Trace**: Click open the **Investigation Trace** card to see safe SQL queries and specialized tool executions with execution times.
4. **Inspect Claims & Verified Evidence**: Click on any claim badge (e.g., `✓ Supported`) to highlight its backing evidence in the right-hand **Evidence Provenance Panel**.
5. **Inspect Evidence Taxonomy**: Switch to the **Evidence Explorer** tab to inspect `FACT`, `DERIVED_FACT`, and `INFERENCE` items with full SQL syntax highlighting and formula inputs.
6. **Inspect Robustness & Decision Analysis**: Open the **Decision Intelligence** view to inspect candidate scores, criteria weights, and alternate sensitivity scenarios (`STABLE` / `SENSITIVE` / `INSUFFICIENT_EVIDENCE`).
7. **Executive Human Review**: Submit a review decision (`APPROVED`, `REJECTED`, `FLAGGED`) as a Reviewer user. Note that owner self-review attempts are automatically blocked with HTTP 403.
8. **Reassess Investigation**: Trigger a dynamic scenario shift (e.g. $+15\%$) to verify deterministic re-evaluation.
9. **Audit Trail Inspection**: Open the **Audit Trail** view to inspect immutable security event logs (`REVIEW_APPROVE`, `LOGIN_SUCCESS`, `EXPORT_REPORT`).

---

## 📋 Known Limitations

1. **Single Database Connection**: SQL tool queries execute against the primary PostgreSQL or SQLite business database. External REST endpoints or third-party web services are not connected.
2. **Observational Evidence Warning**: Difference-in-Differences (DiD) campaign analysis returns observational statistical association warnings ("Causation not proven") in compliance with evidence guardrails.
