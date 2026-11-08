/**
 * VERIDEX Investigation & Decision Intelligence API
 * Connects to:
 * - POST /api/ask
 * - GET  /api/investigations
 * - GET  /api/investigations/metrics/summary
 * - GET  /api/investigations/{id}
 * - POST /api/investigations/{id}/reassess
 * - GET  /api/investigations/{id}/export
 */

import { apiRequest } from './core.js';
import {
  getMockAskResponse,
  getMockReassessResponse,
  getMockInvestigationDetail,
  getMockInvestigationsList,
  getMockAnalyticsSummary,
  getMockExportData
} from '../mocks/mockData.js';

/**
 * Executes or continues a natural language decision intelligence investigation.
 * Connects to POST /api/ask
 *
 * @param {string} question - Natural language business inquiry
 * @param {number} maxTurns - Maximum allowed exploration turns
 * @param {boolean} useMock - Fallback mock flag
 * @param {string|null} investigationId - Optional persistent ID for multi-turn threads
 * @param {AbortSignal|null} signal - Optional abort signal
 * @returns {Promise<Object>} AskResponse payload
 */
export async function askQuestion(question, maxTurns = 3, useMock = false, investigationId = null, signal = null) {
  if (useMock) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(getMockAskResponse(question, investigationId));
      }, 400);
    });
  }

  const payload = {
    question: question.trim(),
    max_turns: maxTurns
  };

  if (investigationId) {
    payload.investigation_id = investigationId;
  }

  return await apiRequest('/api/ask', {
    method: 'POST',
    body: payload,
    signal
  });
}

/**
 * Reassesses multi-scenario robustness for an existing persisted investigation.
 * Connects to POST /api/investigations/{id}/reassess
 *
 * @param {string} investigationId - Persistent investigation identifier
 * @param {number} scenarioShiftPct - Metric perturbation percentage (e.g. 10.0)
 * @param {boolean} useMock - Fallback mock flag
 * @param {AbortSignal|null} signal - Optional abort signal
 * @returns {Promise<Object>} InvestigationReassessResponse
 */
export async function reassessInvestigation(investigationId, scenarioShiftPct = 10.0, useMock = false, signal = null) {
  if (!investigationId) {
    throw new Error('Investigation ID is required for re-assessment.');
  }

  if (useMock) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(getMockReassessResponse(investigationId, scenarioShiftPct));
      }, 350);
    });
  }

  return await apiRequest(`/api/investigations/${encodeURIComponent(investigationId)}/reassess`, {
    method: 'POST',
    body: {
      scenario_shift_pct: Number(scenarioShiftPct)
    },
    signal
  });
}

/**
 * Retrieves full audit details for a specific investigation.
 * Connects to GET /api/investigations/{id}
 *
 * @param {string} investigationId - Persistent investigation identifier
 * @param {boolean} useMock - Fallback mock flag
 * @param {AbortSignal|null} signal - Optional abort signal
 * @returns {Promise<Object>} InvestigationDetail payload
 */
export async function getInvestigationDetail(investigationId, useMock = false, signal = null) {
  if (!investigationId) {
    throw new Error('Investigation ID is required.');
  }

  if (useMock) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(getMockInvestigationDetail(investigationId));
      }, 250);
    });
  }

  return await apiRequest(`/api/investigations/${encodeURIComponent(investigationId)}`, {
    method: 'GET',
    signal
  });
}

/**
 * Retrieves a paginated list of persistent investigation summaries with optional search and filters.
 * Connects to GET /api/investigations
 *
 * @param {number} limit - Maximum number of items
 * @param {number} offset - Pagination offset
 * @param {boolean} useMock - Fallback mock flag
 * @param {string|null} search - Search query on question or ID
 * @param {string|null} status - Filter by investigation status
 * @param {string|null} robustnessStatus - Filter by robustness status
 * @param {string|null} ownerId - Optional owner filter
 * @param {AbortSignal|null} signal - Optional abort signal
 * @returns {Promise<Array<Object>>} List of InvestigationSummary records
 */
export async function listInvestigations(
  limit = 20,
  offset = 0,
  useMock = false,
  search = null,
  status = null,
  robustnessStatus = null,
  ownerId = null,
  signal = null
) {
  if (useMock) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(getMockInvestigationsList(limit, offset, search, status, robustnessStatus, ownerId));
      }, 250);
    });
  }

  const queryParams = new URLSearchParams();
  queryParams.append('limit', String(limit));
  queryParams.append('offset', String(offset));
  if (search && search.trim()) queryParams.append('search', search.trim());
  if (status && status.trim()) queryParams.append('status', status.trim());
  if (robustnessStatus && robustnessStatus.trim()) queryParams.append('robustness_status', robustnessStatus.trim());
  if (ownerId && ownerId.trim()) queryParams.append('owner_id', ownerId.trim());

  return await apiRequest(`/api/investigations?${queryParams.toString()}`, {
    method: 'GET',
    signal
  });
}

/**
 * Exports an investigation audit report as structured JSON or Markdown.
 * Connects to GET /api/investigations/{id}/export?format=json|markdown
 *
 * @param {string} investigationId - Persistent investigation identifier
 * @param {string} format - 'json' or 'markdown'
 * @param {boolean} useMock - Fallback mock flag
 * @param {AbortSignal|null} signal - Optional abort signal
 * @returns {Promise<Object|string>} JSON dict or Markdown text
 */
export async function exportInvestigationReport(investigationId, format = 'json', useMock = false, signal = null) {
  if (!investigationId) {
    throw new Error('Investigation ID is required for report export.');
  }

  const fmt = (format || 'json').toLowerCase().trim();

  if (useMock) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(getMockExportData(investigationId, fmt));
      }, 250);
    });
  }

  return await apiRequest(`/api/investigations/${encodeURIComponent(investigationId)}/export?format=${fmt}`, {
    method: 'GET',
    responseType: fmt === 'markdown' ? 'text' : 'json',
    signal
  });
}

/**
 * Downloads the investigation audit report as an attachment in the browser.
 *
 * @param {string} investigationId
 * @param {'json'|'markdown'} format
 * @param {boolean} useMock
 */
export async function downloadInvestigationReport(investigationId, format = 'json', useMock = false) {
  const content = await exportInvestigationReport(investigationId, format, useMock);
  const isJson = format.toLowerCase() === 'json';
  const blob = new Blob(
    [isJson ? JSON.stringify(content, null, 2) : content],
    { type: isJson ? 'application/json' : 'text/markdown;charset=utf-8' }
  );
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${investigationId}_audit_report.${isJson ? 'json' : 'md'}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * Retrieves global investigation metrics summary across the platform.
 * Connects to GET /api/investigations/metrics/summary
 *
 * @param {boolean} useMock - Fallback mock flag
 * @param {AbortSignal|null} signal - Optional abort signal
 * @returns {Promise<Object>} InvestigationMetricsSummary
 */
export async function getAnalyticsSummary(useMock = false, signal = null) {
  if (useMock) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(getMockAnalyticsSummary());
      }, 250);
    });
  }

  return await apiRequest('/api/investigations/metrics/summary', {
    method: 'GET',
    signal
  });
}

