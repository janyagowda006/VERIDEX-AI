import React from 'react';

/**
 * Native SVG/HTML Candidate Comparison Chart for VERIDEX Decision Intelligence.
 * Renders deterministic candidate rankings and observed metrics provided by the backend DecisionEngine.
 *
 * @param {Array<Object>} rankings - List of candidate ranking objects from analysis.rankings.
 * @param {string} metricName - Name of the metric evaluated (optional).
 */
export function CandidateComparisonChart({ rankings = [], metricName = null }) {
  if (!rankings || rankings.length === 0) {
    return (
      <div className="viz-empty-state" role="status">
        <p className="no-data-text">No candidate ranking data available for visual comparison.</p>
      </div>
    );
  }

  // Parse ranking items safely without mutating or re-calculating decision logic
  const parsedItems = rankings.map((r, idx) => {
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

  // Sort visually by rankNum so #1 is always displayed at the top
  const sortedRankings = [...parsedItems].sort((a, b) => a.rankNum - b.rankNum);

  const maxVal = Math.max(...sortedRankings.map((p) => p.numericVal), 0.00001);
  const minVal = Math.min(...sortedRankings.map((p) => p.numericVal), 0);

  const displayMetricName = metricName
    || (sortedRankings[0]?.metricKey ? sortedRankings[0].metricKey.replace(/_/g, ' ') : 'Observed Value');

  return (
    <div className="viz-card candidate-chart-card" role="region" aria-label="Candidate Comparison Chart">
      <div className="viz-header">
        <div className="viz-title-group">
          <span className="viz-icon" aria-hidden="true">📊</span>
          <h4 className="viz-title">Candidate Performance Ranking</h4>
        </div>
        <span className="viz-metric-badge">
          Metric: {displayMetricName}
        </span>
      </div>

      <div className="candidate-bars-container" role="img" aria-label={`Candidate comparison for ${displayMetricName}`}>
        {sortedRankings.map((item) => {
          const isTopRank = item.rankNum === 1;
          const pct = maxVal > minVal
            ? Math.max(Math.round(((item.numericVal - Math.min(0, minVal)) / (maxVal - Math.min(0, minVal))) * 100), 15)
            : 100;

          return (
            <div
              key={item.r?.rank ?? item.idx}
              className={`candidate-bar-row ${isTopRank ? 'row-leader' : ''}`}
            >
              <div className="row-meta">
                <div className="candidate-identity">
                  <span className={`rank-pill ${isTopRank ? 'pill-leader' : ''}`}>
                    #{item.rankNum}
                  </span>
                  <span className="candidate-name" title={item.entityValue}>
                    {item.entityValue}
                  </span>
                </div>
                <span className="metric-val-display">
                  {typeof item.rawMetric === 'number'
                    ? item.rawMetric.toLocaleString()
                    : (item.rawMetric ?? '—')}
                </span>
              </div>

              <div className="bar-track-outer" aria-hidden="true">
                <div
                  className={`bar-fill-inner ${isTopRank ? 'fill-primary-leader' : 'fill-subtle'}`}
                  style={{ width: `${pct}%` }}
                >
                  {isTopRank && <span className="leader-star">★ Top Candidate</span>}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
