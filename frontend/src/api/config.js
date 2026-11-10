/**
 * VERIDEX API Configuration Module
 * Manages API base URL resolution across local development, staging, and Render production.
 */

/**
 * Resolves the configured backend base URL.
 * In production (e.g. Render Static Site), VITE_API_BASE_URL points to the backend service.
 * In local development, if VITE_API_BASE_URL is not set, an empty string is returned
 * so requests use relative URLs which Vite's proxy routes to http://127.0.0.1:8000.
 *
 * @returns {string} Clean base URL without trailing slash.
 */
export function getApiBaseUrl() {
  const envUrl = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_BASE_URL)
    ? String(import.meta.env.VITE_API_BASE_URL).trim()
    : '';

  if (!envUrl) {
    return '';
  }

  // Strip trailing slashes
  return envUrl.replace(/\/+$/, '');
}

/**
 * Constructs a fully qualified API endpoint URL.
 * Handles leading slash normalization to prevent malformed double slashes.
 *
 * @param {string} endpoint - Path such as '/api/ask' or 'health'
 * @returns {string} Fully constructed URL
 */
export function buildApiUrl(endpoint) {
  const base = getApiBaseUrl();
  const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;

  if (!base) {
    return path;
  }

  return `${base}${path}`;
}

