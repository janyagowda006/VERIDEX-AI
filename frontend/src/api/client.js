import {
  MOCK_ASK_RESPONSE,
  getMockReassessResponse,
  getMockReviewResponse,
  getMockInvestigationDetail,
  getMockInvestigationsList,
  getMockAnalyticsSummary
} from '../mocks/mockData.js';

/**
 * VERIDEX API client for decision intelligence queries.
 * Connects to POST /api/ask endpoint or resolves mock data for development.
 *
 * @param {string} question - Business question text.
 * @param {number} maxTurns - Maximum investigation turns.
 * @param {boolean} useMock - Whether to return mock data.
 * @returns {Promise<Object>} AskResponse object matching frozen backend contract.
 */
export async function askQuestion(question, maxTurns = 3, useMock = false) {
  if (useMock) {
    // Return deterministic mock response
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          ...MOCK_ASK_RESPONSE,
          question: question || MOCK_ASK_RESPONSE.question
        });
      }, 500);
    });
  }

  const response = await fetch('/api/ask', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      question: question,
      max_turns: maxTurns
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
    headers: {
      'Content-Type': 'application/json'
    },
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
    headers: {
      'Content-Type': 'application/json'
    },
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
    headers: {
      'Accept': 'application/json'
    }
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
 * Retrieves a paginated list of persistent investigation summaries.
 * Connects to GET /api/investigations
 *
 * @param {number} limit - Maximum number of summary items.
 * @param {number} offset - Pagination offset.
 * @param {boolean} useMock - Whether to return mock data.
 * @returns {Promise<Array<Object>>} Array of InvestigationSummary objects.
 */
export async function listInvestigations(limit = 20, offset = 0, useMock = false) {
  if (useMock) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(getMockInvestigationsList(limit, offset));
      }, 300);
    });
  }

  const response = await fetch(`/api/investigations?limit=${limit}&offset=${offset}`, {
    method: 'GET',
    headers: {
      'Accept': 'application/json'
    }
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
    headers: {
      'Accept': 'application/json'
    }
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
