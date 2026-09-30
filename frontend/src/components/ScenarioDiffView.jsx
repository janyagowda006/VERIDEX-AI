import React from 'react';

function formatMetricKey(key) {
  if (!key) return '';
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatMetricValue(val) {
  if (val === null || val === undefined) return '—';
  if (typeof val === 'boolean') return val ? 'True' : 'False';
  if (typeof val === 'object') return JSON.stringify(val);
  return String(val);
}

export function ScenarioDiffView({ reassessResult, baselineRobustness }) {
  if (!reassessResult || !reassessResult.robustness_check) return null;

  const {
    requested_scenario_shift_pct,
    baseline_top_candidate,
    baseline_metric_name,
    robustness_check
  } = reassessResult;

  const reassessedStatus = robustness_check.status || 'STABLE';
  const baselineStatus = baselineRobustness?.status || 'STABLE';

  return (
    <div className="scenario-diff-container">
      <div className="scenario-diff-header">
        <div className="diff-title-group">
          <span className="diff-badge-icon" aria-hidden="true">⚡</span>
          <div>
            <h3>Dynamic Scenario Stress Test Diff (+/-{requested_scenario_shift_pct}%)</h3>
            <p className="diff-subtitle">
              Deterministic perturbation check evaluated on metric <strong>{formatMetricKey(baseline_metric_name) || 'Primary Metric'}</strong>
            </p>
          </div>
        </div>
        <span className={`robustness-badge status-${reassessedStatus.toLowerCase()}`}>
          {reassessedStatus}
        </span>
      </div>

      <p className="diff-explanation">{robustness_check.explanation}</p>

      {/* Side-by-Side Comparison Grid */}
      <div className="diff-grid">
        {/* Left Column: Baseline Scenario */}
        <div className="diff-column column-baseline">
          <div className="column-header">
            <span className="col-tag tag-baseline">BASELINE (Original 10%)</span>
            <span className={`col-status status-${baselineStatus.toLowerCase()}`}>
              {baselineStatus}
            </span>
          </div>
          <div className="diff-body">
            <div className="diff-metric-row">
              <span className="diff-label">Top Candidate:</span>
              <span className="diff-val highlight">{baseline_top_candidate || '—'}</span>
            </div>
            {baselineRobustness?.baseline_scenario && (
              <div className="diff-scenario-detail">
                <span className="sc-name">{formatMetricKey(baselineRobustness.baseline_scenario.scenario_name)}</span>
                {baselineRobustness.baseline_scenario.result_summary && (
                  <div className="sc-chips">
                    {Object.entries(baselineRobustness.baseline_scenario.result_summary).map(([k, v]) => (
                      <span key={k} className="chip">
                        {formatMetricKey(k)}: {formatMetricValue(v)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Re-assessed Scenario */}
        <div className="diff-column column-reassessed">
          <div className="column-header">
            <span className="col-tag tag-reassessed">RE-ASSESSED ({requested_scenario_shift_pct}%)</span>
            <span className={`col-status status-${reassessedStatus.toLowerCase()}`}>
              {reassessedStatus}
            </span>
          </div>
          <div className="diff-body">
            {robustness_check.alternate_scenarios && robustness_check.alternate_scenarios.length > 0 ? (
              robustness_check.alternate_scenarios.map((alt, idx) => (
                <div key={idx} className={`diff-scenario-detail ${alt.is_recommendation_changed ? 'alert-changed' : ''}`}>
                  <div className="sc-title-row">
                    <span className="sc-name">{formatMetricKey(alt.scenario_name)}</span>
                    <span className={`sc-flag ${alt.is_recommendation_changed ? 'flag-changed' : 'flag-unchanged'}`}>
                      {alt.is_recommendation_changed ? 'CHANGED' : 'STABLE'}
                    </span>
                  </div>
                  {alt.result_summary && (
                    <div className="sc-chips">
                      {Object.entries(alt.result_summary).map(([k, v]) => (
                        <span key={k} className="chip">
                          {formatMetricKey(k)}: {formatMetricValue(v)}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))
            ) : (
              <p className="no-scenarios">Single scenario fallback evaluation performed.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
