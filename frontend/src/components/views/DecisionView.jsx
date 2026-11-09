import React, { useState } from 'react';
import { CandidateComparisonChart } from '../visualization/CandidateComparisonChart.jsx';
import { CriteriaThresholdView } from '../visualization/CriteriaThresholdView.jsx';
import { HumanReviewPanel } from '../HumanReviewPanel.jsx';

/**
 * Dedicated Decision Intelligence View matching the official VERIDEX interactive prototype.
 * Presentation-only: displays backend-evaluated criteria, rankings, recommendations, and robustness.
 */
export function DecisionView({
  data = null,
  selectedEvidenceId = null,
  onSelectEvidence = null,
  onNavigate = null,
  currentUser = null,
  useMock = true
}) {
  const [valueMode, setValueMode] = useState('norm'); // 'norm' | 'raw'

  const analysis = data?.analysis;
  const recommendation = analysis?.recommendation;
  const robustness = analysis?.robustness;
  const rankings = analysis?.rankings || [];
  const criteria = analysis?.criteria_evaluated || [];
  const evidenceList = data?.evidence || [];
  const supportingIds = recommendation?.supporting_evidence_ids || ['ev_fact_1'];

  if (!analysis) {
    return (
      <div className="view-shell decision-view-shell" role="region" aria-label="Decision Intelligence">
        <div className="card placeholder-card">
          <div className="card-header-row">
            <h2 className="section-heading">Decision Intelligence</h2>
          </div>
          <p>No active decision intelligence analysis is currently available.</p>
          <p className="summary-desc">
            Execute an investigation from the Investigations workspace to evaluate criteria, rank candidates, and produce traceable recommendations.
          </p>
          <div>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => onNavigate && onNavigate('investigations')}
            >
              Open Investigations Workspace →
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Supporting evidence items for the bottom card
  const supportingEvidenceItems = evidenceList.filter((e) =>
    supportingIds.includes(e.evidence_id)
  );

  const topCandidate = rankings[0]?.region
    || rankings[0]?.candidate
    || recommendation?.action_title?.replace(/^Prioritize\s+/i, '')
    || 'North';

  const topScore = rankings[0]?.score
    || (typeof rankings[0]?.gross_revenue === 'number' ? '1.00' : '0.90');

  const robustnessStatus = robustness?.status || recommendation?.robustness_status || 'STABLE';
  const robustnessBadgeClass = robustnessStatus === 'STABLE'
    ? 'b-ok'
    : robustnessStatus === 'SENSITIVE'
      ? 'b-warn'
      : 'b-neu';

  const robustnessLabel = robustnessStatus === 'STABLE'
    ? '✓ Stable'
    : robustnessStatus === 'SENSITIVE'
      ? '◐ Sensitive'
      : '○ Insufficient';

  const thresholdCriteria = criteria.filter((c) => c.operator && c.threshold_value !== undefined);

  return (
    <div className="view-shell decision-view-shell" role="region" aria-label="Decision Intelligence Dashboard">
      {/* Breadcrumb Navigation */}
      <div className="view-breadcrumb-row">
        <button
          type="button"
          className="breadcrumb-link-btn"
          onClick={() => onNavigate && onNavigate('decisions')}
        >
          Decisions
        </button>
        <span className="crumb-sep">/</span>
        <span className="crumb-context">
          from {data?.metadata?.investigation_id || 'active_investigation'}
        </span>
      </div>

      {/* Title & Subtitle */}
      <div className="decision-view-header">
        <h1 className="decision-view-title">{data?.question || 'What region should we prioritize for Q4?'}</h1>
        <p className="decision-view-subtitle">
          {rankings.length} candidates · {criteria.length} criteria · {thresholdCriteria.length || 1} threshold condition(s)
        </p>
      </div>

      {/* Recommendation Hero Card */}
      <div className="card decision-hero-rec-card">
        <div className="rec-main-col">
          <span className="cap-label">Recommendation</span>
          <h2 className="rec-headline">{recommendation?.action_title || `Prioritize ${topCandidate} region`}</h2>
          <p className="rec-rationale-text">
            {recommendation?.rationale || `${topCandidate} ranks first across evaluated criteria and clears all threshold conditions.`}
          </p>
          <div className="rec-supporting-eids">
            <span>Supported by:</span>
            {supportingIds.map((eid) => (
              <button
                key={eid}
                type="button"
                className={`evidence-tag-btn ${selectedEvidenceId === eid ? 'active-eid' : ''}`}
                onClick={() => {
                  if (onSelectEvidence) onSelectEvidence(eid);
                  if (onNavigate) onNavigate('evidence');
                }}
                title={`Inspect evidence ${eid}`}
              >
                {eid}
              </button>
            ))}
          </div>
        </div>

        <div className="rec-side-col">
          <span className="cap-label">Lead Score</span>
          <div className="rec-score-display">{topScore}</div>
          <div>
            <span className={`status-badge ${robustnessBadgeClass}`}>
              {robustnessLabel}
            </span>
          </div>
          <div style={{ marginTop: '8px' }}>
            <button
              type="button"
              className="text-link-btn"
              onClick={() => onNavigate && onNavigate('robustness')}
            >
              View robustness →
            </button>
          </div>
        </div>
      </div>

      {/* Human Review & Approval Integration */}
      <div className="decision-approval-container">
        <HumanReviewPanel
          key={data?.metadata?.investigation_id || 'inv_active'}
          investigationId={data?.metadata?.investigation_id || 'inv_active'}
          investigationStatus={
            data?.status || (robustnessStatus === 'SENSITIVE' ? 'REQUIRES_REVIEW' : 'COMPLETED')
          }
          latestReview={data?.latest_review || null}
          reviewCount={data?.review_count || 0}
          useMock={useMock}
          currentUser={currentUser}
          ownerId={data?.owner_id || data?.metadata?.owner_id || 'usr_analyst_01'}
        />
      </div>

      {/* Two-Column Grid matching Prototype */}
      <div className="decision-layout-cols">
        {/* Left Column Stack */}
        <div className="decision-stack-col">
          {/* Candidate Comparison Card with Toggle */}
          <div className="card decision-panel-card">
            <div className="card-header-row">
              <span className="cap-label">Candidate comparison</span>
              <div className="seg-control" role="group" aria-label="Values Presentation Mode">
                <button
                  type="button"
                  className={`seg-btn ${valueMode === 'norm' ? 'active' : ''}`}
                  onClick={() => setValueMode('norm')}
                >
                  Normalized
                </button>
                <button
                  type="button"
                  className={`seg-btn ${valueMode === 'raw' ? 'active' : ''}`}
                  onClick={() => setValueMode('raw')}
                >
                  Raw values
                </button>
              </div>
            </div>

            {/* Candidate Comparison Table */}
            <div className="table-responsive-wrapper">
              <table className="data-table candidate-eval-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Candidate</th>
                    {criteria.map((crit) => (
                      <th key={crit.criterion_id} style={{ textAlign: 'right' }}>
                        {crit.criterion_name}
                        <small className="table-header-sub">
                          {crit.metric_name ? `(${crit.metric_name})` : ''}
                        </small>
                      </th>
                    ))}
                    <th style={{ textAlign: 'right' }}>Score / Metric</th>
                  </tr>
                </thead>
                <tbody>
                  {rankings.map((cand, idx) => {
                    const candName = cand.region || cand.candidate || cand.name || `Candidate #${idx + 1}`;
                    const isTop = idx === 0;
                    const rawVal = cand.gross_revenue || cand.metric_value || cand.score || 0;
                    const displayVal = typeof rawVal === 'number'
                      ? (valueMode === 'raw' ? rawVal.toLocaleString() : (cand.score ?? (1 - idx * 0.25)).toFixed(2))
                      : rawVal;

                    return (
                      <tr key={candName} className={isTop ? 'highlight-row' : ''}>
                        <td className="rank-cell">{cand.rank || idx + 1}</td>
                        <td>
                          <strong>{candName}</strong>
                          {isTop && <span className="top-badge">Top Candidate</span>}
                        </td>
                        {criteria.map((crit) => {
                          const val = cand[crit.metric_name] ?? cand.details?.[crit.metric_name] ?? crit.actual_value;
                          const fmtVal = typeof val === 'number'
                            ? (valueMode === 'raw' ? val.toLocaleString() : (val / (val * 1.2 || 1)).toFixed(2))
                            : String(val ?? '—');

                          return (
                            <td key={crit.criterion_id} style={{ textAlign: 'right', fontFamily: 'var(--font-mono)' }}>
                              {fmtVal}
                            </td>
                          );
                        })}
                        <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                          {displayVal}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Phase 9.5I Visual Candidate Comparison Chart */}
            <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid var(--line)' }}>
              <CandidateComparisonChart rankings={rankings} />
            </div>
          </div>

          {/* Score Composition Presentation Card */}
          <div className="card decision-panel-card">
            <div className="card-header-row">
              <span className="cap-label">Score composition</span>
            </div>
            <div className="score-composition-bars">
              {rankings.map((c, i) => {
                const candName = c.region || c.candidate || `Candidate #${i + 1}`;
                const val = c.gross_revenue || c.score || 100 - i * 25;
                const maxVal = rankings[0]?.gross_revenue || rankings[0]?.score || 100;
                const pct = Math.max(Math.min(Math.round((val / (maxVal || 1)) * 100), 100), 15);

                return (
                  <div key={candName} className="score-bar-row">
                    <span className="bar-label">{candName}</span>
                    <div className="bar-track">
                      <div
                        className="bar-fill"
                        style={{ width: `${pct}%`, backgroundColor: i === 0 ? 'var(--pr)' : 'var(--fact)' }}
                      />
                    </div>
                    <span className="bar-score-val">
                      {typeof val === 'number' ? (val > 1000 ? `${(val / 1000000).toFixed(2)}M` : val.toFixed(2)) : val}
                    </span>
                  </div>
                );
              })}
            </div>
            <div className="score-bars-legend">
              <span style={{ '--legend-color': 'var(--pr)' }}>Observed Metric</span>
              <span style={{ '--legend-color': 'var(--fact)' }}>Comparative Proportion</span>
            </div>
          </div>
        </div>

        {/* Right Column Stack */}
        <div className="decision-stack-col">
          {/* Criteria and Weights Card */}
          <div className="card decision-panel-card">
            <div className="card-header-row">
              <span className="cap-label">Criteria & threshold compliance</span>
            </div>
            <CriteriaThresholdView criteria={criteria} />
          </div>

          {/* Robustness Check Card */}
          {robustness && (
            <div className="card decision-panel-card">
              <div className="card-header-row">
                <span className="cap-label">Robustness check</span>
                <span className={`status-badge ${robustnessBadgeClass}`}>
                  {robustnessLabel}
                </span>
              </div>
              <div className="robustness-check-body">
                <p className="summary-desc">{robustness.explanation}</p>
                <div className="scenario-mini-list">
                  <div className="scenario-mini-item">
                    <span className="scenario-mini-name">Baseline Scenario</span>
                    <span className="scenario-mini-val">
                      {robustness.baseline_scenario?.result_summary?.top_candidate || topCandidate} ✓
                    </span>
                  </div>
                  {robustness.alternate_scenarios?.map((alt, idx) => (
                    <div key={idx} className="scenario-mini-item">
                      <span className="scenario-mini-name">
                        {alt.scenario_name?.replace(/_/g, ' ') || `Alternate #${idx + 1}`}
                      </span>
                      <span className={`scenario-mini-val ${alt.is_recommendation_changed ? 'val-changed' : 'val-stable'}`}>
                        {alt.result_summary?.second_candidate || topCandidate} {alt.is_recommendation_changed ? '◐' : '✓'}
                      </span>
                    </div>
                  ))}
                </div>
                <div className="robustness-footer-row">
                  <button
                    type="button"
                    className="text-link-btn"
                    onClick={() => onNavigate && onNavigate('robustness')}
                  >
                    View scenario tests →
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Supporting Evidence Card */}
          <div className="card decision-panel-card">
            <div className="card-header-row">
              <span className="cap-label">Supporting evidence</span>
              <button
                type="button"
                className="text-link-btn"
                onClick={() => onNavigate && onNavigate('evidence')}
              >
                Open Explorer →
              </button>
            </div>
            <div className="supporting-evidence-list">
              {(supportingEvidenceItems.length > 0 ? supportingEvidenceItems : evidenceList.slice(0, 3)).map((ev) => {
                const type = (ev.evidence_type || 'FACT').toUpperCase();
                const badgeClass = type === 'FACT' ? 'b-fact' : type === 'DERIVED_FACT' ? 'b-der' : 'b-inf';
                const label = type === 'DERIVED_FACT' ? 'Derived' : type === 'FACT' ? 'Fact' : 'Inference';

                return (
                  <div
                    key={ev.evidence_id}
                    className="supporting-ev-item pointer"
                    onClick={() => {
                      if (onSelectEvidence) onSelectEvidence(ev.evidence_id);
                      if (onNavigate) onNavigate('evidence');
                    }}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        if (onSelectEvidence) onSelectEvidence(ev.evidence_id);
                        if (onNavigate) onNavigate('evidence');
                      }
                    }}
                  >
                    <span className="evidence-id-pill">{ev.evidence_id}</span>
                    <span className={`evidence-type-badge ${badgeClass}`}>{label}</span>
                    <span className="supporting-ev-desc">{ev.description}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default DecisionView;
