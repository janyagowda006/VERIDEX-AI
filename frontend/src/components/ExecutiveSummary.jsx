import React, { useState } from 'react';
import { exportInvestigationReport } from '../api/client.js';

/**
 * Compact Executive Summary displaying high-level decision intelligence KPIs and audit report export.
 * Uses strictly existing response fields: claims, evidence, criteria, rankings, robustness.
 */
export function ExecutiveSummary({ data, onSelectEvidence, useMock = false }) {
  const [exportLoading, setExportLoading] = useState(false);
  const [exportError, setExportError] = useState(null);

  if (!data) return null;

  const { claims = [], evidence = [], analysis, metadata = {} } = data;
  const investigationId = metadata.investigation_id || data.investigation_id || "inv_mock_123456";
  const robustnessStatus = analysis?.robustness?.status || metadata.robustness_status || 'STABLE';
  const rankings = analysis?.rankings || [];
  const criteria = analysis?.criteria_evaluated || [];
  const criteriaPassed = criteria.filter((c) => c.is_met).length;

  const factCount = claims.filter((c) => (c.evidence_type || '').toUpperCase() === 'FACT').length;
  const derivedCount = claims.filter((c) => (c.evidence_type || '').toUpperCase() === 'DERIVED_FACT').length;
  const inferenceCount = claims.filter((c) => (c.evidence_type || '').toUpperCase() === 'INFERENCE').length;

  const handleExport = async (format) => {
    setExportLoading(true);
    setExportError(null);

    try {
      const payload = await exportInvestigationReport(investigationId, format, useMock);

      let blob;
      let extension;
      if (format === 'markdown') {
        blob = new Blob([typeof payload === 'string' ? payload : String(payload)], { type: 'text/markdown;charset=utf-8' });
        extension = 'md';
      } else {
        const jsonStr = typeof payload === 'string' ? payload : JSON.stringify(payload, null, 2);
        blob = new Blob([jsonStr], { type: 'application/json;charset=utf-8' });
        extension = 'json';
      }

      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${investigationId}_audit_report.${extension}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err.message || "Failed to export audit report.");
    } finally {
      setExportLoading(false);
    }
  };

  return (
    <div className="card executive-summary-card" aria-label="Executive Decision Summary">
      <div className="summary-header">
        <div>
          <h2 className="summary-title">Executive Summary & Provenance KPIs</h2>
          <p className="summary-subtitle">Traceable investigation summary</p>
        </div>

        <div className="export-controls-group">
          <span className="export-label">Export Report:</span>
          <button
            type="button"
            className="btn-export-report"
            onClick={() => handleExport('json')}
            disabled={exportLoading}
            aria-label="Export audit report in JSON format"
          >
            📥 JSON
          </button>
          <button
            type="button"
            className="btn-export-report"
            onClick={() => handleExport('markdown')}
            disabled={exportLoading}
            aria-label="Export audit report in Markdown format"
          >
            📄 Markdown
          </button>
        </div>
      </div>

      {exportError && (
        <div className="export-error-notice" role="alert">
          <span>⚠️ {exportError}</span>
        </div>
      )}

      <div className="kpi-grid">
        {/* KPI 1: Robustness Status */}
        <div className={`kpi-card kpi-robustness status-${robustnessStatus.toLowerCase()}`}>
          <div className="kpi-label">Decision Robustness</div>
          <div className="kpi-value">
            <span className="kpi-status-indicator" aria-hidden="true"></span>
            {robustnessStatus}
          </div>
          <div className="kpi-subtext">
            {robustnessStatus === 'STABLE'
              ? 'Invariant to alternate scenarios'
              : robustnessStatus === 'SENSITIVE'
              ? 'Vulnerable to assumptions'
              : 'Requires additional evidence'}
          </div>
        </div>

        {/* KPI 2: Evidence Items */}
        <button
          type="button"
          className="kpi-card kpi-card-button"
          onClick={() => {
            if (evidence.length > 0 && onSelectEvidence) {
              onSelectEvidence(evidence[0].evidence_id);
            }
          }}
          disabled={evidence.length === 0}
          aria-label={`Evidence items: ${evidence.length}. Select to inspect first evidence item in provenance panel`}
        >
          <div className="kpi-label">Evidence Items</div>
          <div className="kpi-value">{evidence.length}</div>
          <div className="kpi-subtext">
            {metadata.total_tool_calls ? `${metadata.total_tool_calls} query trace(s)` : 'Investigation audit trail'}
          </div>
        </button>

        {/* KPI 3: Categorized Claims */}
        <div className="kpi-card">
          <div className="kpi-label">Synthesized Claims</div>
          <div className="kpi-value">{claims.length}</div>
          <div className="kpi-subtext">
            {factCount} Facts · {derivedCount} Derived · {inferenceCount} Inf.
          </div>
        </div>

        {/* KPI 4: Criteria Satisfied */}
        {criteria.length > 0 && (
          <div className="kpi-card">
            <div className="kpi-label">Criteria Satisfied</div>
            <div className="kpi-value">
              {criteriaPassed} / {criteria.length}
            </div>
            <div className="kpi-subtext">
              {criteriaPassed === criteria.length ? '100% threshold compliance' : `${criteria.length - criteriaPassed} unmet criteria`}
            </div>
          </div>
        )}

        {/* KPI 5: Candidates Evaluated */}
        {rankings.length > 0 && (
          <div className="kpi-card">
            <div className="kpi-label">Candidates Evaluated</div>
            <div className="kpi-value">{rankings.length}</div>
            <div className="kpi-subtext">Ranked across observed metrics</div>
          </div>
        )}
      </div>
    </div>
  );
}
