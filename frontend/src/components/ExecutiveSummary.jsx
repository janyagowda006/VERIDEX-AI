import React from 'react';

/**
 * Compact Executive Summary displaying high-level decision intelligence KPIs.
 * Uses strictly existing response fields: claims, evidence, criteria, rankings, robustness.
 */
export function ExecutiveSummary({ data, onSelectEvidence }) {
  if (!data) return null;

  const { claims = [], evidence = [], analysis, metadata = {} } = data;
  const robustnessStatus = analysis?.robustness?.status || metadata.robustness_status || 'STABLE';
  const rankings = analysis?.rankings || [];
  const criteria = analysis?.criteria_evaluated || [];
  const criteriaPassed = criteria.filter((c) => c.is_met).length;

  const factCount = claims.filter((c) => (c.evidence_type || '').toUpperCase() === 'FACT').length;
  const derivedCount = claims.filter((c) => (c.evidence_type || '').toUpperCase() === 'DERIVED_FACT').length;
  const inferenceCount = claims.filter((c) => (c.evidence_type || '').toUpperCase() === 'INFERENCE').length;

  return (
    <div className="card executive-summary-card" aria-label="Executive Decision Summary">
      <div className="summary-header">
        <div>
          <h2 className="summary-title">Executive Summary & Provenance KPIs</h2>
          <p className="summary-subtitle">Traceable investigation summary</p>
        </div>
      </div>

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

        {/* KPI 2: Evidence Items (Semantic & Keyboard Accessible Button) */}
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
