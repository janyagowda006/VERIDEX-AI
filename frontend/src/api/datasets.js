/**
 * VERIDEX Data Sources & Ingestion API
 * Manages dataset uploads (CSV, Excel), table inspection, and ingestion status.
 */

import { apiRequest } from './core.js';
import { getSqlSchema } from './tools.js';

/**
 * Uploads a business data file (CSV or Excel) to the backend.
 * Uses FormData without manual multipart boundaries so the browser correctly
 * adds the multipart boundary string to the Content-Type header.
 *
 * @param {File} file - CSV or Excel file object
 * @param {Object} metadata - Optional dataset metadata
 * @param {AbortSignal|null} signal - Optional abort signal
 * @returns {Promise<Object>} Ingestion confirmation
 */
export async function uploadDataset(file, metadata = {}, signal = null) {
  if (!file) {
    throw new Error('A file must be selected for upload.');
  }

  // File type validation
  const validExtensions = ['.csv', '.xlsx', '.xls'];
  const fileName = file.name.toLowerCase();
  const isValidExtension = validExtensions.some((ext) => fileName.endsWith(ext));

  if (!isValidExtension) {
    throw new Error('Unsupported file format. Please upload a .csv or .xlsx spreadsheet.');
  }

  // Max 50MB safety limit
  const maxBytes = 50 * 1024 * 1024;
  if (file.size > maxBytes) {
    throw new Error('File exceeds maximum upload size of 50 MB.');
  }

  const formData = new FormData();
  formData.append('file', file);
  if (metadata.dataset_name) {
    formData.append('dataset_name', metadata.dataset_name);
  }
  if (metadata.description) {
    formData.append('description', metadata.description);
  }

  // Connects to /api/data-sources/upload or /api/data/upload
  return await apiRequest('/api/data-sources/upload', {
    method: 'POST',
    body: formData,
    signal
  });
}

// Alias for uploadDataset
export const upload_data_source_file = uploadDataset;


/**
 * Lists connected business data tables and current row counts.
 * Uses the database schema endpoint.
 *
 * @param {AbortSignal|null} signal
 * @returns {Promise<Array<Object>>}
 */
export async function listConnectedSources(signal = null) {
  const schema = await getSqlSchema(signal);
  if (!schema || !schema.tables) {
    return [];
  }

  return Object.entries(schema.tables).map(([tableName, tableDetails]) => ({
    name: tableName,
    type: 'Relational Database Table',
    columns: Array.isArray(tableDetails.columns)
      ? tableDetails.columns.map((c) => (typeof c === 'string' ? c : c.name || JSON.stringify(c)))
      : [],
    rowCount: schema.table_row_counts?.[tableName] ?? 0,
    status: 'Connected',
    access: 'Read-Only Safe Mode'
  }));
}

