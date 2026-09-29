import React from 'react';

export function RobustnessCard({ robustness }) {
  if (!robustness) return null;

  const { status, explanation, baseline_scenario, alternate_scenarios = [] } = robustness;

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
          <h4>Baseline Scenario: {baseline_scenario.scenario_name}</h4>
          <p><strong>Assumptions:</strong> {JSON.stringify(baseline_scenario.assumptions)}</p>
          <p><strong>Summary:</strong> {JSON.stringify(baseline_scenario.result_summary)}</p>
        </div>
      )}

      {alternate_scenarios.length > 0 && (
        <div className="alternate-scenarios-section">
          <h4>Alternate Scenario Tests ({alternate_scenarios.length})</h4>
          {alternate_scenarios.map((sc, idx) => (
            <div key={idx} className={`scenario-box alt-box ${sc.is_recommendation_changed ? 'changed' : 'unchanged'}`}>
              <div className="sc-header">
                <strong>Scenario: {sc.scenario_name}</strong>
                <span className={`sc-flag ${sc.is_recommendation_changed ? 'flag-changed' : 'flag-unchanged'}`}>
                  {sc.is_recommendation_changed ? 'RECOMMENDATION CHANGED' : 'RECOMMENDATION STABLE'}
                </span>
              </div>
              <p><strong>Assumptions:</strong> {JSON.stringify(sc.assumptions)}</p>
              <p><strong>Summary:</strong> {JSON.stringify(sc.result_summary)}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
