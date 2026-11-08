/**
 * VERIDEX Tools & Infrastructure Inspection API
 * Connects to:
 * - GET  /health
 * - GET  /db-status
 * - GET  /api/tools/sql-schema
 * - POST /api/tools/sql-query
 */

import { apiRequest } from './core.js';

/**
 * Public health check confirming backend service readiness.
 *
 * @param {AbortSignal|null} signal
 * @returns {Promise<{ status: string }>}
 */
export async function getHealth(signal = null) {
  return await apiRequest('/health', {
    method: 'GET',
    skipAuth: true,
    signal
  });
}

/**
 * Database connectivity and record count check (Admin only).
 *
 * @param {AbortSignal|null} signal
 * @returns {Promise<Object>}
 */
export async function getDbStatus(signal = null) {
  return await apiRequest('/db-status', {
    method: 'GET',
    signal
  });
}

/**
 * Introspects relational database tables, columns, primary keys, and relationships.
 * Connects to GET /api/tools/sql-schema
 *
 * @param {AbortSignal|null} signal
 * @returns {Promise<{ tables: Object, relationships: Array, table_row_counts: Object }>}
 */
export async function getSqlSchema(signal = null) {
  return await apiRequest('/api/tools/sql-schema', {
    method: 'GET',
    signal
  });
}

/**
 * Executes a safe, read-only SQL query against the connected database (Admin only).
 * Connects to POST /api/tools/sql-query
 *
 * @param {string} query
 * @param {AbortSignal|null} signal
 * @returns {Promise<Object>} SQLQueryResult
 */
export async function runSqlQuery(query, signal = null) {
  return await apiRequest('/api/tools/sql-query', {
    method: 'POST',
    body: { query: query.trim() },
    signal
  });
}

