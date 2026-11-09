import React, { useState, useEffect, useCallback } from 'react';
import { getSqlSchema, uploadDataset } from '../../api/client.js';

export function SourcesView({ _currentUser = null, _onNavigate = null }) {
  const [schemaData, setSchemaData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // File Upload State
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [uploadSuccess, setUploadSuccess] = useState(null);

  // Selected table for detailed schema inspection
  const [selectedTable, setSelectedTable] = useState('orders');

  const loadSchema = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getSqlSchema();
      setSchemaData(data);
      if (data?.tables) {
        const tableNames = Object.keys(data.tables);
        if (tableNames.length > 0 && !tableNames.includes(selectedTable)) {
          setSelectedTable(tableNames[0]);
        }
      }
    } catch (err) {
      setError(err.detail || err.message || 'Failed to inspect database schema context.');
    } finally {
      setLoading(false);
    }
  }, [selectedTable]);

  useEffect(() => {
    loadSchema();
  }, [loadSchema]);

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    setUploadError(null);
    setUploadSuccess(null);
    if (!file) return;

    const validExtensions = ['.csv', '.xlsx', '.xls'];
    const name = file.name.toLowerCase();
    const isValid = validExtensions.some((ext) => name.endsWith(ext));

    if (!isValid) {
      setUploadError('Invalid format. Please select a .csv or .xlsx business dataset.');
      setSelectedFile(null);
      return;
    }

    if (file.size > 50 * 1024 * 1024) {
      setUploadError('File exceeds maximum upload size (50MB).');
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
  };

  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (!selectedFile) return;

    setUploadLoading(true);
    setUploadError(null);
    setUploadSuccess(null);

    try {
      const result = await uploadDataset(selectedFile);
      setUploadSuccess(`Successfully ingested '${selectedFile.name}'. ${result.message || ''}`);
      setSelectedFile(null);
      // Refresh schema after ingestion
      loadSchema();
    } catch (err) {
      // If endpoint returns 404 or backend route not implemented yet
      setUploadError(
        err.status === 404
          ? `File upload endpoint (/api/data/upload) is awaiting backend deployment by Gagandeep. Current analysis runs against the verified relational database schema.`
          : (err.detail || err.message || 'File ingestion failed.')
      );
    } finally {
      setUploadLoading(false);
    }
  };

  const tables = schemaData?.tables || {};
  const tableNames = Object.keys(tables);
  const activeTableSchema = tables[selectedTable] || null;

  return (
    <div className="view-shell sources-view-shell" role="region" aria-label="Connected Data Sources">
      {/* Top Safe Mode Guarantee Banner */}
      <div className="card safe-access-banner">
        <span className="safe-badge">RO</span>
        <div>
          <strong>Read-Only Access Enforced.</strong>
          <span>
            {' '}VERIDEX queries business data via deterministic, read-only SQL inspection with SQLGlot AST validation. Prohibited DDL/DML, table alterations, and statement injections are structurally rejected.
          </span>
        </div>
      </div>

      {/* Header */}
      <div className="sources-view-header">
        <div>
          <h1 className="sources-view-title">Connected Business Data Sources</h1>
          <p className="sources-view-subtitle">
            Relational operational tables, verified schema columns, and dataset ingestion.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-outline btn-sm"
          onClick={loadSchema}
          disabled={loading}
          aria-label="Refresh database schema"
        >
          <span className="btn-icon" aria-hidden="true">↻</span>
          Refresh Schema
        </button>
      </div>

      {/* Main Grid: Schema Inspection (Left) + File Upload & Ingestion (Right) */}
      <div className="sources-layout-grid">
        {/* Left Column: Relational Tables & Schema Details */}
        <div className="sources-schema-column">
          <div className="card sources-table-card">
            <div className="card-header-row">
              <h2 className="section-heading">Operational Database Tables</h2>
              <span className="badge badge-platform">PostgreSQL 16</span>
            </div>

            {loading ? (
              <div className="history-state-container" role="status">
                <span className="btn-spinner" aria-hidden="true"></span>
                <span>Inspecting database schema and relationships...</span>
              </div>
            ) : error ? (
              <div className="history-state-container history-error-state" role="alert">
                <span className="error-icon" aria-hidden="true">⚠️</span>
                <p>{error}</p>
                <button type="button" className="btn btn-outline btn-sm" onClick={loadSchema}>
                  Retry Schema Introspection
                </button>
              </div>
            ) : tableNames.length === 0 ? (
              <p className="summary-desc">No database tables introspected.</p>
            ) : (
              <>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Table Name</th>
                      <th>Columns</th>
                      <th>Row Count</th>
                      <th>Safety Mode</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tableNames.map((name) => {
                      const tInfo = tables[name];
                      const cols = tInfo?.columns || [];
                      const count = schemaData?.table_row_counts?.[name] ?? '—';
                      const isSelected = selectedTable === name;

                      return (
                        <tr
                          key={name}
                          className={`pointer ${isSelected ? 'highlight-row' : ''}`}
                          onClick={() => setSelectedTable(name)}
                        >
                          <td>
                            <strong>{name}</strong>
                          </td>
                          <td>{cols.length} attributes</td>
                          <td style={{ fontFamily: 'var(--font-mono)' }}>{count.toLocaleString()}</td>
                          <td>
                            <span className="status-badge status-badge-ok">✓ Read-Only Safe</span>
                          </td>
                          <td>
                            <button
                              type="button"
                              className={`btn btn-xs ${isSelected ? 'btn-primary' : 'btn-outline'}`}
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedTable(name);
                              }}
                            >
                              Inspect Schema
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>

                {/* Detailed Column Inspector for Selected Table */}
                {activeTableSchema && (
                  <div className="table-column-inspector" style={{ marginTop: '1.5rem' }}>
                    <div className="card-header-row">
                      <h3 style={{ fontSize: '1rem', margin: 0 }}>
                        Table Schema: <code>{selectedTable}</code>
                      </h3>
                      <span className="meta-val">
                        {activeTableSchema.columns?.length || 0} Columns · Primary Key:{' '}
                        <code>{activeTableSchema.primary_key || `${selectedTable}_id`}</code>
                      </span>
                    </div>

                    <div className="table-responsive-wrapper" style={{ marginTop: '0.75rem' }}>
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Column Name</th>
                            <th>Data Type</th>
                            <th>Constraint</th>
                            <th>Sample / Notes</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(activeTableSchema.columns || []).map((col) => {
                            const colName = typeof col === 'string' ? col : col.name || col.column_name;
                            const colType = typeof col === 'object' ? col.type || col.data_type || 'VARCHAR' : 'ATTRIBUTE';
                            const isPk = colName === activeTableSchema.primary_key || colName.endsWith('_id');

                            return (
                              <tr key={colName}>
                                <td>
                                  <code>{colName}</code>
                                </td>
                                <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--mu)' }}>
                                  {colType}
                                </td>
                                <td>
                                  {isPk ? (
                                    <span className="status-badge status-badge-ok">PRIMARY KEY</span>
                                  ) : (
                                    <span className="meta-val">Standard</span>
                                  )}
                                </td>
                                <td className="summary-desc">
                                  {colName === 'region'
                                    ? 'Single Source of Truth (customers table only)'
                                    : colName.includes('revenue') || colName.includes('price')
                                      ? 'Monetary business metric'
                                      : 'Verified relational column'}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Right Column: Dataset Upload & Ingestion */}
        <div className="sources-upload-column">
          <div className="card pad-card">
            <span className="cap-label">Data Ingestion</span>
            <h2 className="section-heading" style={{ marginTop: '0.25rem' }}>
              Upload Spreadsheet Dataset
            </h2>
            <p className="summary-desc">
              Ingest business data (CSV or Excel) into the VERIDEX safe execution environment for deterministic inquiry.
            </p>

            {uploadError && (
              <div className="review-message message-error" role="alert" style={{ marginBottom: '1rem' }}>
                <span className="msg-icon" aria-hidden="true">⚠️</span>
                <span>{uploadError}</span>
              </div>
            )}

            {uploadSuccess && (
              <div className="review-message message-success" role="status" style={{ marginBottom: '1rem' }}>
                <span className="msg-icon" aria-hidden="true">✓</span>
                <span>{uploadSuccess}</span>
              </div>
            )}

            <form onSubmit={handleUploadSubmit} className="upload-form">
              <div className="upload-dropzone">
                <input
                  type="file"
                  id="datasetFileInput"
                  accept=".csv,.xlsx,.xls"
                  onChange={handleFileChange}
                  disabled={uploadLoading}
                  className="file-input-hidden"
                />
                <label htmlFor="datasetFileInput" className="dropzone-label">
                  <span className="dropzone-icon" aria-hidden="true">📁</span>
                  <span className="dropzone-title">
                    {selectedFile ? selectedFile.name : 'Choose CSV or Excel file'}
                  </span>
                  <span className="dropzone-sub">
                    {selectedFile
                      ? `${(selectedFile.size / 1024).toFixed(1)} KB · Ready to ingest`
                      : 'Drag & drop or click to browse (.csv, .xlsx up to 50MB)'}
                  </span>
                </label>
              </div>

              <div className="upload-actions" style={{ marginTop: '1rem' }}>
                <button
                  type="submit"
                  className="btn btn-primary btn-block"
                  disabled={!selectedFile || uploadLoading}
                >
                  {uploadLoading ? (
                    <span className="btn-loading-content">
                      <span className="btn-spinner" aria-hidden="true"></span>
                      <span>Ingesting Dataset...</span>
                    </span>
                  ) : (
                    <span>Upload & Ingest Dataset →</span>
                  )}
                </button>
              </div>
            </form>

            <div className="callout-card callout-border-stable" style={{ marginTop: '1.25rem' }}>
              <span className="cap-label">Ingestion Guarantee</span>
              <p style={{ margin: 0, fontSize: '0.85rem' }}>
                Uploaded files are parsed deterministically into relational structures. No prompt injection or unverified code execution can alter data tables.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default SourcesView;
