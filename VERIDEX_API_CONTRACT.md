# VERIDEX AI — Centralized API Contract & Reconciliation Specification

**Version:** 1.0.0 (Release Candidate)  
**Date:** November 2026  
**Status:** Reconciled & Verified  
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
6. **Separation of Duties:** Self-review of investigation threads is rejected by the backend (403 Forbidden).

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
    "email": "analyst@veridex.internal",
    "password": "correct-password"
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 86400,
    "user": {
      "user_id": "usr_analyst_01",
      "email": "analyst@veridex.internal",
      "full_name": "Lead Analyst",
      "role": "ANALYST",
      "is_active": true
    }
  }
  ```
- **Errors:**
  - `401 Unauthorized`: `{"detail": "Incorrect email or password"}`
  - `422 Unprocessable Entity`: Validation error on payload schema.

### 3.2 Current User Profile
- **Endpoint:** `GET /api/auth/me`
- **Auth:** Required (`Bearer`)
- **Response (`200 OK`):**
  ```json
  {
    "user_id": "usr_analyst_01",
    "email": "analyst@veridex.internal",
    "full_name": "Lead Analyst",
    "role": "ANALYST",
    "is_active": true
  }
  ```
- **Errors:** `401 Unauthorized` if token is missing, malformed, or expired.

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
    "tables_loaded": 3
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
- **Response (`200 OK`):**
  ```json
  {
    "tables": {
      "orders": {
        "columns": ["order_id", "region", "product_line", "revenue", "profit", "quarter"],
        "primary_key": ["order_id"]
      }
    },
    "relationships": [],
    "table_row_counts": {
      "orders": 18420
    }
  }
  ```

### 5.2 Read-Only SQL Execution
- **Endpoint:** `POST /api/tools/sql-query`
- **Auth:** Required (Admin / Analyst)
- **Request Body:**
  ```json
  {
    "query": "SELECT region, SUM(revenue) AS total_revenue FROM orders GROUP BY region;"
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "columns": ["region", "total_revenue"],
    "rows": [
      ["North", 4820311.0],
      ["East", 4110942.0]
    ],
    "row_count": 2,
    "execution_time_ms": 14.5
  }
  ```
- **Security Enforcements:**
  - `400 Bad Request` if query contains non-SELECT AST clauses (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`).

---

## 6. Dynamic Dataset Ingestion

- **Endpoints:** `POST /api/data-sources/upload`, `POST /api/data/upload`, `POST /data/upload`
- **Auth:** Required
- **Request Type:** `multipart/form-data`
  - `file`: File binary (`.csv`, `.xlsx`, `.xls`)
  - `dataset_name`: String (optional)
  - `description`: String (optional)
- **Response (`201 Created`):**
  ```json
  {
    "dataset_id": "ds_9a1f2e3c",
    "filename": "orders_2026.csv",
    "table_name": "uploaded_orders_2026_9a1f2e3c",
    "row_count": 18420,
    "columns": ["order_id", "region", "revenue"],
    "status": "INGESTED"
  }
  ```
- **Validation:**
  - `400 Bad Request`: Disallowed file extension, corrupt CSV, or file size > 50 MB.

---

## 7. Decision Intelligence & Investigation Endpoints

### 7.1 Natural Language Investigation Submission
- **Endpoint:** `POST /api/ask`
- **Auth:** Required
- **Request Body:**
  ```json
  {
    "question": "What region should we prioritize for Q4?",
    "max_turns": 3,
    "investigation_id": null
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "investigation_id": "inv_0142",
    "question": "What region should we prioritize for Q4?",
    "answer": "Prioritize North region based on highest revenue ($4.82M) and margin (31.4%).",
    "claims": [
      {
        "claim_id": "cl_01",
        "claim_text": "North generated $4.82M in revenue.",
        "evidence_ids": ["ev_fact_01"]
      }
    ],
    "evidence": [
      {
        "evidence_id": "ev_fact_01",
        "evidence_type": "FACT",
        "description": "Revenue aggregation by region from orders table.",
        "source": {
          "source_type": "sql_query",
          "sql": "SELECT region, SUM(revenue) FROM orders GROUP BY region;",
          "query_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
          "relevant_rows": [{"region": "North", "revenue": 4820311}]
        }
      }
    ],
    "analysis": {
      "recommendation": {
        "action_title": "Prioritize North region",
        "rationale": "Consistently ranks first across revenue and margin criteria.",
        "supporting_evidence_ids": ["ev_fact_01"]
      },
      "rankings": [
        {"candidate": "North", "score": 0.90, "rank": 1},
        {"candidate": "East", "score": 0.74, "rank": 2}
      ],
      "robustness": {
        "status": "STABLE",
        "explanation": "Recommendation remains first across all weight perturbations.",
        "lead_margin": 0.16,
        "threshold": 0.05
      }
    },
    "status": "COMPLETED",
    "created_at": "2026-11-09T14:12:00Z"
  }
  ```

### 7.2 List Investigations (Audit History)
- **Endpoint:** `GET /api/investigations`
- **Auth:** Required
- **Query Parameters:**
  - `limit` (integer, default 10)
  - `offset` (integer, default 0)
  - `status` (string, optional: `COMPLETED`, `REQUIRES_REVIEW`, `FAILED`)
  - `robustness` (string, optional: `STABLE`, `SENSITIVE`, `INSUFFICIENT_EVIDENCE`)
  - `q` (string, optional search query)
- **Response (`200 OK`):**
  ```json
  [
    {
      "investigation_id": "inv_0142",
      "question": "What region should we prioritize for Q4?",
      "status": "COMPLETED",
      "robustness_status": "STABLE",
      "evidence_count": 7,
      "created_at": "2026-11-09T14:12:00Z"
    }
  ]
  ```

### 7.3 Investigation Metrics Summary
- **Endpoint:** `GET /api/investigations/metrics/summary`
- **Auth:** Required
- **Response (`200 OK`):**
  ```json
  {
    "total_investigations": 12,
    "completed_count": 9,
    "requires_review_count": 2,
    "failed_count": 1,
    "stable_count": 8,
    "sensitive_count": 3,
    "insufficient_count": 1
  }
  ```

### 7.4 Investigation Detail by ID
- **Endpoint:** `GET /api/investigations/{investigation_id}`
- **Auth:** Required
- **Response (`200 OK`):** Full `InvestigationDetailResponse` with steps, evidence lineage, and review history.

### 7.5 Robustness Re-assessment
- **Endpoint:** `POST /api/investigations/{investigation_id}/reassess`
- **Auth:** Required
- **Request Body:**
  ```json
  {
    "scenario_shift_pct": 20.0
  }
  ```
- **Response (`200 OK`):** Updated robustness score, status, and perturbed ranking scenarios.

### 7.6 Human-in-the-Loop Review Submission
- **Endpoint:** `POST /api/investigations/{investigation_id}/review`
- **Auth:** Required
- **Request Body:**
  ```json
  {
    "status": "APPROVED",
    "reviewer_id": "usr_reviewer_02",
    "comments": "Audited evidence calculations and confirmed stability."
  }
  ```
- **Response (`200 OK`):** Updated investigation detail with recorded human audit record.
- **Enforcement:** `403 Forbidden` if `reviewer_id` matches the investigation `owner_id`.

### 7.7 Investigation Export
- **Endpoint:** `GET /api/investigations/{investigation_id}/export?format={json|markdown}`
- **Auth:** Required
- **Response (`200 OK`):** Formatted Markdown text or JSON audit bundle download.

---

## 8. Specialized Verified Tools

### 8.1 Metric Driver Decomposition
- **Endpoints:** `POST /tools/decompose`, `POST /api/tools/decompose`
- **Auth:** Required
- **Request Body:**
  ```json
  {
    "metric": "revenue",
    "dimensions": ["region", "category"],
    "period_a": {"start_date": "2025-01-01", "end_date": "2025-03-31"},
    "period_b": {"start_date": "2025-04-01", "end_date": "2025-06-30"}
  }
  ```
- **Response (`200 OK`):** `DecompositionResponse` with waterfall analysis and evidence items.

### 8.2 Campaign Lift / Difference-in-Differences
- **Endpoints:** `POST /tools/campaign-impact`, `POST /api/tools/campaign-impact`
- **Auth:** Required
- **Request Body:**
  ```json
  {
    "campaign_id": "CMP-2025-Q3-SOUTH"
  }
  ```
- **Response (`200 OK`):** `CampaignImpactResponse` with DiD estimate, standard errors, and inference disclaimers.

### 8.3 Numerical Claim Verification
- **Endpoints:** `POST /verify`, `POST /api/verify`
- **Auth:** Required
- **Request Body:**
  ```json
  {
    "answer_text": "North revenue reached $4.82M.",
    "evidence": [...],
    "strict_mode": false,
    "tolerance": 0.05
  }
  ```
- **Response (`200 OK`):** `VerificationResponse` status (`PASS` / `FAIL`), verified claims count, and unverified discrepancies.

---

## 9. Reconciliation Sign-off Matrix

| Frontend Module | Exported Function | Target Backend Route | Method | Status |
|-----------------|-------------------|----------------------|--------|--------|
| `auth.js` | `login` | `/api/auth/login` | POST | Reconciled & Verified |
| `auth.js` | `getMe` | `/api/auth/me` | GET | Reconciled & Verified |
| `investigations.js` | `askQuestion` | `/api/ask` | POST | Reconciled & Verified |
| `investigations.js` | `listInvestigations` | `/api/investigations` | GET | Reconciled & Verified |
| `investigations.js` | `getAnalyticsSummary` | `/api/investigations/metrics/summary` | GET | Reconciled & Verified |
| `investigations.js` | `getInvestigationDetail` | `/api/investigations/{id}` | GET | Reconciled & Verified |
| `investigations.js` | `reassessInvestigation` | `/api/investigations/{id}/reassess` | POST | Reconciled & Verified |
| `investigations.js` | `exportInvestigationReport` | `/api/investigations/{id}/export` | GET | Reconciled & Verified |
| `review.js` | `submitReview` | `/api/investigations/{id}/review` | POST | Reconciled & Verified |
| `tools.js` | `getHealth` | `/health` | GET | Reconciled & Verified |
| `tools.js` | `getDbStatus` | `/db-status` | GET | Reconciled & Verified |
| `tools.js` | `getSqlSchema` | `/api/tools/sql-schema` | GET | Reconciled & Verified |
| `tools.js` | `runSqlQuery` | `/api/tools/sql-query` | POST | Reconciled & Verified |
| `tools.js` | `runDriverDecomposition` | `/api/tools/decompose` | POST | Reconciled & Verified |
| `tools.js` | `evaluateCampaignImpact` | `/api/tools/campaign-impact` | POST | Reconciled & Verified |
| `tools.js` | `verifyAnswerClaims` | `/api/verify` | POST | Reconciled & Verified |
| `datasets.js` | `uploadDataset` | `/api/data-sources/upload` | POST | Reconciled & Verified |
