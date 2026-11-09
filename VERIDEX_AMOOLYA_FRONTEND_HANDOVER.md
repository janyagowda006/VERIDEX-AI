# VERIDEX — FRONTEND HANDOVER AND ARCHITECTURAL BASELINE REPORT
**Author**: Amoolya (Frontend Integration Engineer)  
**Date**: November 2026  
**Repository**: [janyagowda006/VERIDEX-AI](https://github.com/janyagowda006/VERIDEX-AI)  
**Branch**: `team/frontend`  
**Status**: Comprehensive Baseline Completed — Entering Implementation

---

## 1. Executive Summary

VERIDEX is an Evidence-First AI Decision Intelligence platform designed around the foundational principle: *"AI for reasoning, code for correctness."* The frontend is built on **React 19**, **Vite 8**, and vanilla modern CSS with custom design tokens, providing a high-density, accessible, and responsive user experience for enterprise analysts, reviewers, auditors, and administrators.

This handover document records the baseline inspection of the existing codebase prior to Phase 1–14 execution. It inventories all frontend components, API interactions, mock implementations, backend dependencies, and initial test/build baselines.

---

## 2. Frontend Architecture & Technology Stack

- **Framework**: React 19 (`react: ^19.2.8`, `react-dom: ^19.2.8`)
- **Build Tool**: Vite 8 (`vite: ^8.3.0`, `@vitejs/plugin-react: ^6.1.1`)
- **Linter**: Oxlint (`oxlint: ^1.81.0`)
- **Styling**: Vanilla modern CSS (`src/index.css`, `src/App.css`) with CSS custom properties (`--bg-primary`, `--accent-teal`, `--border-subtle`, etc.) and system/user dark-light theme toggle.
- **State Management**: React state hooks (`useState`, `useEffect`, `useCallback`, `useMemo`) combined with centralized API client modules.
- **Routing**: Internal state-driven view router in `App.jsx` (`overview`, `investigations`, `sources`, `evidence`, `decisions`, `robustness`, `detail`, `history`, `settings`).

---

## 3. Page & Component Inventory

| Component / File | Location | Role / Responsibility | Baseline Status |
| :--- | :--- | :--- | :--- |
| `App.jsx` | `src/App.jsx` | Main application shell, top header, view switching, theme management | ⚠️ Prototype state: hardcoded default analyst, `useMock=true` default, placeholder history view. |
| `Sidebar.jsx` | `src/components/Sidebar.jsx` | Left persistent navigation bar with brand mark, view tabs, and user profile badge | ⚠️ Prototype state: hardcoded `'Gagandeep'` fallback. |
| `OverviewView.jsx` | `src/components/views/OverviewView.jsx` | Landing dashboard showing key metrics, suggested questions, pending reviews | ⚠️ Prototype state: hardcoded fallback metrics (214, 97, 9, 12). |
| `InvestigationWorkspaceView.jsx` | `src/components/views/InvestigationWorkspaceView.jsx` | Multi-turn investigation workspace with question input, rail, summary, evidence, review | ⚠️ Prototype state: fallback placeholder tool calls when empty. |
| `DecisionView.jsx` | `src/components/views/DecisionView.jsx` | Decision intelligence view with candidate comparison chart, threshold checks, review | ✅ Structurally complete; needs real API data connection. |
| `RobustnessView.jsx` | `src/components/views/RobustnessView.jsx` | Scenario sensitivity view with scenario chart and rank shifts | ⚠️ Prototype state: hardcoded outlier sensitivity and perturbation text. |
| `EvidenceExplorerView.jsx` | `src/components/views/EvidenceExplorerView.jsx` | Fact/derived fact/inference catalog, search, filter, SQL provenance inspector | ✅ Well structured; ready for live data. |
| `InvestigationDetailView.jsx` | `src/components/views/InvestigationDetailView.jsx` | Full audit detail view with execution timeline and sticky TOC | ⚠️ Prototype state: hardcoded `"Today, 14:12"` timestamp. |
| `HistoryView.jsx` | `src/components/views/HistoryView.jsx` | Standalone history audit log with search, filters, pagination | ❌ Missing standalone view (currently rendered as a placeholder card in `App.jsx`). |
| `QuestionInput.jsx` | `src/components/QuestionInput.jsx` | Query input form with keyboard shortcut (`Ctrl+Enter`), preset pills, mock toggle | ✅ Functional; needs default live mode. |
| `HumanReviewPanel.jsx` | `src/components/HumanReviewPanel.jsx` | Human-in-the-Loop review form (APPROVED, REJECTED, FLAGGED), self-review guard | ✅ Functional; needs role-based permissions and live backend confirmation. |
| `InvestigationHistoryDrawer.jsx` | `src/components/InvestigationHistoryDrawer.jsx` | Slide-over drawer to browse, search, and load persisted investigations | ✅ Functional; calls `listInvestigations`. |
| `GlobalAnalyticsPanel.jsx` | `src/components/GlobalAnalyticsPanel.jsx` | Slide-over drawer displaying platform-wide investigation counts & robustness stats | ✅ Functional; calls `getAnalyticsSummary`. |
| `CandidateComparisonChart.jsx` | `src/components/visualization/CandidateComparisonChart.jsx` | SVG candidate ranking and score comparison visualization | ✅ Functional. |
| `CriteriaThresholdView.jsx` | `src/components/visualization/CriteriaThresholdView.jsx` | SVG/HTML threshold passing/failing indicator | ✅ Functional. |
| `EvidenceDecisionTrace.jsx` | `src/components/visualization/EvidenceDecisionTrace.jsx` | Flowchart showing evidence-to-decision lineage trace | ✅ Functional. |
| `RobustnessScenarioChart.jsx` | `src/components/visualization/RobustnessScenarioChart.jsx` | SVG multi-scenario sensitivity comparison chart | ✅ Functional. |

---

## 4. Existing API Client & Endpoint Inventory

The current `src/api/client.js` contains:
- `login(email, password, useMock)` -> `POST /api/auth/login`
- `getMe(useMock, devRole)` -> `GET /api/auth/me`
- `askQuestion(question, maxTurns, useMock, investigationId)` -> `POST /api/ask`
- `reassessInvestigation(investigationId, scenarioShiftPct, useMock)` -> `POST /api/investigations/{id}/reassess`
- `submitReview(investigationId, reviewStatus, reviewerId, reviewNotes, useMock)` -> `POST /api/investigations/{id}/review`
- `getInvestigationDetail(investigationId, useMock)` -> `GET /api/investigations/{id}`
- `listInvestigations(limit, offset, useMock, search, status, robustnessStatus, ownerId)` -> `GET /api/investigations`
- `exportInvestigationReport(investigationId, format, useMock)` -> `GET /api/investigations/{id}/export`
- `getAnalyticsSummary(useMock)` -> `GET /api/investigations/metrics/summary`

### Identified Gaps in API Client:
1. **Missing Base URL Configuration**: Directly calls relative endpoints (e.g. `fetch('/api/ask')`). Does not support `import.meta.env.VITE_API_BASE_URL` for production Render Static Site deployment.
2. **Missing Endpoints**:
   - `GET /health` (backend health check)
   - `GET /db-status` (database connectivity and record count check)
   - `GET /api/tools/sql-schema` (database schema inspection for Data Sources view)
   - `POST /api/tools/sql-query` (safe SQL query execution)
   - Multipart file upload / dataset ingestion endpoint
3. **No AbortSignal Support**: Network requests cannot be cancelled when views unmount or questions are re-submitted.
4. **No Centralized Error Normalizer**: Error parsing is duplicated across individual fetch calls.
5. **No Network Error Interception**: Failures when backend is offline throw unhandled generic exceptions.

---

## 5. Existing Mock Data (`src/mocks/mockData.js`)

The mock module defines:
- `MOCK_USERS`: 4 default users (`analyst`, `reviewer`, `auditor`, `admin`).
- `MOCK_ASK_RESPONSE`: Sample multi-region gross revenue question response with FACT, DERIVED_FACT, INFERENCE, rankings, recommendation, and robustness check.
- `MOCK_REASSESS_RESPONSE`: Sample reassessment response.
- `MOCK_HISTORICAL_INVESTIGATIONS`: 5 sample historical investigations with varying statuses (`COMPLETED`, `REQUIRES_REVIEW`).
- `MOCK_ANALYTICS_SUMMARY`: Aggregate statistics.

**Rule**: Mock data must be decoupled from production flows. The frontend must target the real backend by default, using mock data only as an optional explicit fallback during offline local development.

---

## 6. Backend Integration Dependencies & Contracts

The backend is built with **FastAPI** (`backend/app/main.py`):
1. **Authentication**: `POST /api/auth/login`, `GET /api/auth/me`. Default users in `backend/app/api/deps.py`:
   - `analyst@veridex.ai` / `password123` (`ANALYST`)
   - `reviewer@veridex.ai` / `password123` (`REVIEWER`)
   - `auditor@veridex.ai` / `password123` (`AUDITOR`)
   - `admin@veridex.ai` / `password123` (`ADMIN`)
2. **Decision Engine & Ask API**: `POST /api/ask` (single-turn & multi-turn thread continuation via `investigation_id`).
3. **Investigations & Audit**:
   - `GET /api/investigations` (paginated, with search & filters)
   - `GET /api/investigations/{id}`
   - `POST /api/investigations/{id}/reassess`
   - `POST /api/investigations/{id}/review` (self-review forbidden by backend)
   - `GET /api/investigations/{id}/export?format=json|markdown`
4. **Tools & Schema**: `GET /api/tools/sql-schema`, `POST /api/tools/sql-query`.
5. **Observed Backend Issue**: `backend/app/main.py` currently lacks `CORSMiddleware`. For local dev, Vite proxy (`/api`) bypasses CORS. For Render deployment, Gagandeep must add `CORSMiddleware`. This is documented in `VERIDEX_API_INTEGRATION_ISSUES.md`.

---

## 7. Baseline Build and Lint Results

Command: `npm run build`
Result: **SUCCESS**
- Vite 8.3.1 transformed 43 modules in 361ms.
- Built production bundles in `dist/`.

Command: `npm run lint`
Result: **0 errors, 4 warnings**
- `src/components/InvestigationHistoryDrawer.jsx:50:12` (setState synchronously inside effect)
- `src/components/GlobalAnalyticsPanel.jsx:17:5` (setState synchronously inside effect)
- `src/components/HumanReviewPanel.jsx:27:7` (setState synchronously inside effect)
- `src/App.jsx:134:5` (setState synchronously inside effect on mount)

Test Suite:
- Currently no automated unit test runner configured in `package.json`.
- A Vitest test suite will be introduced in Phase 12 to test API client, auth, views, and rendering.

---

## 8. Recommended Implementation Order

1. **Phase 1**: Centralized API Client (`client.js`, base URL, error normalizer, abort signals, modular clients).
2. **Phase 2**: Authentication & Session Management (Login modal/view, JWT token storage, `useAuth` / `AuthContext`, user session state, logout, 401 handling).
3. **Phase 3**: Dashboard & Application Entry Flow (real user identity, remove fake fallback metrics, live data loading).
4. **Phase 4**: History View (implement standalone `HistoryView.jsx`, pagination, filters, search, navigation to detail).
5. **Phase 5**: Decisions & Human Review (real review submission, role-based controls, confirmation dialog, real persistence).
6. **Phase 6**: Robustness View (remove hardcoded scenarios, live scenario perturbation & re-assessment).
7. **Phase 7**: Investigation Detail & Execution Timeline (real timestamps, execution status, tool outputs, export download).
8. **Phase 8**: Investigation Creation & Full Multi-Turn Workflow.
9. **Phase 9**: Data Sources & Schema Inspection (`/api/tools/sql-schema`, safe read-only display, CSV/Excel upload handling).
10. **Phase 10**: Reports, Exports & Remaining UI polish.
11. **Phase 11**: API Contract Coordination (`VERIDEX_API_INTEGRATION_ISSUES.md`).
12. **Phase 12**: Automated Testing (Vitest test suite covering API client, auth, views).
13. **Phase 13**: Render Deployment Readiness (`VITE_API_BASE_URL` configuration, documentation).
14. **Phase 14**: Final Documentation & Handover reports.

