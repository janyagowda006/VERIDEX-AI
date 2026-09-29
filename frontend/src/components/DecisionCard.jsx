import React from 'react';

export function DecisionCard({ analysis }) {
  if (!analysis) return null;

  const { recommendation, criteria_evaluated = [], rankings = [] } = analysis;

  return (
    <div className="card decision-card">
      <h2>Actionable Decision Recommendation</h2>

      {recommendation ? (
        <div className="recommendation-content">
          <div className="rec-header">
            <h3 className="rec-title">{recommendation.action_title}</h3>
            <span className={`robustness-badge status-${recommendation.robustness_status.toLowerCase()}`}>
              {recommendation.robustness_status}
            </span>
          </div>
          <p className="rec-rationale"><strong>Rationale:</strong> {recommendation.rationale}</p>
          {recommendation.supporting_evidence_ids && recommendation.supporting_evidence_ids.length > 0 && (
            <div className="rec-evidence">
              <strong>Supporting Evidence IDs:</strong> {recommendation.supporting_evidence_ids.join(', ')}
            </div>
          )}
        </div>
      ) : (
        <p className="no-data-text">No recommendation generated.</p>
      )}

      {/* Evaluated Criteria */}
      {criteria_evaluated.length > 0 && (
        <div className="criteria-section">
          <h4>Evaluated Decision Criteria ({criteria_evaluated.length})</h4>
          <ul className="criteria-list">
            {criteria_evaluated.map((crit) => (
              <li key={crit.criterion_id} className={`crit-item ${crit.is_met ? 'met' : 'unmet'}`}>
                <span className="crit-status">{crit.is_met ? '✓ SATISFIED' : '✗ NOT SATISFIED'}</span>
                <span className="crit-name">{crit.criterion_name}</span>
                <p className="crit-expl">{crit.explanation}</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Candidate Rankings */}
      {rankings.length > 0 && (
        <div className="rankings-section">
          <h4>Candidate Rankings</h4>
          <table className="data-table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Candidate Segment</th>
                <th>Observed Metric Value</th>
              </tr>
            </thead>
            <tbody>
              {rankings.map((r) => {
                const entityKey = Object.keys(r.details || {}).find(k => ['region', 'product_name', 'customer_name', 'category'].includes(k)) || 'Item';
                const metricKey = Object.keys(r.details || {}).find(k => typeof r.details[k] === 'number') || 'Value';
                return (
                  <tr key={r.rank}>
                    <td><strong>#{r.rank}</strong></td>
                    <td>{r.details[entityKey]}</td>
                    <td>{r.details[metricKey]}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
