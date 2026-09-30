import React from 'react';
import { CopyButton } from './CopyButton.jsx';

export function DecisionCard({ analysis, selectedEvidenceId, onSelectEvidence }) {
  if (!analysis) return null;

  const { recommendation, criteria_evaluated = [], rankings = [] } = analysis;
  const isRecActive = Boolean(
    selectedEvidenceId && recommendation?.supporting_evidence_ids?.includes(selectedEvidenceId)
  );

  // Parse ranking items dynamically (contract resilient)
  const parsedRankings = rankings.map((r, idx) => {
    const details = r?.details || {};
    const topKeys = Object.keys(r || {}).filter((k) => k !== 'rank' && k !== 'details');
    const detailKeys = Object.keys(details).filter((k) => k !== 'rank');

    const metricKey = topKeys.find((k) => typeof r[k] === 'number')
      || detailKeys.find((k) => typeof details[k] === 'number');

    const entityKey = topKeys.find((k) => k !== metricKey)
      || detailKeys.find((k) => k !== metricKey);

    const entityValue = (entityKey ? (r[entityKey] ?? details[entityKey]) : null)
      ?? (r?.rank ? `Candidate #${r.rank}` : `Candidate #${idx + 1}`);

    const rawMetric = metricKey ? (r[metricKey] ?? details[metricKey]) : null;
    const numericVal = typeof rawMetric === 'number' ? rawMetric : parseFloat(rawMetric) || 0;
    const rawRank = r?.rank ?? details?.rank;
    const parsedRank = typeof rawRank === 'number' ? rawRank : parseInt(rawRank, 10);
    const rankNum = Number.isFinite(parsedRank) && parsedRank > 0 ? parsedRank : (idx + 1);

    return {
      r,
      idx,
      rankNum,
      entityKey,
      metricKey,
      entityValue,
      rawMetric,
      numericVal,
    };
  });

  const allRankNums = parsedRankings.map((p) => p.rankNum);
  const minRank = allRankNums.length > 0 ? Math.min(...allRankNums, 1) : 1;
  const maxRank = allRankNums.length > 0 ? Math.max(...allRankNums, 1) : 1;
  const rankSpan = maxRank - minRank;
  const minBarPercent = parsedRankings.length > 3 ? 25 : 35;

  // Visual rankings sorted by rankNum so #1 is on top even if raw array is unsorted
  const visualRankings = [...parsedRankings].sort((a, b) => a.rankNum - b.rankNum);

  return (
    <div className="card decision-card">
      <h2>Actionable Decision Recommendation</h2>

      {recommendation ? (
        <div className={`recommendation-content ${isRecActive ? 'rec-active' : ''}`}>
          {isRecActive && (
            <div className="rec-active-badge">
              <span className="indicator-dot" aria-hidden="true">●</span> Backed by Selected Evidence ({selectedEvidenceId})
            </div>
          )}
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

          {/* Visual Distribution of Candidate Rankings by Rank Order */}
          <div className="rankings-visual" role="img" aria-label="Visual ranking order of candidates">
            <div className="rankings-visual-header">
              <span className="visual-title">Candidate Ranking Order</span>
              <span className="visual-metric-name">
                {visualRankings[0]?.metricKey ? `Observed: ${visualRankings[0].metricKey.replace(/_/g, ' ')}` : 'Observed Values'}
              </span>
            </div>
            <div className="ranking-bars-list">
              {visualRankings.map((p) => {
                const percentage = rankSpan <= 0
                  ? 100
                  : Math.max(
                      Math.round(100 - ((p.rankNum - minRank) / rankSpan) * (100 - minBarPercent)),
                      minBarPercent
                    );
                const isLeader = p.rankNum === 1;
                return (
                  <div key={p.r?.rank ?? p.idx} className={`ranking-bar-item ${isLeader ? 'bar-leader' : ''}`}>
                    <div className="bar-labels">
                      <span className="bar-candidate-label">
                        <span className={`bar-rank-badge ${isLeader ? 'badge-leader' : ''}`}>#{p.rankNum}</span>
                        <span className="bar-candidate-name">{p.entityValue}</span>
                      </span>
                      <span className="bar-metric-value">
                        {typeof p.rawMetric === 'number' ? p.rawMetric.toLocaleString() : p.rawMetric ?? '—'}
                      </span>
                    </div>
                    <div className="bar-track" aria-hidden="true">
                      <div
                        className={`bar-fill ${isLeader ? 'fill-leader' : ''}`}
                        style={{ width: `${percentage}%` }}
                      >
                        {isLeader && <span className="leader-pill">Top Rank</span>}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <table className="data-table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Candidate Segment</th>
                <th>Observed Metric Value</th>
              </tr>
            </thead>
            <tbody>
              {parsedRankings.map((p) => (
                <tr key={p.r?.rank ?? p.idx}>
                  <td><strong>#{p.rankNum}</strong></td>
                  <td>{p.entityValue}</td>
                  <td>{p.rawMetric ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
