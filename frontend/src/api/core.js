/**
 * VERIDEX Centralized HTTP Core Request Engine
 * Standardizes URL resolution, authorization headers, request serialization,
 * multipart upload boundary management, response parsing, and error normalization.
 */

import { buildApiUrl } from './config.js';
import { getAuthToken, handleUnauthorized } from './session.js';

export class VeridexApiError extends Error {
  constructor(message, status, detail = null, data = null) {
    super(message);
    this.name = 'VeridexApiError';
    this.status = status;
    this.detail = detail;
    this.data = data;
  }
}

export class VeridexNetworkError extends Error {
  constructor(message = 'Backend service is unreachable. Please verify server connectivity.', originalError = null) {
    super(message);
    this.name = 'VeridexNetworkError';
    this.originalError = originalError;
  }
}

/**
 * Builds standard authorization headers.
 *
 * @param {Object} extraHeaders - Custom headers to merge
 * @returns {Object} Headers object with Authorization if token present
 */
export function getAuthHeaders(extraHeaders = {}) {
  const headers = { ...extraHeaders };
  const token = getAuthToken();
  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

/**
 * Central HTTP request dispatcher for all VERIDEX frontend views.
 *
 * @param {string} endpoint - Relative endpoint path (e.g. '/api/ask', '/health')
 * @param {Object} options - Fetch options
 * @param {string} options.method - HTTP method (GET, POST, etc.)
 * @param {any} options.body - Request body (object, string, FormData, or Blob)
 * @param {Object} options.headers - Custom request headers
 * @param {AbortSignal} options.signal - Optional AbortController signal
 * @param {string} options.responseType - Expected response format: 'json' (default), 'text', or 'blob'
 * @param {boolean} options.skipAuth - If true, omits Authorization header
 * @returns {Promise<any>} Parsed response data
 */
export async function apiRequest(endpoint, options = {}) {
  const {
    method = 'GET',
    body = null,
    headers = {},
    signal = null,
    responseType = 'json',
    skipAuth = false
  } = options;

  const url = buildApiUrl(endpoint);
  const requestHeaders = { ...headers };

  // Attach Authorization header if authenticated and not skipped
  if (!skipAuth) {
    const token = getAuthToken();
    if (token && !requestHeaders['Authorization']) {
      requestHeaders['Authorization'] = `Bearer ${token}`;
    }
  }

  let serializedBody = body;

  // Handle request body serialization
  if (body !== null && body !== undefined) {
    if (typeof FormData !== 'undefined' && body instanceof FormData) {
      // CRITICAL: When sending FormData, delete Content-Type to let the browser
      // automatically generate 'multipart/form-data; boundary=----WebKitFormBoundary...'
      delete requestHeaders['Content-Type'];
      serializedBody = body;
    } else if (typeof Blob !== 'undefined' && body instanceof Blob) {
      // Blob payload: retain or set explicit content type
      serializedBody = body;
    } else if (typeof body === 'object' && !(body instanceof String)) {
      if (!requestHeaders['Content-Type']) {
        requestHeaders['Content-Type'] = 'application/json';
      }
      serializedBody = JSON.stringify(body);
    }
  }

  // Set default Accept header if not explicitly configured
  if (!requestHeaders['Accept']) {
    if (responseType === 'text') {
      requestHeaders['Accept'] = 'text/plain, text/markdown, text/*, */*';
    } else if (responseType === 'blob') {
      requestHeaders['Accept'] = '*/*';
    } else {
      requestHeaders['Accept'] = 'application/json';
    }
  }

  const fetchConfig = {
    method,
    headers: requestHeaders,
    signal
  };

  if (serializedBody !== null && serializedBody !== undefined && method !== 'GET' && method !== 'HEAD') {
    fetchConfig.body = serializedBody;
  }

  let response;
  try {
    response = await fetch(url, fetchConfig);
  } catch (networkErr) {
    // Check if error was caused by manual abort
    if (signal && signal.aborted) {
      const abortError = new Error('Request was cancelled.');
      abortError.name = 'AbortError';
      throw abortError;
    }
    // Network / offline / server down error
    throw new VeridexNetworkError(
      `Unable to connect to VERIDEX backend at ${url}. Please ensure the backend is running and CORS is configured.`,
      networkErr
    );
  }

  // Handle HTTP 401 Unauthorized
  if (response.status === 401) {
    handleUnauthorized();
  }

  // Handle Non-2xx Responses
  if (!response.ok) {
    let errorDetail = response.statusText;
    let errorData = null;

    try {
      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        errorData = await response.json();
        if (errorData) {
          if (typeof errorData.detail === 'string') {
            errorDetail = errorData.detail;
          } else if (Array.isArray(errorData.detail)) {
            // Pydantic validation errors list
            errorDetail = errorData.detail.map((e) => `${e.loc?.join('.') || 'param'}: ${e.msg}`).join('; ');
          } else if (errorData.message) {
            errorDetail = errorData.message;
          } else {
            errorDetail = JSON.stringify(errorData);
          }
        }
      } else {
        const textErr = await response.text();
        if (textErr) errorDetail = textErr;
      }
    } catch {
      // Parsing fallback
    }

    throw new VeridexApiError(
      errorDetail || `Request failed with status code ${response.status}`,
      response.status,
      errorDetail,
      errorData
    );
  }

  // Handle Successful Responses based on requested format
  if (response.status === 204) {
    return null;
  }

  if (responseType === 'text') {
    return await response.text();
  }

  if (responseType === 'blob') {
    return await response.blob();
  }

  // Default: JSON parsing
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return await response.json();
  }

  const rawText = await response.text();
  try {
    return JSON.parse(rawText);
  } catch {
    return rawText;
  }
}

