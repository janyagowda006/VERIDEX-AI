/**
 * VERIDEX Centralized API Client
 *
 * Unified export facade uniting:
 * - config.js: Base URL resolution (local Vite proxy vs Render production)
 * - session.js: JWT token storage, user caching, and security lifecycle
 * - core.js: Standardized HTTP dispatcher, multipart boundaries, error parsing
 * - auth.js: Login, Current User profile, Logout
 * - investigations.js: Natural language AI reasoning, multi-turn threads, history, exports
 * - review.js: Human-in-the-Loop audit approvals/rejections
 * - tools.js: Safe SQL, schema introspection, health checks
 * - datasets.js: File uploads and table metadata
 */

// Configuration & URL Building
export { getApiBaseUrl, buildApiUrl } from './config.js';

// Session & Token Management
export {
  setAuthToken,
  getAuthToken,
  setAuthUser,
  getAuthUser,
  clearAuthToken,
  isAuthenticated,
  handleUnauthorized,
  subscribeAuthChange
} from './session.js';

// Core HTTP Request Dispatcher & Headers
export {
  apiRequest,
  getAuthHeaders,
  VeridexApiError,
  VeridexNetworkError
} from './core.js';

// Authentication Endpoints
export {
  login,
  getMe,
  logout
} from './auth.js';

// Investigation & Decision Intelligence Endpoints
export {
  askQuestion,
  reassessInvestigation,
  getInvestigationDetail,
  listInvestigations,
  exportInvestigationReport,
  downloadInvestigationReport,
  getAnalyticsSummary
} from './investigations.js';

// Human-in-the-Loop Review Endpoints
export {
  submitReview
} from './review.js';

// System Tools & Schema Inspection Endpoints
export {
  getHealth,
  getDbStatus,
  getSqlSchema,
  runSqlQuery
} from './tools.js';

// Data Sources & Upload Endpoints
export {
  uploadDataset,
  listConnectedSources
} from './datasets.js';
