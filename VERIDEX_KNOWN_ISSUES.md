# VERIDEX AI — Known Issues & Operational Notes

**Version:** 1.0.0 (Release Candidate)  
**Branch:** `integration/veridex-release`  
**Date:** November 2026  
**Auditor:** Senior Integration Engineer  

---

## 1. Overview

This document catalogs known non-blocking warnings, runtime requirements, and operational considerations identified during the controlled integration and release verification.

---

## 2. Non-Blocking Frontend Lint Warnings

Running `npm run lint` (`oxlint`) yields **0 errors** and **17 non-blocking warnings**:

1. **Unused Parameter in Mock Test:**
   - File: `frontend/tests/investigations.test.js:162`
   - Warning: Parameter `options` is declared but never used in global fetch mock.
   - Impact: None. Benign mock signature.

2. **Unused Import in Config Test:**
   - File: `frontend/tests/api_client.test.js:4`
   - Warning: `getApiBaseUrl` is imported but not explicitly asserted.
   - Impact: None.

3. **React Compiler Optimization Notices (`set-state-in-effect`):**
   - Files: `HumanReviewPanel.jsx`, `InvestigationHistoryDrawer.jsx`, `GlobalAnalyticsPanel.jsx`, `OverviewView.jsx`, `WorkspaceView.jsx`
   - Warning: Synchronous `setState` inside `useEffect` causes React compiler to skip memoization optimization for these components.
   - Impact: Minor rendering optimization notice; component functionality, lifecycle, and reactivity are verified and behave correctly.

---

## 3. Host Environment & CI/CD Deployment Notes

1. **Local Windows Development Workstation:**
   - The local Windows workstation used for integration testing contains Node.js v24.13.0 and npm 11.8.0.
   - It does not have an installed Python 3.12 interpreter (`py -0` reports no installed Pythons) or Docker daemon.
   - **Resolution:** Full backend automated pytest runs (436 tests) are executed within the Docker container (`backend/Dockerfile`) or the CI/CD pipeline (GitHub Actions / Render build pipeline).

2. **Render Dynamic Port Binding:**
   - Render requires web services to bind to the dynamic `$PORT` environment variable provided at runtime.
   - **Verification:** `backend/Dockerfile` has been audited and verified to use:
     ```sh
     CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
     ```
     This prevents startup timeout crashes on Render.

3. **PostgreSQL Driver Configuration:**
   - In production on Render, `DATABASE_URL` must point to the provisioned PostgreSQL instance.
   - The configuration in `backend/app/core/config.py` enforces `postgresql+psycopg2://` with graceful fallback for local development SQLite if the database is unreachable during offline tests.

---

## 4. Client-Side Upload Guard

- **Behavior:** The frontend `uploadDataset` API client enforces a client-side 50 MB file limit (`File exceeds maximum upload size of 50 MB`).
- **File Extensions:** Supported file extensions are `.csv`, `.xlsx`, and `.xls`. Any unsupported format triggers an immediate client-side validation error before transmitting network requests.

---

## 5. Security & RBAC Enforcement

- **Self-Review Separation:** An investigator cannot approve or reject their own investigation thread. The backend enforces `403 Forbidden` (`Investigator cannot review own investigation`). The frontend surfaces this error cleanly to the user.
- **SQL Glot AST Validation:** Any attempts to run modifying SQL (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`) via `POST /api/tools/sql-query` are rejected by the AST analyzer with a descriptive error.

