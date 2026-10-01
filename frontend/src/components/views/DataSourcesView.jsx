import React, { useState, useEffect } from 'react';
import { getSqlSchema } from '../../api/client.js';

export function DataSourcesView({ useMock = false }) {
  const [schema, setSchema] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedTable, setSelectedTable] = useState('customers');

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);

    getSqlSchema(useMock)
      .then((data) => {
        if (isMounted) {
          setSchema(data);
          if (data.tables && data.tables.length > 0) {
            setSelectedTable(data.tables[0].name);
          }
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || 'Failed to load database schema context.');
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [useMock]);

  const currentTableData = schema?.tables?.find((t) => t.name === selectedTable);

  return (
    <div className="view-container datasources-view">
      <div className="view-header">
        <div>
          <h2>Data Sources & SQL Security Constraints</h2>
          <p className="view-subtitle">
            Verified PostgreSQL business tables. Read-only SELECT access enforced by AST parsing.
          </p>
        </div>
        <span className="badge badge-platform">PostgreSQL 16 Engine</span>
      </div>

      {/* SQL Safety & Governance Guardrails Banner */}
      <div className="card guardrails-card" style={{ marginBottom: '1.5rem', backgroundColor: 'var(--bg-card-subtle)', borderColor: 'var(--border-light)' }}>
        <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span>🛡️</span> SQL Security & Deterministic Execution Rules
        </h3>
        <div className="guardrails-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem', fontSize: '0.85rem' }}>
          <div className="rule-item">
            <strong>SELECT-Only AST Validation:</strong> SQLGlot parses every query. `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER` are strictly blocked.
          </div>
          <div className="rule-item">
            <strong>Row & Timeout Bounds:</strong> Queries are bounded by max 1000 rows and a strict 5.0s execution timeout.
          </div>
          <div className="rule-item">
            <strong>Single Source of Truth:</strong> The <code>region</code> field exists ONLY in <code>customers</code>. Region joins are enforced on <code>orders.customer_id</code>.
          </div>
        </div>
      </div>

      {loading && (
        <div className="card loading-card" role="status">
          <div className="spinner" aria-hidden="true"></div>
          <p>Loading database schema context...</p>
        </div>
      )}

      {error && (
        <div className="card error-card" role="alert">
          <span className="error-icon" aria-hidden="true">⚠️</span>
          <p>{error}</p>
        </div>
      )}

      {!loading && !error && schema && (
        <div className="datasources-layout" style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: '1.5rem' }}>
          {/* Table List Selector */}
          <div className="table-selector-card card" style={{ padding: '1rem' }}>
            <h4 style={{ fontSize: '0.875rem', fontWeight: '600', marginBottom: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>
              Database Tables ({schema.tables?.length || 0})
            </h4>
            <div className="table-nav" role="tablist" style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              {schema.tables?.map((table) => (
                <button
                  key={table.name}
                  type="button"
                  role="tab"
                  aria-selected={selectedTable === table.name}
                  className={`table-nav-btn ${selectedTable === table.name ? 'active' : ''}`}
                  onClick={() => setSelectedTable(table.name)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justify: 'space-between',
                    padding: '0.5rem 0.75rem',
                    borderRadius: '0.375rem',
                    fontSize: '0.875rem',
                    fontWeight: selectedTable === table.name ? '600' : '400',
                    border: '1px solid',
                    borderColor: selectedTable === table.name ? 'var(--color-primary)' : 'transparent',
                    backgroundColor: selectedTable === table.name ? 'var(--bg-card-subtle)' : 'transparent',
                    color: selectedTable === table.name ? 'var(--color-primary)' : 'var(--text-primary)',
                    cursor: 'pointer',
                    textAlign: 'left'
                  }}
                >
                  <span>📋 {table.name}</span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>{table.columns?.length} cols</span>
                </button>
              ))}
            </div>
          </div>

          {/* Table Detail View */}
          <div className="table-detail-card card">
            {currentTableData ? (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid var(--border-light)', paddingBottom: '0.75rem' }}>
                  <h3 style={{ fontSize: '1.125rem', fontWeight: '700', margin: 0 }}>
                    Table: <code>{currentTableData.name}</code>
                  </h3>
                  <span className="badge badge-platform">Safe Read-Only</span>
                </div>

                <h4 style={{ fontSize: '0.875rem', fontWeight: '600', marginBottom: '0.5rem' }}>Columns & Schema Definition</h4>
                <div style={{ overflowX: 'auto', marginBottom: '1.5rem' }}>
                  <table className="data-table" style={{ width: '100%', fontSize: '0.85rem', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ backgroundColor: 'var(--bg-card-subtle)', textAlign: 'left' }}>
                        <th style={{ padding: '0.5rem 0.75rem' }}>Column Name</th>
                        <th style={{ padding: '0.5rem 0.75rem' }}>Data Type</th>
                        <th style={{ padding: '0.5rem 0.75rem' }}>Primary Key</th>
                        <th style={{ padding: '0.5rem 0.75rem' }}>Nullable</th>
                      </tr>
                    </thead>
                    <tbody>
                      {currentTableData.columns?.map((col) => (
                        <tr key={col.name} style={{ borderBottom: '1px solid var(--border-light)' }}>
                          <td style={{ padding: '0.5rem 0.75rem', fontWeight: col.primary_key ? '600' : '400' }}>
                            <code>{col.name}</code>
                          </td>
                          <td style={{ padding: '0.5rem 0.75rem', color: 'var(--text-secondary)' }}>{col.type}</td>
                          <td style={{ padding: '0.5rem 0.75rem' }}>
                            {col.primary_key ? <span style={{ color: 'var(--color-success)', fontWeight: '600' }}>[PK] Yes</span> : 'No'}
                          </td>
                          <td style={{ padding: '0.5rem 0.75rem', color: 'var(--text-tertiary)' }}>
                            {col.nullable ? 'Yes' : 'No'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {currentTableData.foreign_keys && currentTableData.foreign_keys.length > 0 && (
                  <div>
                    <h4 style={{ fontSize: '0.875rem', fontWeight: '600', marginBottom: '0.5rem' }}>Foreign Key Relationships</h4>
                    <ul style={{ paddingLeft: '1.25rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                      {currentTableData.foreign_keys.map((fk, idx) => (
                        <li key={idx} style={{ marginBottom: '0.35rem' }}>
                          <code>({fk.constrained_columns?.join(', ')})</code> → <code>{fk.referred_table}({fk.referred_columns?.join(', ')})</code>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <p className="no-data-text">Select a table to view schema details.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
