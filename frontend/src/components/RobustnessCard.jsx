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

function ScenarioMetrics({ data, title }) {
  if (!data || Object.keys(data).length === 0) return null;

  return (
    <div className="metric-group">
      <span className="metric-group-title">{title}:</span>
      <div className="metric-chips">
        {Object.entries(data).map(([key, val]) => (
          <div key={key} className="metric-chip">
            <span className="chip-key">{formatMetricKey(key)}:</span>
            <span className="chip-val">{formatMetricValue(val)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function RobustnessCard({ robustness, selectedEvidenceId, onSelectEvidence }) {
  if (!robustness) return null;

  const { status, explanation, baseline_scenario, alternate_scenarios = [], supporting_evidence_ids = [] } = robustness;

  return (
    <div className="card robustness-card">
      <div className="card-header">
        <h2>Deterministic Robustness Check</h2>
        <span className={`robustness-badge status-${status.toLowerCase()}`}>
          {status}
        </span>
      </div>

      <p className="robustness-explanation">{explanation}</p>

      {baseline_scenario && (
        <div className="scenario-box baseline-box">
          <div className="sc-header">
            <strong>Baseline Scenario: {formatMetricKey(baseline_scenario.scenario_name)}</strong>
            <span className="sc-flag flag-baseline">BASELINE</span>
          </div>
          <ScenarioMetrics data={baseline_scenario.assumptions} title="Assumptions" />
          <ScenarioMetrics data={baseline_scenario.result_summary} title="Observed Results" />
        </div>
      )}

      {alternate_scenarios.length > 0 && (
        <div className="alternate-scenarios-section">
          <h4>Alternate Scenario Tests ({alternate_scenarios.length})</h4>
          {alternate_scenarios.map((sc, idx) => (
            <div key={idx} className={`scenario-box alt-box ${sc.is_recommendation_changed ? 'changed' : 'unchanged'}`}>
              <div className="sc-header">
                <strong>Scenario: {formatMetricKey(sc.scenario_name)}</strong>
                <span className={`sc-flag ${sc.is_recommendation_changed ? 'flag-changed' : 'flag-unchanged'}`}>
                  {sc.is_recommendation_changed ? 'RECOMMENDATION CHANGED' : 'RECOMMENDATION STABLE'}
                </span>
              </div>
              <ScenarioMetrics data={sc.assumptions} title="Alternate Assumptions" />
              <ScenarioMetrics data={sc.result_summary} title="Sensitivity Results" />
            </div>
          ))}
        </div>
      )}

      {supporting_evidence_ids && supporting_evidence_ids.length > 0 && (
        <div className="rob-evidence">
          <span className="ev-label">Supporting Evidence:</span>
          <div className="ev-tags-group">
            {supporting_evidence_ids.map((id) => (
              <button
                key={id}
                type="button"
                className={`ev-tag-btn ${selectedEvidenceId === id ? 'active' : ''}`}
                onClick={() => onSelectEvidence && onSelectEvidence(id)}
                title={`Inspect evidence item ${id}`}
                aria-label={`Jump to evidence item ${id}`}
              >
                {id}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
