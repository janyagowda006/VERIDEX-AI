import React, { useState } from 'react';
import { exportInvestigationReport } from '../api/client.js';

/**
 * Compact Executive Summary displaying high-level decision intelligence KPIs and audit report export.
 * Uses strictly existing response fields: claims, evidence, criteria, rankings, robustness.
 */
export function ExecutiveSummary({ data, onSelectEvidence, useMock = false, currentUser = null }) {
  const [exportLoading, setExportLoading] = useState(false);
  const [exportError, setExportError] = useState(null);

  if (!data) return null;

  const userRole = currentUser?.role || 'ANALYST';
  const canExport = ['REVIEWER', 'AUDITOR', 'ADMIN'].includes(userRole);

  const { claims = [], evidence = [], analysis, metadata = {}, latest_review = null, status = 'COMPLETED' } = data;
  const investigationId = metadata.investigation_id || data.investigation_id || "inv_mock_123456";
  const recommendation = analysis?.recommendation || null;
  const robustnessStatus = analysis?.robustness?.status || metadata.robustness_status || 'STABLE';
  const criteria = analysis?.criteria_evaluated || [];
  const criteriaPassed = criteria.filter((c) => c.is_met).length;

  const factCount = claims.filter((c) => (c.evidence_type || '').toUpperCase() === 'FACT').length;
  const derivedCount = claims.filter((c) => (c.evidence_type || '').toUpperCase() === 'DERIVED_FACT').length;
  const inferenceCount = claims.filter((c) => (c.evidence_type || '').toUpperCase() === 'INFERENCE').length;

  const handleExport = async (format) => {
    if (!canExport) return;
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
          <h2 className="summary-title">Executive Decision Dashboard</h2>
          <p className="summary-subtitle">Traceable business intelligence summary & provenance metrics</p>
        </div>

        <div className="export-controls-group">
          <span className="export-label">Export Audit Report:</span>
          <button
            type="button"
            className="btn-export-report"
            onClick={() => handleExport('json')}
            disabled={exportLoading || !canExport}
            title={!canExport ? "Export requires REVIEWER, AUDITOR, or ADMIN role" : "Export JSON Report"}
            aria-label="Export audit report in JSON format"
          >
            📥 JSON
          </button>
          <button
            type="button"
            className="btn-export-report"
            onClick={() => handleExport('markdown')}
            disabled={exportLoading || !canExport}
            title={!canExport ? "Export requires REVIEWER, AUDITOR, or ADMIN role" : "Export Markdown Report"}
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

      {/* Hero Recommendation Summary Banner */}
      {recommendation && (
        <div className="dash-hero-banner">
          <div className="hero-top-row">
            <span className="hero-tag">🎯 Key Executive Action</span>
            <span className={`robustness-badge status-${robustnessStatus.toLowerCase()}`}>
              Robustness: {robustnessStatus}
            </span>
          </div>
          <h3 className="hero-action-title">{recommendation.action_title}</h3>
          <p className="hero-rationale">{recommendation.rationale}</p>
        </div>
      )}

      {/* Executive KPI Grid */}
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

        {/* KPI 2: Verified Evidence Items */}
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

        {/* KPI 4: Criteria Compliance */}
        {criteria.length > 0 && (
          <div className="kpi-card">
            <div className="kpi-label">Criteria Compliance</div>
            <div className="kpi-value">
              {criteriaPassed} / {criteria.length}
            </div>
            <div className="kpi-subtext">
              {criteriaPassed === criteria.length ? '100% threshold satisfied' : `${criteria.length - criteriaPassed} unmet criteria`}
            </div>
          </div>
        )}

        {/* KPI 5: Human Review Decision Status */}
        <div className="kpi-card">
          <div className="kpi-label">Human Review Status</div>
          <div className="kpi-value" style={{ fontSize: '1.1rem' }}>
            {latest_review ? (
              <span className={`audit-badge badge-${(latest_review.review_status || 'PENDING').toLowerCase()}`}>
                {latest_review.review_status}
              </span>
            ) : status === 'REQUIRES_REVIEW' ? (
              <span className="requires-review-badge">REQUIRES REVIEW</span>
            ) : (
              <span className="review-pending-tag">PENDING REVIEW</span>
            )}
          </div>
          <div className="kpi-subtext">
            {latest_review ? `Reviewed by ${latest_review.reviewer_id}` : 'HITL verification layer'}
          </div>
        </div>
      </div>
    </div>
  );
}
