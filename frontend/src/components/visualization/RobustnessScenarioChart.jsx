import React from 'react';

function formatScenarioTitle(name) {
  if (!name) return 'Scenario';
  return name
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

/**
 * Visualizes baseline vs alternate scenario perturbation tests from RobustnessEngine.
 * Displays sensitivity tipping points and recommendation stability.
 *
 * @param {Object} baselineScenario - Baseline scenario from robustness.baseline_scenario.
 * @param {Array<Object>} alternateScenarios - List of scenarios from robustness.alternate_scenarios.
 * @param {string} robustnessStatus - Classification status: STABLE, SENSITIVE, INSUFFICIENT_EVIDENCE.
 */
export function RobustnessScenarioChart({
  baselineScenario = null,
  alternateScenarios = [],
  robustnessStatus = 'STABLE'
}) {
  const normStatus = (robustnessStatus || 'STABLE').toUpperCase();

  return (
    <div className="viz-card robustness-chart-card" role="region" aria-label="Robustness Scenario Sensitivity Chart">
      <div className="viz-header">
        <div className="viz-title-group">
          <span className="viz-icon" aria-hidden="true">🛡️</span>
          <h4 className="viz-title">Scenario Sensitivity & Perturbation Timeline</h4>
        </div>
        <span className={`robustness-status-pill status-${normStatus.toLowerCase()}`}>
          Status: {normStatus}
        </span>
      </div>

      <div className="scenario-timeline-container">
        {/* Baseline Scenario Node */}
        {baselineScenario && (
          <div className="timeline-node node-baseline">
            <div className="node-badge-col">
              <span className="node-pill pill-baseline">Baseline</span>
              <div className="node-line-connector" aria-hidden="true" />
            </div>
            <div className="node-content-box">
              <div className="node-title-row">
                <strong>{formatScenarioTitle(baselineScenario.scenario_name)}</strong>
                <span className="stability-tag tag-stable">Baseline Reference</span>
              </div>
              <div className="node-details">
                {baselineScenario.result_summary?.top_candidate && (
                  <span>Top Candidate: <strong>{baselineScenario.result_summary.top_candidate}</strong></span>
                )}
                {baselineScenario.result_summary?.total_rows !== undefined && (
                  <span>Total Rows Evaluated: {baselineScenario.result_summary.total_rows}</span>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Alternate Perturbation Scenarios */}
        {alternateScenarios.map((sc, idx) => {
          const isChanged = Boolean(sc.is_recommendation_changed);
          return (
            <div key={idx} className={`timeline-node node-alternate ${isChanged ? 'node-changed' : 'node-unchanged'}`}>
              <div className="node-badge-col">
                <span className={`node-pill ${isChanged ? 'pill-changed' : 'pill-unchanged'}`}>
                  Alt #{idx + 1}
                </span>
                {idx < alternateScenarios.length - 1 && (
                  <div className="node-line-connector" aria-hidden="true" />
                )}
              </div>
              <div className="node-content-box">
                <div className="node-title-row">
                  <strong>{formatScenarioTitle(sc.scenario_name)}</strong>
                  <span className={`stability-tag ${isChanged ? 'tag-changed' : 'tag-stable'}`}>
                    {isChanged ? '⚠ Recommendation Shift' : '✓ Recommendation Stable'}
                  </span>
                </div>

                <div className="node-details">
                  {sc.assumptions?.lead_margin_threshold && (
                    <span>Threshold: {sc.assumptions.lead_margin_threshold}</span>
                  )}
                  {sc.result_summary?.lead_margin_percent !== undefined && (
                    <span>Observed Margin: <strong>{sc.result_summary.lead_margin_percent}%</strong></span>
                  )}
                  {sc.result_summary?.second_candidate && (
                    <span>Challenger: <strong>{sc.result_summary.second_candidate}</strong></span>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {alternateScenarios.length === 0 && (
          <p className="no-data-text">No baseline alternate scenario tests recorded.</p>
        )}
      </div>
    </div>
  );
}
