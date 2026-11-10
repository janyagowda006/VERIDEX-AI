# VERIDEX AI — Centralized API Contract & Reconciliation Specification

**Version:** 1.0.0 (Release Candidate — Post-Integration Verified)  
**Date:** November 2026  
**Status:** 100% Reconciled & Execution-Verified  
**Approver:** Gagandeep (Backend & Infrastructure Lead)  
**Authors:** Senior Integration Engineer, Janya (Backend Lead), Amoolya (Frontend Lead)  

---

## 1. Overview & Architectural Principles

VERIDEX is an Evidence-First Decision Intelligence platform. Every decision recommendation is traceable to verified data evidence, deterministic calculations, and sensitivity analysis.

The API contract establishes strict parity between:
- **Backend Implementation:** FastAPI application (`backend/app/api/routes.py`, `backend/app/main.py`)
- **Frontend Integration:** Centralized API client facade (`frontend/src/api/client.js`, `core.js`, `auth.js`, `investigations.js`, `review.js`, `tools.js`, `datasets.js`)

### Key Contract Guarantees
1. **Zero Mock Leaks:** Production traffic connects to real FastAPI endpoints. Mock data is isolated to opt-in development fallbacks (`useMock`).
2. **Centralized HTTP Dispatcher:** All frontend requests route through `apiRequest()` in `frontend/src/api/core.js`.
3. **Automatic Authorization:** Bearer JWT tokens stored via `session.js` are attached automatically to authenticated requests.
4. **Clean Multipart Boundaries:** File uploads use standard `FormData` without manually overriding multipart boundary headers.
5. **AST Read-Only SQL:** Direct SQL tool enforces AST parsing via `sqlglot` to reject mutation statements (`INSERT`, `UPDATE`, `DELETE`, `DROP`).
6. **Separation of Duties:** Self-review of investigation threads is rejected by the backend (`403 Forbidden`).
7. **Strict RBAC Enforcement:** Exporting executive audit reports requires `REVIEWER`, `AUDITOR`, or `ADMIN` roles (`403 Forbidden` for `ANALYST`).

---

## 2. Base URLs and Environments

| Environment | Frontend Base URL (`VITE_API_BASE_URL`) | Proxy / Target | CORS Allowed |
|-------------|----------------------------------------|----------------|--------------|
| **Local Dev** | `""` (Empty string, relative paths) | Vite proxy -> `http://127.0.0.1:8000` | `http://localhost:5173`, `http://localhost:3000` |
| **Production (Render)** | `https://veridex-api.onrender.com` (or injected `FRONTEND_ORIGIN`) | Render Web Service | `FRONTEND_ORIGIN` env var |

---

## 3. Authentication & RBAC Contract

All secured endpoints require the `Authorization: Bearer <JWT_TOKEN>` header.

### 3.1 Login
- **Endpoint:** `POST /api/auth/login`
- **Auth:** Public
- **Request Body (`application/json`):**
  ```json
  {
    "email": "analyst@veridex.ai",
    "password": "password123"
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "user": {
      "user_id": "usr_analyst_01",
      "email": "analyst@veridex.ai",
      "full_name": "Alice Analyst",
      "role": "ANALYST",
      "is_active": true,
      "created_at": "2026-11-09T14:12:00Z"
    }
  }
  ```
- **Errors:**
  - `401 Unauthorized`: `{"detail": "Incorrect email or password"}`
  - `401 Unauthorized`: `{"detail": "User account is inactive"}`
  - `422 Unprocessable Entity`: Validation error on payload schema.

### 3.2 Current User Profile
- **Endpoint:** `GET /api/auth/me`
- **Auth:** Required (`Bearer`)
- **Response (`200 OK`):**
  ```json
  {
    "user_id": "usr_analyst_01",
    "email": "analyst@veridex.ai",
    "full_name": "Alice Analyst",
    "role": "ANALYST",
    "is_active": true,
    "created_at": "2026-11-09T14:12:00Z"
  }
  ```
- **Errors:** `401 Unauthorized` (`{"detail": "Not authenticated"}`) if token is missing, malformed, or expired.

---

## 4. System Health & Infrastructure Endpoints

### 4.1 Basic Health Check
- **Endpoint:** `GET /health`
- **Auth:** Public
- **Response (`200 OK`):**
  ```json
  {
    "status": "ok",
    "mode": "standalone_deterministic",
    "service": "veridex"
  }
  ```

### 4.2 Readiness Probes
- **Endpoints:** `GET /ready`, `GET /health/ready`, `GET /api/health/ready`
- **Auth:** Public
- **Response (`200 OK`):**
  ```json
  {
    "status": "ready",
    "database": "connected",
    "service": "veridex",
    "tables_loaded": 4
  }
  ```

### 4.3 Database Connectivity Status
- **Endpoint:** `GET /db-status`
- **Auth:** Public / Admin
- **Response (`200 OK`):**
  ```json
  {
    "status": "healthy",
    "database": "connected",
    "driver": "psycopg2",
    "tables": {
      "orders": 18420,
      "investigations": 12
    }
  }
  ```

---

## 5. Relational Tools & Schema Endpoints

### 5.1 Schema Introspection
- **Endpoints:** `GET /api/tools/sql-schema`, `GET /api/tools/schema`
- **Auth:** Required (`Bearer`)
- **Backend Response Schema (`SchemaContext`):**
  ```json
  {
    "tables": [
      {
        "name": "orders",
        "columns": [
          {"name": "order_id", "type": "VARCHAR(32)", "nullable": false, "primary_key": true},
          {"name": "customer_id", "type": "VARCHAR(32)", "nullable": false, "primary_key": false},
          {"name": "order_date", "type": "DATE", "nullable": false, "primary_key": false},
          {"name": "sales_channel", "type": "VARCHAR(32)", "nullable": false, "primary_key": false},
          {"name": "order_status", "type": "VARCHAR(32)", "nullable": false, "primary_key": false},
          {"name": "discount", "type": "NUMERIC(4, 2)", "nullable": false, "primary_key": false}
        ],
        "foreign_keys": [
          {"constrained_columns": ["customer_id"], "referred_table": "customers", "referred_columns": ["customer_id"]}
        ]
      }
    ]
  }
  ```
- **Frontend Normalization:** `frontend/src/api/tools.js::getSqlSchema()` normalizes the backend array into a dictionary map `{ [table_name]: { name, columns, foreign_keys } }` while providing `raw_tables` to guarantee backwards and forwards compatibility across all React UI views.

### 5.2 Read-Only SQL Execution
- **Endpoint:** `POST /api/tools/sql-query`
- **Auth:** Required (`Bearer`)
- **Request Body:**
  ```json
  {
    "query": "SELECT region, COUNT(*) AS count FROM customers GROUP BY region;",
    "max_rows": 100
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "success": true,
    "sql": "SELECT region, COUNT(*) AS count FROM customers GROUP BY region LIMIT 100",
    "data": [
      {"region": "North", "count": 45},
      {"region": "East", "count": 38}
    ],
    "columns": ["region", "count"],
    "row_count": 2,
    "metadata": {
      "execution_time_ms": 14.5,
      "row_count": 2,
      "columns": ["region", "count"],
      "truncated": false,
      "query_hash": "a1b2c3d4e5f6...",
      "timestamp": "2026-11-09T14:12:00Z"
    }
  }
  ```
- **Security Enforcements:**
  - `400 Bad Request` if query contains non-SELECT AST clauses (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`).

---

## 6. Dynamic Dataset Ingestion & Uploads

### 6.1 Route Clarification & Reconciliation
- **Registered Backend Endpoints:**
  - `POST /api/data-sources/upload` (Primary REST route)
  - `POST /api/data/upload` (Standard alias)
  - `POST /data/upload` (Root alias)
- **Clarification on `/api/data/ingest`:**  
  The phrase `/api/data/ingest` was used conceptually in earlier engineering audit notes to refer to the data ingestion subsystem (`app.services.data_ingestion`). The actual registered FastAPI routes are `@router.post("/api/data-sources/upload")` and its aliases. No duplicate routes are needed.
- **Auth:** Required (`require_roles("ANALYST", "ADMIN")`)
- **Request Type:** `multipart/form-data`
  - `file`: Binary file stream (`.csv`, `.xlsx`, `.xls`)
- **Response (`201 Created`):**
  ```json
  {
    "dataset_id": "ds_e2994",
    "filename": "uploaded_orders.csv",
    "table_name": "uploaded_uploaded_orders_ds_e2994",
    "row_count": 2,
    "columns": ["order_id", "region", "product_line", "revenue", "profit", "quarter", "returned"],
    "status": "INGESTED",
    "message": "Dataset 'uploaded_orders.csv' successfully ingested into table 'uploaded_uploaded_orders_ds_e2994' with 2 rows and 7 columns."
  }
  ```
- **Validation:**
  - `400 Bad Request`: Disallowed file extension, corrupt format, or file size > 50 MB.

---

## 7. Decision Intelligence & Investigation Endpoints

### 7.1 Natural Language Investigation Submission
- **Endpoint:** `POST /api/ask`
- **Auth:** Required (`Bearer`)
- **Request Body:**
  ```json
  {
    "question": "What region should we prioritize for Q4?",
    "max_turns": 3,
    "investigation_id": null
  }
  ```
- **Response (`200 OK`):** `AskResponse` payload with `investigation_id`, `question`, `answer`, `claims`, `evidence`, `analysis` (recommendations, rankings, robustness), and `tool_calls`.

### 7.2 List Investigations (Audit History)
- **Endpoint:** `GET /api/investigations`
- **Auth:** Required (`Bearer`)
- **Query Parameters:**
  - `limit` (int, default 20, 1-100)
  - `offset` (int, default 0)
  - `search` (string, optional keyword query)
  - `status` (string, optional filter: `COMPLETED`, `REQUIRES_REVIEW`, `FAILED`)
  - `robustness_status` (string, optional filter: `STABLE`, `SENSITIVE`, `INSUFFICIENT_EVIDENCE`)
  - `owner_id` (string, optional filter; analysts automatically scoped to own investigations)
- **Response (`200 OK`):** List of `InvestigationSummary` objects.

### 7.3 Investigation Metrics Summary
- **Endpoint:** `GET /api/investigations/metrics/summary`
- **Auth:** Required (`Bearer`)
- **Response (`200 OK`):** `InvestigationMetricsSummary` object with platform-wide totals.

### 7.4 Investigation Detail by ID
- **Endpoint:** `GET /api/investigations/{investigation_id}`
- **Auth:** Required (`Bearer`)
- **Response (`200 OK`):** Full `InvestigationDetailResponse` with turns, execution timeline, evidence lineage, and review history.

### 7.5 Robustness Re-assessment
- **Endpoint:** `POST /api/investigations/{investigation_id}/reassess`
- **Auth:** Required (`Bearer`)
- **Request Body:**
  ```json
  {
    "scenario_shift_pct": 15.0
  }
  ```
- **Response (`200 OK`):** `InvestigationReassessResponse` with perturbed weights, candidate score shifts, and sensitivity evaluation.

### 7.6 Human-in-the-Loop Review Submission
- **Endpoint:** `POST /api/investigations/{investigation_id}/review`
- **Auth:** Required (`require_roles("REVIEWER", "ADMIN")`)
- **Request Body:**
  ```json
  {
    "review_status": "APPROVED",
    "reviewer_id": "usr_reviewer_01",
    "review_notes": "Audited evidence calculations and confirmed stability."
  }
  ```
- **Response (`200 OK`):** Updated `InvestigationDetailResponse` with `review_status: "APPROVED"`.
- **Enforcement Rules:**
  - `403 Forbidden`: If authenticated user has role `ANALYST`.
  - `403 Forbidden`: **Separation of Duties** — if `reviewer_id` equals the investigation's `owner_id` (`"Self-Review Blocked: You cannot review an investigation you initiated."`).

### 7.7 Investigation Audit Report Export
- **Endpoint:** `GET /api/investigations/{investigation_id}/export?format={json|markdown}`
- **Auth:** Required (`require_roles("REVIEWER", "AUDITOR", "ADMIN")`)
- **Enforcement:** `403 Forbidden` for role `ANALYST`.
- **Response (`format=markdown`):** Returns formatted markdown string beginning with `# VERIDEX Executive Audit Report`.
- **Response (`format=json`):**
  ```json
  {
    "veridex_report_version": "1.0",
    "exported_at": "2026-11-09T14:12:00Z",
    "investigation": {
      "investigation_id": "inv_cf6a7494d886",
      "question": "What region should we prioritize for Q4?",
      "status": "COMPLETED",
      "robustness_status": "STABLE",
      "created_at": "2026-11-09T14:12:00Z",
      "completed_at": "2026-11-09T14:12:03Z",
      "execution_time_ms": 3200,
      "turns_used": 2,
      "evidence_count": 7,
      "claims_count": 4,
      "error_message": null
    },
    "claims": [...],
    "evidence": [...],
    "analysis": {...},
    "turns": [...],
    "reviews": [...]
  }
  ```

---

## 8. Specialized Verified Tools

### 8.1 Metric Driver Decomposition
- **Endpoints:** `POST /tools/decompose`, `POST /api/tools/decompose`
- **Auth:** Required
- **Request Body:** `DecompositionRequest(metric="revenue", dimensions=["region", "category"], period_a=..., period_b=...)`
- **Response (`200 OK`):** `DecompositionResponse` with waterfall analysis and evidence items.

### 8.2 Campaign Lift / Difference-in-Differences
- **Endpoints:** `POST /tools/campaign-impact`, `POST /api/tools/campaign-impact`
- **Auth:** Required
- **Request Body:** `CampaignImpactRequest(campaign_id="CMP-2025-Q3-SOUTH")`
- **Response (`200 OK`):** `CampaignImpactResponse` with DiD estimate, standard errors, and inference disclaimers.

### 8.3 Numerical Claim Verification
- **Endpoints:** `POST /verify`, `POST /api/verify`
- **Auth:** Required
- **Request Body:** `VerificationRequest(answer_text="...", evidence=[...], strict_mode=false, tolerance=0.05)`
- **Response (`200 OK`):** `VerificationResponse` status (`PASS` / `FAIL`), verified claims count, and unverified discrepancies.

---

## 9. Reconciliation Sign-off Matrix

| Frontend Module | Exported Function | Target Backend Route | Method | RBAC Required | Status |
|-----------------|-------------------|----------------------|--------|---------------|--------|
| `auth.js` | `login` | `/api/auth/login` | POST | Public | Reconciled & Verified |
| `auth.js` | `getMe` | `/api/auth/me` | GET | Authenticated | Reconciled & Verified |
| `investigations.js` | `askQuestion` | `/api/ask` | POST | Authenticated | Reconciled & Verified |
| `investigations.js` | `listInvestigations` | `/api/investigations` | GET | Authenticated | Reconciled & Verified |
| `investigations.js` | `getAnalyticsSummary` | `/api/investigations/metrics/summary` | GET | Authenticated | Reconciled & Verified |
| `investigations.js` | `getInvestigationDetail` | `/api/investigations/{id}` | GET | Authenticated | Reconciled & Verified |
| `investigations.js` | `reassessInvestigation` | `/api/investigations/{id}/reassess` | POST | Authenticated | Reconciled & Verified |
| `investigations.js` | `exportInvestigationReport` | `/api/investigations/{id}/export` | GET | Reviewer/Auditor/Admin | Reconciled & Verified |
| `review.js` | `submitReview` | `/api/investigations/{id}/review` | POST | Reviewer/Admin (No self-review) | Reconciled & Verified |
| `tools.js` | `getHealth` | `/health` | GET | Public | Reconciled & Verified |
| `tools.js` | `getDbStatus` | `/db-status` | GET | Public/Admin | Reconciled & Verified |
| `tools.js` | `getSqlSchema` | `/api/tools/sql-schema` | GET | Authenticated | Reconciled & Verified |
| `tools.js` | `runSqlQuery` | `/api/tools/sql-query` | POST | Authenticated | Reconciled & Verified |
| `tools.js` | `runDriverDecomposition` | `/api/tools/decompose` | POST | Authenticated | Reconciled & Verified |
| `tools.js` | `evaluateCampaignImpact` | `/api/tools/campaign-impact` | POST | Authenticated | Reconciled & Verified |
| `tools.js` | `verifyAnswerClaims` | `/api/verify` | POST | Authenticated | Reconciled & Verified |
| `datasets.js` | `uploadDataset` | `/api/data-sources/upload` | POST | Analyst/Admin | Reconciled & Verified |
