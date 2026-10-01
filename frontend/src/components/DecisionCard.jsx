import React from 'react';
import { CopyButton } from './CopyButton.jsx';
import { CandidateComparisonChart } from './visualization/CandidateComparisonChart.jsx';
import { CriteriaThresholdView } from './visualization/CriteriaThresholdView.jsx';

export function DecisionCard({ analysis, selectedEvidenceId, onSelectEvidence }) {
  if (!analysis) return null;

  const { recommendation, criteria_evaluated = [], rankings = [] } = analysis;
  const isRecActive = Boolean(
    selectedEvidenceId && recommendation?.supporting_evidence_ids?.includes(selectedEvidenceId)
  );

  // Parse ranking items dynamically for the table view (contract resilient)
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

      {/* Candidate Performance Comparison Visualization */}
      {rankings.length > 0 && (
        <div className="decision-viz-block">
          <CandidateComparisonChart rankings={rankings} />
        </div>
      )}

      {/* Evaluated Decision Criteria & Threshold Gauge */}
      {criteria_evaluated.length > 0 && (
        <div className="decision-viz-block">
          <CriteriaThresholdView criteria={criteria_evaluated} />
        </div>
      )}

      {/* Detailed Candidate Rankings Data Table */}
      {rankings.length > 0 && (
        <div className="rankings-section">
          <h4>Candidate Rankings Table ({rankings.length})</h4>
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
                  <td>{typeof p.rawMetric === 'number' ? p.rawMetric.toLocaleString() : (p.rawMetric ?? '—')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
