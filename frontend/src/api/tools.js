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
  const data = await apiRequest('/api/tools/sql-schema', {
    method: 'GET',
    signal
  });

  // Normalize schema: if tables is an array of TableSchema objects, provide mapped dictionary
  if (data && Array.isArray(data.tables)) {
    const tableMap = {};
    for (const t of data.tables) {
      tableMap[t.name] = {
        name: t.name,
        columns: t.columns || [],
        foreign_keys: t.foreign_keys || []
      };
    }
    return {
      ...data,
      tables: tableMap,
      raw_tables: data.tables
    };
  }

  return data;
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

/**
 * Executes metric driver decomposition across dimensions.
 * Connects to POST /api/tools/decompose
 *
 * @param {Object} params
 * @param {AbortSignal|null} signal
 * @returns {Promise<Object>} DecompositionResponse
 */
export async function runDriverDecomposition(params = {}, signal = null) {
  return await apiRequest('/api/tools/decompose', {
    method: 'POST',
    body: params,
    signal
  });
}

/**
 * Evaluates campaign lift using Difference-in-Differences.
 * Connects to POST /api/tools/campaign-impact
 *
 * @param {Object} params
 * @param {AbortSignal|null} signal
 * @returns {Promise<Object>} CampaignImpactResponse
 */
export async function evaluateCampaignImpact(params = {}, signal = null) {
  return await apiRequest('/api/tools/campaign-impact', {
    method: 'POST',
    body: params,
    signal
  });
}

/**
 * Verifies numerical claims in an answer against evidence items.
 * Connects to POST /api/verify
 *
 * @param {Object} params
 * @param {AbortSignal|null} signal
 * @returns {Promise<Object>} VerificationResponse
 */
export async function verifyAnswerClaims(params = {}, signal = null) {
  return await apiRequest('/api/verify', {
    method: 'POST',
    body: params,
    signal
  });
}


