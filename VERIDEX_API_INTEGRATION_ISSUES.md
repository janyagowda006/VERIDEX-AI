# VERIDEX — API CONTRACT INTEGRATION ISSUES REPORT
**Author**: Amoolya (Frontend Integration Engineer)  
**Backend Owner**: Gagandeep  
**Date**: November 2026  
**Status**: Formal Coordination Report  

---

## 1. Executive Summary

As part of the frontend integration and delivery workstream, this document tracks all API contract alignments, observed discrepancies, security headers, and missing backend endpoints identified during the implementation of the centralized API client, authentication layer, and dashboard views.

---

## 2. Identified Backend Issues for Gagandeep

### ISSUE-01: Missing FastAPI CORS Middleware in `backend/app/main.py`

- **Severity**: Critical (Deployment Blocker for Render)
- **Component**: Backend Entrypoint (`backend/app/main.py`)
- **Required Endpoint / Behavior**:
  Cross-Origin Resource Sharing (CORS) headers must be sent on all responses, including preflight `OPTIONS` requests, allowing the Render Static Site frontend domain to communicate with the FastAPI backend.
- **Current Observed Behavior**:
  `backend/app/main.py` initializes the FastAPI application and includes `api_router` without registering `CORSMiddleware`.
  ```python
  app = FastAPI(
      title=settings.PROJECT_NAME,
      description="Evidence-First AI Decision Intelligence Platform",
      version="0.1.0"
  )
  app.include_router(api_router)
  ```
- **Expected Behavior**:
  Register `CORSMiddleware` using origins configured in environment variables or default allowable development/production origins:
  ```python
  from fastapi.middleware.cors import CORSMiddleware

  origins = [
      "http://localhost:5173",
      "http://127.0.0.1:5173",
      "http://localhost:3000",
      "https://*.onrender.com",
  ]

  app.add_middleware(
      CORSMiddleware,
      allow_origins=["*"],  # or specific origin list
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```
- **Error Behavior**:
  In local dev via Vite proxy (`/api`), requests succeed because Vite rewrites the origin. In production on Render (where frontend is a static site and backend is a web service), browser fetch requests are blocked by the browser with:
  `Access to fetch at 'https://veridex-backend.onrender.com/api/auth/login' from origin 'https://veridex-frontend.onrender.com' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.`
- **Relevant Frontend Files**:
  - `frontend/src/api/client.js`
  - `frontend/src/api/core.js`
- **Reproduction Steps**:
  1. Set `VITE_API_BASE_URL=https://veridex-backend.onrender.com` in `.env.production`.
  2. Attempt `POST /api/auth/login` from the deployed frontend.
  3. Inspect DevTools Network tab — request fails at preflight with CORS error.

---

### ISSUE-02: Missing Dataset Upload & Ingestion Endpoint (`POST /api/data/upload`)

- **Severity**: Moderate (Data Sources Workstream)
- **Component**: Routes (`backend/app/api/routes.py`)
- **Required Endpoint / Behavior**:
  `POST /api/data/upload` accepting multipart file upload (`.csv` or `.xlsx`) to allow users to ingest new business datasets dynamically into PostgreSQL.
- **Current Observed Behavior**:
  The backend provides database loading scripts (`scripts/load_data.py`), schema introspection (`GET /api/tools/sql-schema`), and safe query execution (`POST /api/tools/sql-query`), but has no HTTP route for runtime file ingestion.
- **Expected Behavior**:
  Implement route:
  ```python
  @router.post("/api/data/upload")
  async def upload_dataset_file(
      file: UploadFile = File(...),
      dataset_name: Optional[str] = Form(None),
      current_user: User = Depends(require_roles("ANALYST", "ADMIN")),
      db: Session = Depends(get_db)
  ):
      # Validate extension (.csv, .xlsx)
      # Ingest via data_ingestion service
      # Return 200 with table summary and row count
  ```
- **Relevant Frontend Files**:
  - `frontend/src/api/datasets.js`
  - `frontend/src/components/views/SourcesView.jsx`
- **Frontend Fallback / Mitigation**:
  The frontend UI displays the existing introspected tables (`customers`, `products`, `orders`, `order_items`) from `GET /api/tools/sql-schema` and informs the user if `/api/data/upload` is not yet available on the backend.

---

### ISSUE-03: Clarification of Seeded Test Account Credentials in Documentation

- **Severity**: Low (Developer Experience / Testing Alignment)
- **Component**: Documentation (`README.md`, `backend/app/api/deps.py`)
- **Required Behavior**:
  All project collaborators and external evaluators should have clear visibility of the seeded accounts and passwords.
- **Current Status**:
  Verified in `backend/app/api/deps.py` lines 13–42:
  - `analyst@veridex.ai` / `password123` (`ANALYST`)
  - `reviewer@veridex.ai` / `password123` (`REVIEWER`)
  - `auditor@veridex.ai` / `password123` (`AUDITOR`)
  - `admin@veridex.ai` / `password123` (`ADMIN`)
- **Frontend Action**:
  Implemented quick-fill role selector buttons on the `LoginModal` interface so users can test all four personas seamlessly.

---

## 3. Verified and Confirmed API Contracts

The following endpoints have been verified against backend route handlers in `backend/app/api/routes.py` and are integrated into the frontend API client:

| HTTP Method | Route | Auth / Role Required | Request Schema | Response Schema | Frontend Module |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/health` | None (Public) | None | `{"status": "ok"}` | `src/api/tools.js` |
| `POST` | `/api/auth/login` | None (Public) | `LoginRequest` (`email`, `password`) | `Token` (`access_token`, `token_type`, `user`) | `src/api/auth.js` |
| `GET` | `/api/auth/me` | Bearer Token | None | `UserRead` (`user_id`, `email`, `full_name`, `role`, `is_active`) | `src/api/auth.js` |
| `GET` | `/db-status` | `ADMIN` | None | `{"database_connected": bool, "table_counts": {...}, "summary_metrics": {...}}` | `src/api/tools.js` |
| `GET` | `/api/tools/sql-schema` | Authenticated User | None | `SchemaContext` (`tables`, `relationships`, `table_row_counts`) | `src/api/tools.js` |
| `POST` | `/api/tools/sql-query` | `ADMIN` | `SQLQueryRequest` (`query`) | `SQLQueryResult` (`columns`, `rows`, `metadata`) | `src/api/tools.js` |
| `POST` | `/api/ask` | `ANALYST`, `ADMIN` | `AskRequest` (`question`, `max_turns`, `investigation_id`) | `AskResponse` (`answer`, `claims`, `evidence`, `analysis`, `tool_calls`) | `src/api/investigations.js` |
| `GET` | `/api/investigations` | Authenticated User | Query params: `limit`, `offset`, `search`, `status`, `robustness_status`, `owner_id` | `List[InvestigationSummary]` | `src/api/investigations.js` |
| `GET` | `/api/investigations/metrics/summary` | Authenticated User | None | `InvestigationMetricsSummary` | `src/api/investigations.js` |
| `GET` | `/api/investigations/{id}` | Authenticated User (Owner check for ANALYST) | Path param: `investigation_id` | `InvestigationDetail` (`result_json`, `latest_review`, `review_count`, `turns`) | `src/api/investigations.js` |
| `POST` | `/api/investigations/{id}/reassess` | `ANALYST`, `REVIEWER`, `ADMIN` | `InvestigationReassessRequest` (`scenario_shift_pct`) | `InvestigationReassessResponse` (`robustness`, `explanation`) | `src/api/investigations.js` |
| `POST` | `/api/investigations/{id}/review` | `REVIEWER`, `ADMIN` (Self-review blocked) | `InvestigationReviewCreate` (`review_status`, `reviewer_id`, `review_notes`) | `InvestigationReviewResponse` | `src/api/review.js` |
| `GET` | `/api/investigations/{id}/export` | `REVIEWER`, `AUDITOR`, `ADMIN` | Query param: `format=json\|markdown` | JSON file attachment or Markdown text | `src/api/investigations.js` |

