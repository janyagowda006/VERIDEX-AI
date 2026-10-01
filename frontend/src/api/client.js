import {
  getMockAskResponse,
  getMockReassessResponse,
  getMockReviewResponse,
  getMockInvestigationDetail,
  getMockInvestigationsList,
  getMockAnalyticsSummary,
  getMockExportData,
  getMockLoginResponse,
  getMockMeResponse,
  getMockSqlSchema,
  getMockAuditLogs
} from '../mocks/mockData.js';


let activeAuthToken = null;
try {
  activeAuthToken = localStorage.getItem('veridex_auth_token') || null;
} catch {
  // fallback for restricted environments
}

export function setAuthToken(token) {
  activeAuthToken = token;
  try {
    if (token) {
      localStorage.setItem('veridex_auth_token', token);
    } else {
      localStorage.removeItem('veridex_auth_token');
    }
  } catch {
    // fallback
  }
}

export function getAuthToken() {
  if (!activeAuthToken) {
    try {
      activeAuthToken = localStorage.getItem('veridex_auth_token');
    } catch {
      // fallback
    }
  }
  return activeAuthToken;
}

export function getAuthHeaders(extraHeaders = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...extraHeaders
  };
  const token = getAuthToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

/**
 * Authenticate user with credentials.
 * Connects to POST /api/auth/login
 */
export async function login(email, password, useMock = false) {
  if (useMock) {
    return new Promise((resolve) => {
      setTimeout(() => {
        const res = getMockLoginResponse(email);
        setAuthToken(res.access_token);
        resolve(res);
      }, 300);
    });
  }

  const response = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });

  if (!response.ok) {
    const errorText = await response.text();
    let detail = errorText;
    try {
      const jsonErr = JSON.parse(errorText);
      if (jsonErr.detail) detail = typeof jsonErr.detail === 'string' ? jsonErr.detail : JSON.stringify(jsonErr.detail);
    } catch {
      // fallback
    }
    throw new Error(detail || "Authentication failed.");
  }

  const data = await response.json();
  if (data.access_token) {
    setAuthToken(data.access_token);
  }
  return data;
}

/**
 * Retrieve current authenticated user details.
 * Connects to GET /api/auth/me
 */
export async function getMe(useMock = false, devRole = "ANALYST") {
  if (useMock) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(getMockMeResponse(devRole));
      }, 200);
    });
  }

  const token = getAuthToken();
  if (!token) return null;

  const response = await fetch('/api/auth/me', {
    method: 'GET',
    headers: getAuthHeaders({ 'Accept': 'application/json' })
  });

  if (!response.ok) {
    return null;
  }

  return await response.json();
}



/**
 * VERIDEX API client for decision intelligence queries.
 * Connects to POST /api/ask endpoint or resolves mock data for development.
 *
 * @param {string} question - Business question text.
 * @param {number} maxTurns - Maximum investigation turns.
 * @param {boolean} useMock - Whether to return mock data.
 * @param {string|null} investigationId - Optional persistent investigation ID for multi-turn continuations.
 * @returns {Promise<Object>} AskResponse object matching frozen backend contract.
 */
export async function askQuestion(question, maxTurns = 3, useMock = false, investigationId = null) {
  if (useMock) {
    // Return deterministic mock response with multi-turn support
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(getMockAskResponse(question, investigationId));
      }, 500);
    });
  }

  const payload = {
    question: question,
    max_turns: maxTurns
  };

  if (investigationId) {
    payload.investigation_id = investigationId;
  }

  const response = await fetch('/api/ask', {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const errorText = await response.text();
    let detail = errorText;
    try {
      const jsonErr = JSON.parse(errorText);
      if (jsonErr.detail) detail = typeof jsonErr.detail === 'string' ? jsonErr.detail : JSON.stringify(jsonErr.detail);
    } catch {
      // fallback
    }
    throw new Error(detail || "Failed to execute investigation request.");
  }

  return await response.json();
}


/**
 * Executes dynamic metric robustness re-assessment on an existing persisted investigation.
 * Connects to POST /api/investigations/{id}/reassess
 *
 * @param {string} investigationId - Persistent investigation identifier.
 * @param {number} scenarioShiftPct - Percentage metric perturbation (e.g. 5, 10, 15, 20, 25, 30).
 * @param {boolean} useMock - Whether to return mock data.
 * @returns {Promise<Object>} InvestigationReassessResponse matching backend contract.
 */
export async function reassessInvestigation(investigationId, scenarioShiftPct = 10.0, useMock = false) {
  if (!investigationId) {
    throw new Error("Investigation ID is required for re-assessment.");
  }

  if (useMock) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(getMockReassessResponse(investigationId, scenarioShiftPct));
      }, 400);
    });
  }

  const response = await fetch(`/api/investigations/${encodeURIComponent(investigationId)}/reassess`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      scenario_shift_pct: Number(scenarioShiftPct)
    })
  });

  if (!response.ok) {
    const errorText = await response.text();
    let detail = errorText;
    try {
      const jsonErr = JSON.parse(errorText);
      if (jsonErr.detail) detail = jsonErr.detail;
    } catch {
      // fallback
    }
    if (response.status === 404) {
      throw new Error("Investigation not found.");
    } else if (response.status === 422) {
      throw new Error(`Validation Error: ${detail}`);
    } else if (response.status === 400) {
      throw new Error(`Invalid Request: ${detail}`);
    } else {
      throw new Error("Unable to reassess investigation. Please try again.");
    }
  }

  return await response.json();
}

/**
 * Submits a persistent Human-in-the-Loop review decision for an existing investigation.
 * Connects to POST /api/investigations/{id}/review
 *
 * @param {string} investigationId - Persistent investigation identifier.
 * @param {string} reviewStatus - Decision (APPROVED, REJECTED, FLAGGED).
 * @param {string} reviewerId - Identifier of human reviewer.
 * @param {string} reviewNotes - Optional reviewer rationale/notes.
 * @param {boolean} useMock - Whether to return mock data.
 * @returns {Promise<Object>} InvestigationReviewResponse matching backend contract.
 */
export async function submitReview(investigationId, reviewStatus, reviewerId, reviewNotes = null, useMock = false) {
  if (!investigationId) {
    throw new Error("Investigation ID is required for review submission.");
  }

  if (useMock) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(getMockReviewResponse(investigationId, reviewStatus, reviewerId, reviewNotes));
      }, 400);
    });
  }

  const response = await fetch(`/api/investigations/${encodeURIComponent(investigationId)}/review`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      review_status: reviewStatus,
      reviewer_id: reviewerId,
      review_notes: reviewNotes || null
    })
  });

  if (!response.ok) {
    const errorText = await response.text();
    let detail = errorText;
    try {
      const jsonErr = JSON.parse(errorText);
      if (jsonErr.detail) detail = jsonErr.detail;
    } catch {
      // fallback
    }
    if (response.status === 404) {
      throw new Error("Investigation not found.");
    } else if (response.status === 400) {
      throw new Error(`Cannot submit review: ${detail}`);
    } else if (response.status === 422) {
      throw new Error(`Validation Error: ${detail}`);
    } else {
      throw new Error("Review submission failed. Please try again.");
    }
  }

  return await response.json();
}

/**
 * Retrieves full investigation details by investigation_id.
 * Connects to GET /api/investigations/{id}
 *
 * @param {string} investigationId - Persistent investigation identifier.
 * @param {boolean} useMock - Whether to return mock data.
 * @returns {Promise<Object>} InvestigationDetail matching backend contract.
 */
export async function getInvestigationDetail(investigationId, useMock = false) {
  if (!investigationId) {
    throw new Error("Investigation ID is required.");
  }

  if (useMock) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(getMockInvestigationDetail(investigationId));
      }, 300);
    });
  }

  const response = await fetch(`/api/investigations/${encodeURIComponent(investigationId)}`, {
    method: 'GET',
    headers: getAuthHeaders({ 'Accept': 'application/json' })
  });

  if (!response.ok) {
    const errorText = await response.text();
    let detail = errorText;
    try {
      const jsonErr = JSON.parse(errorText);
      if (jsonErr.detail) detail = typeof jsonErr.detail === 'string' ? jsonErr.detail : JSON.stringify(jsonErr.detail);
    } catch {
      // fallback
    }
    if (response.status === 404) {
      throw new Error("Investigation not found.");
    }
    throw new Error(detail || "Failed to retrieve investigation detail.");
  }

  return await response.json();
}

/**
 * Retrieves a paginated list of persistent investigation summaries with optional search/filtering.
 * Connects to GET /api/investigations
 *
 * @param {number} limit - Maximum number of summary items.
 * @param {number} offset - Pagination offset.
 * @param {boolean} useMock - Whether to return mock data.
 * @param {string|null} search - Keyword search over question or ID.
 * @param {string|null} status - Filter by investigation lifecycle status.
 * @param {string|null} robustnessStatus - Filter by decision robustness status.
 * @returns {Promise<Array<Object>>} Array of InvestigationSummary objects.
 */
export async function listInvestigations(
  limit = 20,
  offset = 0,
  useMock = false,
  search = null,
  status = null,
  robustnessStatus = null,
  ownerId = null
) {
  if (useMock) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(getMockInvestigationsList(limit, offset, search, status, robustnessStatus, ownerId));
      }, 300);
    });
  }

  const params = new URLSearchParams();
  params.append('limit', String(limit));
  params.append('offset', String(offset));
  if (search && search.trim()) params.append('search', search.trim());
  if (status && status.trim()) params.append('status', status.trim());
  if (robustnessStatus && robustnessStatus.trim()) params.append('robustness_status', robustnessStatus.trim());
  if (ownerId && ownerId.trim()) params.append('owner_id', ownerId.trim());

  const response = await fetch(`/api/investigations?${params.toString()}`, {
    method: 'GET',
    headers: getAuthHeaders({ 'Accept': 'application/json' })
  });

  if (!response.ok) {
    const errorText = await response.text();
    let detail = errorText;
    try {
      const jsonErr = JSON.parse(errorText);
      if (jsonErr.detail) detail = typeof jsonErr.detail === 'string' ? jsonErr.detail : JSON.stringify(jsonErr.detail);
    } catch {
      // fallback
    }
    throw new Error(detail || "Failed to retrieve investigation history.");
  }

  return await response.json();
}

/**
 * Exports a persisted investigation audit report in JSON or Markdown format.
 * Connects to GET /api/investigations/{id}/export?format=json|markdown
 *
 * @param {string} investigationId - Persistent investigation identifier.
 * @param {string} format - Export format ('json' or 'markdown').
 * @param {boolean} useMock - Whether to return mock data.
 * @returns {Promise<Object|string>} JSON dict payload or Markdown text content.
 */
export async function exportInvestigationReport(investigationId, format = 'json', useMock = false) {
  if (!investigationId) {
    throw new Error("Investigation ID is required for report export.");
  }

  const fmt = (format || 'json').toLowerCase().trim();

  if (useMock) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(getMockExportData(investigationId, fmt));
      }, 300);
    });
  }

  const response = await fetch(`/api/investigations/${encodeURIComponent(investigationId)}/export?format=${fmt}`, {
    method: 'GET',
    headers: getAuthHeaders({
      'Accept': fmt === 'markdown' ? 'text/markdown, text/plain' : 'application/json'
    })
  });

  if (!response.ok) {
    const errorText = await response.text();
    let detail = errorText;
    try {
      const jsonErr = JSON.parse(errorText);
      if (jsonErr.detail) detail = typeof jsonErr.detail === 'string' ? jsonErr.detail : JSON.stringify(jsonErr.detail);
    } catch {
      // fallback
    }
    throw new Error(detail || "Failed to export investigation report.");
  }

  if (fmt === 'markdown') {
    return await response.text();
  }
  return await response.json();
}

/**
 * Retrieves global investigation metrics summary including total counts, status distribution,
 * human review decisions, robustness distribution, and average execution time.
 * Connects to GET /api/investigations/metrics/summary
 *
 * @param {boolean} useMock - Whether to return mock data.
 * @returns {Promise<Object>} InvestigationMetricsSummary object matching backend contract.
 */
export async function getAnalyticsSummary(useMock = false) {
  if (useMock) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(getMockAnalyticsSummary());
      }, 300);
    });
  }

  const response = await fetch('/api/investigations/metrics/summary', {
    method: 'GET',
    headers: getAuthHeaders({ 'Accept': 'application/json' })
  });

  if (!response.ok) {
    const errorText = await response.text();
    let detail = errorText;
    try {
      const jsonErr = JSON.parse(errorText);
      if (jsonErr.detail) detail = typeof jsonErr.detail === 'string' ? jsonErr.detail : JSON.stringify(jsonErr.detail);
    } catch {
      // fallback
    }
    throw new Error(detail || "Failed to retrieve global analytics summary.");
  }

  return await response.json();
}

/**
 * Retrieves database schema context from GET /api/tools/sql-schema.
 */
export async function getSqlSchema(useMock = false) {
  if (useMock) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(getMockSqlSchema());
      }, 300);
    });
  }

  const response = await fetch('/api/tools/sql-schema', {
    method: 'GET',
    headers: getAuthHeaders({ 'Accept': 'application/json' })
  });

  if (!response.ok) {
    throw new Error("Failed to retrieve SQL schema context.");
  }
  return await response.json();
}

/**
 * Retrieves enterprise security audit log entries from GET /api/v1/audit/logs.
 * Restricted to AUDITOR and ADMIN roles.
 */
export async function listAuditLogs(useMock = false, user_id = null, action_type = null, status = null, limit = 50, offset = 0) {
  if (useMock) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(getMockAuditLogs());
      }, 300);
    });
  }

  const params = new URLSearchParams();
  params.append('limit', String(limit));
  params.append('offset', String(offset));
  if (user_id) params.append('user_id', user_id);
  if (action_type) params.append('action_type', action_type);
  if (status) params.append('status', status);

  const response = await fetch(`/api/v1/audit/logs?${params.toString()}`, {
    method: 'GET',
    headers: getAuthHeaders({ 'Accept': 'application/json' })
  });

  if (!response.ok) {
    if (response.status === 403) {
      throw new Error("Access Forbidden: Audit Log access requires AUDITOR or ADMIN role.");
    }
    throw new Error("Failed to retrieve security audit logs.");
  }
  return await response.json();
}
