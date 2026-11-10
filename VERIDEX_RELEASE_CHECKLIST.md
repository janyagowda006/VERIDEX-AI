# VERIDEX AI — Release Verification Checklist

**Branch:** `integration/veridex-release`  
**Target:** `main`  
**Current HEAD Commit:** `6698dcb`  
**Integration Engineer:** Senior Integration Engineer  
**Final Approver:** Gagandeep  

---

## 1. Git Safety & Branch Integrity Checklist

- [x] All work committed to dedicated integration branch `integration/veridex-release`.
- [x] `main` and `origin/main` untouched and unmerged (awaiting Gagandeep's final approval).
- [x] Developer branches `origin/team/data-intelligence` and `origin/team/frontend` unmodified.
- [x] No destructive commands used (`git reset --hard`, `git clean -fd` avoided).
- [x] Working tree is completely clean (`git status` shows clean).
- [x] Zero merge conflict markers (`<<<<<<<`) anywhere in repository.
- [x] Both original merge commits preserved in history (`b1a7199` and `2b0a85e`).
- [x] No secrets, private keys, `.env` files, or JWT secrets committed to version control.

---

## 2. Backend Architecture & Security Checklist

- [x] **Readiness Probes:** `/ready`, `/health/ready`, `/api/health/ready` present and active.
- [x] **CORS Configuration:** `backend/app/main.py` binds `CORSMiddleware` using `settings.cors_origins` (supports `localhost:5173`, `localhost:3000`, and dynamic `FRONTEND_ORIGIN`).
- [x] **Render Compatibility:** `backend/Dockerfile` dynamically binds to `$PORT` via shell expansion `exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`.
- [ ] **Database Persistence (Production PostgreSQL):** NOT VERIFIED LOCALLY (Local PostgreSQL port 5432 was unreachable; in-memory SQLite used for automated tests and 9-step integration test; PostgreSQL connectivity must be validated on Render staging).
- [x] **AST SQL Safety:** AST parsing enforced using `sqlglot` to reject mutation statements (`INSERT`, `UPDATE`, `DELETE`, `DROP`).
- [x] **Audit Logging:** Tamper-evident audit trail records login attempts, reviews, and tool queries.
- [x] **Separation of Duties:** Self-review prevention rejects investigator reviewing their own threads (`403 Forbidden`).
- [x] **Multi-turn IDOR Guard:** Thread ownership validated for multi-turn investigations.
- [x] **Route Parity:** All route aliases (`/api/tools/sql-schema` and `/api/tools/schema`, `/api/data-sources/upload` and `/api/data/upload`) active.

---

## 3. Frontend Architecture & Integration Checklist

- [x] **Centralized API Client:** All views route through `frontend/src/api/client.js` and `core.js`.
- [x] **Base URL Resolution:** `import.meta.env.VITE_API_BASE_URL` respected; relative paths used in dev.
- [x] **Vite Dev Proxy:** Proxies `/api`, `/health`, `/ready`, and `/db-status` to `http://127.0.0.1:8000`.
- [x] **Automatic Auth:** JWT Bearer token attached to protected requests via `getAuthHeaders()`.
- [x] **Multipart Boundaries:** `FormData` used for dataset uploads without manual `Content-Type` boundary overrides.
- [x] **Zero Mock Leaks:** Default runtime mode is live (`useMock = false`); mock data isolated to opt-in testing.
- [x] **Schema Normalization:** `getSqlSchema()` normalizes `SchemaContext.tables` array into dictionary map for UI views while preserving `raw_tables`.
- [x] **Dynamic Views:**
  - `OverviewView.jsx`: Connected to `getAnalyticsSummary` and `listInvestigations`.
  - `HistoryView.jsx`: Connected to backend pagination, query search, status & robustness filters.
  - `DecisionView.jsx`: Renders real backend criteria, weights, and normalized rankings.
  - `RobustnessView.jsx`: Supports real-time re-assessment via `POST /api/investigations/{id}/reassess`.
  - `InvestigationDetailView.jsx`: Full execution timeline, claims-to-evidence graph, and export downloads.
  - `EvidenceExplorerView.jsx`: Dynamic evidence drawer with SQL syntax and copy utilities.
  - `Sidebar.jsx`: Dynamic user initials, full name, role, and sign-out button.
  - `SourcesView.jsx`: Schema reflection and dataset file uploads.

---

## 4. Automated Verification Results

| Layer | Test / Task | Target | Actual Result | Status |
|-------|-------------|--------|---------------|--------|
| **Backend** | Pytest Test Suite (`pytest backend/tests`) | 447 tests | **447 passed, 0 failed, 0 skipped (35.63s)** | **PASS** |
| **Frontend** | Unit Tests (`npm test`) | 30 tests | **30 passed, 0 failed (279ms)** | **PASS** |
| **Frontend** | Production Build (`npm run build`) | Bundle dist | **Built in 421ms, 0 errors** | **PASS** |
| **Frontend** | Linter (`npm run lint`) | Static Analysis | **0 errors, 16 warnings** | **PASS** |
| **End-to-End** | 9-Phase Workflow Verification | All 9 flows | **9 of 9 flows verified in production mode** | **PASS** |

---

## 5. Render Deployment Configuration Reference

### Backend Web Service (Render)
- **Environment:** Docker
- **Dockerfile Path:** `backend/Dockerfile`
- **Health Check Path:** `/ready`
- **Environment Variables Required:**
  ```ini
  DATABASE_URL=postgresql+psycopg2://user:password@hostname:5432/dbname
  JWT_SECRET=<strong-random-secret>
  JWT_ALGORITHM=HS256
  ACCESS_TOKEN_EXPIRE_MINUTES=1440
  FRONTEND_ORIGIN=https://veridex-app.onrender.com
  ENVIRONMENT=production
  ```

### Frontend Static Site (Render)
- **Build Command:** `npm run build`
- **Publish Directory:** `dist`
- **Environment Variables Required:**
  ```ini
  VITE_API_BASE_URL=https://veridex-api.onrender.com
  ```

---

## 6. Approver Sign-Off Block

**Integration Branch:** `integration/veridex-release`  
**Current HEAD Commit:** `6698dcb` (or latest commit with documentation updates)  

```
Approved for Merge into Main: [ ] YES   [ ] NO
Approver: Gagandeep (Backend & Infrastructure Lead)
Signature: ____________________________________
Date: _________________________________________
```
