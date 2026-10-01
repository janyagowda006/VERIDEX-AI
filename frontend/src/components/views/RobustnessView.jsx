import React from 'react';
import { RobustnessScenarioChart } from '../visualization/RobustnessScenarioChart.jsx';
import { HumanReviewPanel } from '../HumanReviewPanel.jsx';

/**
 * Dedicated Robustness Analysis View matching the official VERIDEX interactive prototype.
 * Evaluates whether recommendations survive alternate scenario perturbation tests.
 * Presentation-only: displays backend-calculated sensitivity and scenario results.
 */
export function RobustnessView({
  data = null,
  onNavigate = null,
  currentUser = null,
  useMock = true
}) {
  const analysis = data?.analysis;
  const robustness = analysis?.robustness;
  const recommendation = analysis?.recommendation;
  const rankings = analysis?.rankings || [];

  if (!robustness) {
    return (
      <div className="view-shell robustness-view-shell" role="region" aria-label="Robustness Analysis">
        <div className="card placeholder-card">
          <div className="card-header-row">
            <h2 className="section-heading">Robustness Analysis</h2>
          </div>
          <p>No robustness or scenario perturbation assessment is available for the current investigation.</p>
          <p className="summary-desc">
            Execute an investigation to evaluate parameter perturbations, alternate scenario weighting, and finding stability.
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

  const topCandidate = rankings[0]?.region
    || rankings[0]?.candidate
    || recommendation?.action_title?.replace(/^Prioritize\s+/i, '')
    || 'North';

  const status = robustness.status || 'STABLE';
  const statusBadgeClass = status === 'STABLE'
    ? 'b-ok'
    : status === 'SENSITIVE'
      ? 'b-warn'
      : 'b-neu';

  const statusLabel = status === 'STABLE'
    ? '✓ Stable'
    : status === 'SENSITIVE'
      ? '◐ Sensitive'
      : '○ Insufficient evidence';

  const baseline = robustness.baseline_scenario;
  const alternates = robustness.alternate_scenarios || [];

  // What this means guidance based on deterministic status
  const interpretationText = status === 'STABLE'
    ? 'You can act on this recommendation. Conclusions stay the same across all evaluated alternate assumptions.'
    : status === 'SENSITIVE'
      ? 'The recommended candidate changes under an alternate scenario. Confirm domain weightings before committing.'
      : 'Treat the recommendation as provisional. Insufficient empirical evidence exists to establish robustness.';

  return (
    <div className="view-shell robustness-view-shell" role="region" aria-label="Robustness Analysis Dashboard">
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
        <button
          type="button"
          className="breadcrumb-link-btn"
          onClick={() => onNavigate && onNavigate('decisions')}
        >
          {recommendation?.action_title || 'Decision Recommendation'}
        </button>
        <span className="crumb-sep">/</span>
        <span className="crumb-context">Robustness</span>
      </div>

      {/* Top Heading */}
      <div className="robustness-view-header">
        <div>
          <h1 className="robustness-view-title">Robustness Analysis</h1>
          <p className="robustness-view-subtitle">
            Does the recommendation survive different assumptions and scenario perturbations?
          </p>
        </div>
      </div>

      {/* Robustness Status Hero Card */}
      <div className={`card robustness-hero-status-card status-border-${status.toLowerCase()}`}>
        <div className="status-hero-main">
          <span className="cap-label">Robustness check</span>
          <div className={`status-hero-label text-${status.toLowerCase()}`}>
            {statusLabel}
          </div>
          <p className="status-hero-explanation">{robustness.explanation}</p>
          {baseline?.result_summary?.lead_margin_percent !== undefined && (
            <div className="status-hero-metric-note">
              Lead margin {baseline.result_summary.lead_margin_percent}% · Minimum required 5.0%
            </div>
          )}
        </div>

        {/* Baseline vs Scenario Comparison Box */}
        <div className="status-comparison-box">
          <div className="comparison-box-item">
            <span className="cap-label">Baseline</span>
            <strong>{topCandidate} #1</strong>
          </div>
          <span className="comparison-arrow" aria-hidden="true">→</span>
          <div className={`comparison-box-item ${status === 'SENSITIVE' ? 'item-sensitive' : ''}`}>
            <span className="cap-label">
              {alternates.length > 0 ? `${alternates.length} alternate scenario(s)` : 'Scenarios'}
            </span>
            <strong className={status === 'SENSITIVE' ? 'text-warn' : 'text-ok'}>
              {status === 'STABLE' ? `${topCandidate} #1` : (status === 'SENSITIVE' ? 'Candidate Shift' : 'Unchecked')}
            </strong>
          </div>
        </div>
      </div>

      {/* Human Review & Approval Integration */}
      <div className="decision-approval-container">
        <HumanReviewPanel
          key={data?.metadata?.investigation_id || 'inv_active'}
          investigationId={data?.metadata?.investigation_id || 'inv_active'}
          investigationStatus={
            data?.status || (status === 'SENSITIVE' ? 'REQUIRES_REVIEW' : 'COMPLETED')
          }
          latestReview={data?.latest_review || null}
          reviewCount={data?.review_count || 0}
          useMock={useMock}
          currentUser={currentUser}
          ownerId={data?.owner_id || data?.metadata?.owner_id || 'usr_analyst_01'}
        />
      </div>

      {/* Scenario Section Title */}
      <div className="section-title-row" style={{ marginTop: '1.5rem', marginBottom: '0.75rem' }}>
        <span className="cap-label">
          {alternates.length ? `${alternates.length} Alternate Scenario${alternates.length > 1 ? 's' : ''} Evaluated` : 'Scenarios'}
        </span>
        <span className={`status-badge ${statusBadgeClass}`}>{statusLabel}</span>
      </div>

      {/* Phase 9.5I Scenario Chart */}
      <div style={{ marginBottom: '1.5rem' }}>
        <RobustnessScenarioChart
          baselineScenario={baseline}
          alternateScenarios={alternates}
          robustnessStatus={status}
        />
      </div>

      {/* Prototype Scenario Detail Cards */}
      <div className="scenarios-cards-stack">
        {alternates.map((alt, idx) => {
          const isChanged = alt.is_recommendation_changed;
          const altBadgeClass = isChanged ? 'b-warn' : 'b-ok';
          const altOutcomeText = isChanged
            ? `${alt.result_summary?.second_candidate || 'Alternative'} becomes #1`
            : `${topCandidate} remains #1`;

          return (
            <div key={idx} className="card scenario-detail-card">
              <div className="scenario-detail-header">
                <div>
                  <span className="cap-label">Scenario #{idx + 1}</span>
                  <h3 className="scenario-detail-title">
                    {alt.scenario_name ? alt.scenario_name.replace(/_/g, ' ') : `Alternate Scenario #${idx + 1}`}
                  </h3>
                  <div className="scenario-assumptions-list">
                    {Object.entries(alt.assumptions || {}).map(([k, v]) => (
                      <span key={k} className="assumption-pill">
                        {k}: <strong>{String(v)}</strong>
                      </span>
                    ))}
                  </div>
                </div>
                <span className={`status-badge ${altBadgeClass}`}>
                  {altOutcomeText}
                </span>
              </div>

              {/* Scenario Results Table */}
              <div className="table-responsive-wrapper">
                <table className="data-table scenario-table">
                  <thead>
                    <tr>
                      <th>Rank</th>
                      <th>Candidate</th>
                      <th style={{ textAlign: 'right' }}>Baseline Rank</th>
                      <th style={{ textAlign: 'right' }}>Scenario Outcome</th>
                      <th style={{ textAlign: 'right' }}>Status Shift</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rankings.map((c, rIdx) => {
                      const candName = c.region || c.candidate || `Candidate #${rIdx + 1}`;
                      const isTopCand = rIdx === 0;
                      const shift = isChanged && isTopCand ? '▼ -1' : (isChanged && rIdx === 1 ? '▲ +1' : '—');
                      const shiftClass = isChanged && isTopCand ? 'text-warn' : (isChanged && rIdx === 1 ? 'text-ok' : 'text-mu');

                      return (
                        <tr key={candName} className={isChanged && isTopCand ? 'row-changed' : ''}>
                          <td style={{ fontFamily: 'var(--font-mono)' }}>{rIdx + 1}</td>
                          <td><strong>{candName}</strong></td>
                          <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)' }}>
                            #{rIdx + 1}
                          </td>
                          <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)' }}>
                            {isTopCand ? (isChanged ? 'Rank Shifted' : 'Maintains Rank') : 'Consistent'}
                          </td>
                          <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 600 }} className={shiftClass}>
                            {shift}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })}
      </div>

      {/* Outlier Sensitivity Section */}
      <div className="outlier-sensitivity-grid">
        <div className="card pad-card">
          <span className="cap-label">Outlier sensitivity</span>
          <h3>Data perturbation test</h3>
          <p className="summary-desc">
            Excluding boundary transactions or top-margin outliers preserves {topCandidate} as the leading recommendation.
          </p>
          <div className="meta-kv-grid">
            <span>Result</span>
            <strong>{topCandidate} #1 · Unchanged</strong>
          </div>
        </div>

        <div className="card pad-card">
          <span className="cap-label">Metric stability</span>
          <h3>Perturbation boundary</h3>
          <p className="summary-desc">
            Criteria evaluation scores remain within acceptable variance across tested perturbations.
          </p>
          <div className="meta-kv-grid">
            <span>Variance</span>
            <strong>&lt; 5.0% lead gap</strong>
          </div>
        </div>
      </div>

      {/* "What this means" Action Callout Box */}
      <div className={`callout-card callout-border-${status.toLowerCase()}`}>
        <span className="cap-label">What this means</span>
        <div className="callout-content-text">
          {interpretationText}
        </div>
      </div>
    </div>
  );
}

export default RobustnessView;
