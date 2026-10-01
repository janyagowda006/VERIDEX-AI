import React, { useState, useEffect } from 'react';
import { ClaimBadge } from './ClaimBadge.jsx';
import { CopyButton } from './CopyButton.jsx';
import { EvidenceDecisionTrace } from './visualization/EvidenceDecisionTrace.jsx';

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

export function EvidencePanel({
  evidence = [],
  toolCalls = [],
  claims = [],
  criteria = [],
  recommendation = null,
  selectedEvidenceId,
  onSelectEvidence
}) {
  const [expanded, setExpanded] = useState(true);
  const [activeTab, setActiveTab] = useState('evidence');

  // Bidirectional navigation: auto-expand and scroll to targeted evidence item
  useEffect(() => {
    if (!selectedEvidenceId) return;

    const timer = setTimeout(() => {
      setExpanded(true);
      setActiveTab('evidence');
      const el = document.getElementById(`evidence-${selectedEvidenceId}`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 50);

    return () => clearTimeout(timer);
  }, [selectedEvidenceId]);

  if (!evidence.length && !toolCalls.length) return null;

  return (
    <div className="card evidence-panel">
      <button
        type="button"
        className="card-header card-header-toggle pointer"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        aria-controls="evidence-panel-body"
      >
        <h2>Evidence & Provenance Trace ({evidence.length})</h2>
        <span className="expand-icon" aria-hidden="true">{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div id="evidence-panel-body" className="evidence-body">
          <div className="tab-buttons" role="tablist" aria-label="Evidence and SQL provenance tabs">
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === 'evidence'}
              className={`tab-btn ${activeTab === 'evidence' ? 'active' : ''}`}
              onClick={() => setActiveTab('evidence')}
            >
              Evidence Items ({evidence.length})
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === 'tools'}
              className={`tab-btn ${activeTab === 'tools' ? 'active' : ''}`}
              onClick={() => setActiveTab('tools')}
            >
              SQL Execution Trace ({toolCalls.length})
            </button>
          </div>

          {activeTab === 'evidence' && (
            <div className="evidence-list">
              {/* Visual End-to-End Evidence Lineage Flowchart */}
              {evidence.length > 0 && (
                <div className="evidence-viz-block">
                  <EvidenceDecisionTrace
                    evidence={evidence}
                    claims={claims}
                    criteria={criteria}
                    recommendation={recommendation}
                    onSelectEvidence={onSelectEvidence}
                  />
                </div>
              )}
              {evidence.length === 0 ? (
                <p className="no-data-text">No evidence items recorded for this investigation.</p>
              ) : (
                evidence.map((item) => (
                <div
                  key={item.evidence_id}
                  id={`evidence-${item.evidence_id}`}
                  className={`evidence-card ${selectedEvidenceId === item.evidence_id ? 'highlighted' : ''}`}
                >
                  {selectedEvidenceId === item.evidence_id && (
                    <div className="active-evidence-indicator">
                      <span className="indicator-dot" aria-hidden="true">●</span> Selected Evidence ({item.evidence_id})
                    </div>
                  )}

                  <div className="ev-card-header">
                    <span className="ev-id">{item.evidence_id}</span>
                    <ClaimBadge type={item.evidence_type} />
                  </div>

                  <p className="ev-desc">{item.description}</p>

                  {/* FACT Evidence SQL Provenance */}
                  {item.source && (
                    <div className="provenance-box">
                      <div className="prov-row">
                        <div className="sql-header">
                          <strong>SQL Query:</strong>
                          <CopyButton text={item.source.sql} label="Copy SQL" className="copy-btn-sm" />
                        </div>
                        <pre className="sql-block"><code>{item.source.sql}</code></pre>
                      </div>
                      <div className="prov-meta">
                        <span className="meta-item">
                          <strong>Query Hash:</strong> <code>{item.source.query_hash.substring(0, 16)}...</code>
                          <CopyButton text={item.source.query_hash} label="Copy Hash" className="copy-btn-sm" />
                        </span>
                        <span className="meta-item">
                          <strong>Execution Time:</strong> {item.source.execution_metadata.execution_time_ms} ms
                        </span>
                        <span className="meta-item">
                          <strong>Timestamp:</strong> {item.source.timestamp}
                        </span>
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
                      {item.calculation.input_evidence_ids && item.calculation.input_evidence_ids.length > 0 && (
                        <div className="calc-parents">
                          <strong>Parent Evidence IDs:</strong>{' '}
                          <span className="ev-tags-group">
                            {item.calculation.input_evidence_ids.map((pId) => (
                              <button
                                key={pId}
                                type="button"
                                className={`ev-tag-btn ${selectedEvidenceId === pId ? 'active' : ''}`}
                                onClick={() => onSelectEvidence && onSelectEvidence(pId)}
                                title={`Inspect parent evidence item ${pId}`}
                                aria-label={`Jump to parent evidence item ${pId}`}
                              >
                                {pId}
                              </button>
                            ))}
                          </span>
                        </div>
                      )}
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
              ))
            )}
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
                  <div className="sql-header">
                    <span className="trace-sql-label">Executed Query:</span>
                    <CopyButton text={tc.arguments.sql} label="Copy SQL" className="copy-btn-sm" />
                  </div>
                  <pre className="sql-block"><code>{tc.arguments.sql}</code></pre>
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
