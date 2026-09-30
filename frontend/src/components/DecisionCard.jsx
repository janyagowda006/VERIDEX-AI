import React from 'react';
import { CopyButton } from './CopyButton.jsx';

export function DecisionCard({ analysis, selectedEvidenceId, onSelectEvidence }) {
  if (!analysis) return null;

  const { recommendation, criteria_evaluated = [], rankings = [] } = analysis;

  return (
    <div className="card decision-card">
      <h2>Actionable Decision Recommendation</h2>

      {recommendation ? (
        <div className="recommendation-content">
          <div className="rec-header">
            <h3 className="rec-title">{recommendation.action_title}</h3>
            <div className="rec-header-actions">
              <CopyButton
                text={`Recommendation: ${recommendation.action_title}\nRationale: ${recommendation.rationale}\nRobustness: ${recommendation.robustness_status}`}
                label="Copy Recommendation"
                className="copy-btn-sm"
              />
              <span className={`robustness-badge status-${recommendation.robustness_status.toLowerCase()}`}>
                {recommendation.robustness_status}
              </span>
            </div>
          </div>
          <p className="rec-rationale"><strong>Rationale:</strong> {recommendation.rationale}</p>
          {recommendation.supporting_evidence_ids && recommendation.supporting_evidence_ids.length > 0 && (
            <div className="rec-evidence">
              <span className="ev-label">Supporting Evidence:</span>
              <div className="ev-tags-group">
                {recommendation.supporting_evidence_ids.map((id) => (
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
              {rankings.map((r, idx) => {
                const details = r?.details || {};
                const topKeys = Object.keys(r || {}).filter(k => k !== 'rank' && k !== 'details');
                const detailKeys = Object.keys(details).filter(k => k !== 'rank');

                // Detect metric key (numeric value in r or in details)
                const metricKey = topKeys.find(k => typeof r[k] === 'number')
                  || detailKeys.find(k => typeof details[k] === 'number');

                // Detect candidate/ranking dimension key (non-metric property)
                const entityKey = topKeys.find(k => k !== metricKey)
                  || detailKeys.find(k => k !== metricKey);

                // Extract values with safe fallbacks
                const entityValue = (entityKey ? (r[entityKey] ?? details[entityKey]) : null)
                  ?? (r?.rank ? `Candidate #${r.rank}` : `Candidate #${idx + 1}`);

                const metricValue = (metricKey ? (r[metricKey] ?? details[metricKey]) : null) ?? '—';
                const rankNum = r?.rank ?? (idx + 1);

                return (
                  <tr key={r?.rank ?? idx}>
                    <td><strong>#{rankNum}</strong></td>
                    <td>{entityValue}</td>
                    <td>{metricValue}</td>
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
