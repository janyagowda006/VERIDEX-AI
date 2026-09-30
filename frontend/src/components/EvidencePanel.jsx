import React, { useState } from 'react';
import { ClaimBadge } from './ClaimBadge.jsx';

/**
 * Formats the calculation output based on the formula type defined in the API contract.
 * Supported contract formulas from backend/app/services/evidence_calculations.py:
 * - percentage_change: percentage unit (%)
 * - share_of_total: percentage unit (%)
 * - difference: absolute numeric value (no %)
 * - ratio: numeric ratio (no %)
 * Unknown types: safe neutral representation (no %)
 */
function formatCalculationOutput(calculation) {
  if (!calculation || calculation.output === null || calculation.output === undefined) {
    return 'Undefined';
  }

  const normalized = (calculation.formula_name || '').toLowerCase();

  switch (normalized) {
    case 'percentage_change':
    case 'share_of_total':
      return `${calculation.output}%`;
    case 'difference':
    case 'ratio':
      return `${calculation.output}`;
    default:
      return `${calculation.output}`;
  }
}

export function EvidencePanel({ evidence = [], toolCalls = [] }) {
  const [expanded, setExpanded] = useState(true);
  const [activeTab, setActiveTab] = useState('evidence');

  if (!evidence.length && !toolCalls.length) return null;

  return (
    <div className="card evidence-panel">
      <div className="card-header pointer" onClick={() => setExpanded(!expanded)}>
        <h2>Verified Evidence & Provenance Trace ({evidence.length})</h2>
        <span className="expand-icon">{expanded ? '▲' : '▼'}</span>
      </div>

      {expanded && (
        <div className="evidence-body">
          <div className="tab-buttons">
            <button
              className={`tab-btn ${activeTab === 'evidence' ? 'active' : ''}`}
              onClick={() => setActiveTab('evidence')}
            >
              Evidence Items ({evidence.length})
            </button>
            <button
              className={`tab-btn ${activeTab === 'tools' ? 'active' : ''}`}
              onClick={() => setActiveTab('tools')}
            >
              SQL Execution Trace ({toolCalls.length})
            </button>
          </div>

          {activeTab === 'evidence' && (
            <div className="evidence-list">
              {evidence.map((item) => (
                <div key={item.evidence_id} className="evidence-card">
                  <div className="ev-card-header">
                    <span className="ev-id">{item.evidence_id}</span>
                    <ClaimBadge type={item.evidence_type} />
                  </div>

                  <p className="ev-desc">{item.description}</p>

                  {/* FACT Evidence SQL Provenance */}
                  {item.source && (
                    <div className="provenance-box">
                      <div className="prov-row">
                        <strong>SQL Query:</strong>
                        <pre className="sql-block">{item.source.sql}</pre>
                      </div>
                      <div className="prov-meta">
                        <span><strong>Query Hash:</strong> <code>{item.source.query_hash.substring(0, 16)}...</code></span>
                        <span><strong>Execution Time:</strong> {item.source.execution_metadata.execution_time_ms} ms</span>
                        <span><strong>Timestamp:</strong> {item.source.timestamp}</span>
                      </div>

                      {/* Sample Rows Table */}
                      {item.source.relevant_rows && item.source.relevant_rows.length > 0 && (
                        <div className="table-wrapper">
                          <table className="data-table">
                            <thead>
                              <tr>
                                {item.source.columns.map((col) => (
                                  <th key={col}>{col}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {item.source.relevant_rows.map((row, rIdx) => (
                                <tr key={rIdx}>
                                  {item.source.columns.map((col) => (
                                    <td key={col}>{row[col] !== undefined ? String(row[col]) : ''}</td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}

                  {/* DERIVED_FACT Calculation Provenance */}
                  {item.calculation && (
                    <div className="calculation-box">
                      <div><strong>Formula:</strong> <code>{item.calculation.formula}</code></div>
                      <div><strong>Formula Output:</strong> {formatCalculationOutput(item.calculation)}</div>
                      <div><strong>Inputs:</strong> {JSON.stringify(item.calculation.inputs)}</div>
                      <div><strong>Parent Evidence IDs:</strong> {item.calculation.input_evidence_ids.join(', ')}</div>
                    </div>
                  )}

                  {item.limitations && item.limitations.length > 0 && (
                    <div className="limitations-box">
                      <strong>Limitations:</strong>
                      <ul>
                        {item.limitations.map((lim, idx) => (
                          <li key={idx}>{lim}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {activeTab === 'tools' && (
            <div className="tool-trace-list">
              {toolCalls.map((tc, idx) => (
                <div key={idx} className="tool-trace-card">
                  <div className="trace-header">
                    <span>Turn {tc.turn}: {tc.tool_name}</span>
                    <span className={`status-tag ${tc.result.success ? 'success' : 'failed'}`}>
                      {tc.result.success ? 'SUCCESS' : 'FAILED'}
                    </span>
                  </div>
                  <pre className="sql-block">{tc.arguments.sql}</pre>
                  <p className="trace-info">Returned {tc.result.row_count} records in {tc.result.metadata?.execution_time_ms || 0} ms</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
