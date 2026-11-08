import React, { useState } from 'react';
import { RobustnessScenarioChart } from '../visualization/RobustnessScenarioChart.jsx';
import { HumanReviewPanel } from '../HumanReviewPanel.jsx';
import { reassessInvestigation } from '../../api/client.js';

/**
 * Dedicated Robustness Analysis View matching the official VERIDEX interactive prototype.
 * Evaluates whether recommendations survive alternate scenario perturbation tests.
 * Displays backend-calculated sensitivity, scenario results, and interactive re-assessment.
 */
export function RobustnessView({
  data = null,
  onNavigate = null,
  currentUser = null,
  useMock = false,
  onRobustnessUpdated = null
}) {
  const [shiftPct, setShiftPct] = useState(10.0);
  const [reassessing, setReassessing] = useState(false);
  const [reassessError, setReassessError] = useState(null);
  const [reassessResult, setReassessResult] = useState(null);

  const activeData = reassessResult ? { ...data, analysis: { ...(data?.analysis || {}), robustness: reassessResult.robustness } } : data;
  const analysis = activeData?.analysis;
  const robustness = activeData?.analysis?.robustness;
  const recommendation = analysis?.recommendation;
  const rankings = analysis?.rankings || [];
  const invId = activeData?.metadata?.investigation_id || activeData?.investigation_id || null;

  const handleReassess = async () => {
    if (!invId) {
      setReassessError("Cannot reassess robustness: missing investigation ID.");
      return;
    }

    setReassessing(true);
    setReassessError(null);

    try {
      const result = await reassessInvestigation(invId, shiftPct, useMock);
      setReassessResult(result);
      if (onRobustnessUpdated) {
        onRobustnessUpdated(result);
      }
    } catch (err) {
      setReassessError(err.detail || err.message || "Failed to execute robustness re-assessment.");
    } finally {
      setReassessing(false);
    }
  };

  if (!robustness) {
    return (
      <div className="view-shell robustness-view-shell" role="region" aria-label="Robustness Analysis">
        <div className="card placeholder-card">
          <div className="card-header-row">
            <h2 className="section-heading">Robustness Analysis</h2>
          </div>
          <p>No robustness or scenario perturbation assessment is available for the current investigation.</p>
          <p className="summary-desc">
            Execute a decision intelligence investigation from the workspace to evaluate parameter perturbations, alternate scenario weighting, and finding stability.
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
    || 'Leading Candidate';

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
          <h1 className="robustness-view-title">Robustness & Sensitivity Analysis</h1>
          <p className="robustness-view-subtitle">
            Deterministic stress-testing: does the recommendation survive alternate scenario perturbations?
          </p>
        </div>
      </div>

      {/* Interactive Re-assessment Control Bar */}
      {invId && (
        <div className="card pad-card" style={{ marginBottom: '1.25rem' }}>
          <div className="card-header-row">
            <div>
              <span className="cap-label">Dynamic Stress Testing</span>
              <h3 style={{ margin: '0.2rem 0', fontSize: '1.05rem' }}>Scenario Perturbation Threshold</h3>
              <p className="summary-desc" style={{ margin: 0 }}>
                Re-evaluate candidate rankings under synthetic parameter shifts (POST /api/investigations/{'{id}'}/reassess).
              </p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
              <div className="seg-control" role="group" aria-label="Perturbation Shift Percentage">
                {[5.0, 10.0, 15.0, 20.0, 25.0].map((pct) => (
                  <button
                    key={pct}
                    type="button"
                    className={`seg-btn ${shiftPct === pct ? 'active' : ''}`}
                    onClick={() => setShiftPct(pct)}
                    disabled={reassessing}
                  >
                    ±{pct}%
                  </button>
                ))}
              </div>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={handleReassess}
                disabled={reassessing}
              >
                {reassessing ? (
                  <span className="btn-loading-content">
                    <span className="btn-spinner" aria-hidden="true"></span>
                    <span>Reassessing...</span>
                  </span>
                ) : (
                  <span>Re-evaluate Robustness</span>
                )}
              </button>
            </div>
          </div>
          {reassessError && (
            <div className="review-message message-error" style={{ marginTop: '0.75rem' }}>
              <span className="msg-icon" aria-hidden="true">⚠️</span>
              <span>{reassessError}</span>
            </div>
          )}
          {reassessResult && (
            <div className="review-message message-success" style={{ marginTop: '0.75rem' }}>
              <span className="msg-icon" aria-hidden="true">✓</span>
              <span>
                Robustness re-assessed at ±{shiftPct}% perturbation: status is <strong>{reassessResult.robustness?.status}</strong>.
              </span>
            </div>
          )}
        </div>
      )}

      {/* Robustness Status Hero Card */}
      <div className={`card robustness-hero-status-card status-border-${status.toLowerCase()}`}>
        <div className="status-hero-main">
          <span className="cap-label">Deterministic Robustness Check</span>
          <div className={`status-hero-label text-${status.toLowerCase()}`}>
            {statusLabel}
          </div>
          <p className="status-hero-explanation">{robustness.explanation}</p>
          {baseline?.result_summary?.lead_margin_percent !== undefined && (
            <div className="status-hero-metric-note">
              Baseline Lead Margin: <strong>{baseline.result_summary.lead_margin_percent}%</strong> · Required Stability Threshold: <strong>5.0%</strong>
            </div>
          )}
        </div>

        {/* Baseline vs Scenario Comparison Box */}
        <div className="status-comparison-box">
          <div className="comparison-box-item">
            <span className="cap-label">
              <span className="badge badge-platform" style={{ fontSize: '0.65rem', marginRight: '4px' }}>OBSERVED</span>
              Baseline
            </span>
            <strong>{topCandidate} #1</strong>
          </div>
          <span className="comparison-arrow" aria-hidden="true">→</span>
          <div className={`comparison-box-item ${status === 'SENSITIVE' ? 'item-sensitive' : ''}`}>
            <span className="cap-label">
              <span className="badge badge-platform" style={{ fontSize: '0.65rem', marginRight: '4px' }}>SIMULATED</span>
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
          key={invId || 'inv_active'}
          investigationId={invId || 'inv_active'}
          investigationStatus={
            activeData?.status || (status === 'SENSITIVE' ? 'REQUIRES_REVIEW' : 'COMPLETED')
          }
          latestReview={activeData?.latest_review || null}
          reviewCount={activeData?.review_count || 0}
          useMock={useMock}
          currentUser={currentUser}
          ownerId={activeData?.owner_id || activeData?.metadata?.owner_id || 'usr_analyst_01'}
        />
      </div>

      {/* Scenario Section Title */}
      <div className="section-title-row" style={{ marginTop: '1.5rem', marginBottom: '0.75rem' }}>
        <span className="cap-label">
          {alternates.length ? `${alternates.length} Alternate Scenario${alternates.length > 1 ? 's' : ''} Evaluated` : 'Scenarios'}
        </span>
        <span className={`status-badge ${statusBadgeClass}`}>{statusLabel}</span>
      </div>

      {/* Scenario Chart */}
      <div style={{ marginBottom: '1.5rem' }}>
        <RobustnessScenarioChart
          baselineScenario={baseline}
          alternateScenarios={alternates}
          robustnessStatus={status}
        />
      </div>

      {/* Scenario Detail Cards */}
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
                  <span className="cap-label">
                    <span className="badge badge-platform" style={{ fontSize: '0.65rem', marginRight: '6px' }}>SIMULATED</span>
                    Scenario #{idx + 1}
                  </span>
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
