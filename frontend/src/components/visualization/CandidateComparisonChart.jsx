import React, { useRef } from 'react';
import { exportSvgElement } from '../../utils/svgExporter.js';
import { Tooltip } from '../Tooltip.jsx';

/**
 * Native SVG/HTML Candidate Comparison Chart for VERIDEX Decision Intelligence.
 * Renders deterministic candidate rankings and observed metrics provided by the backend DecisionEngine.
 * Supports presentation-layer SVG vector export and accessible tooltips.
 *
 * @param {Array<Object>} rankings - List of candidate ranking objects from analysis.rankings.
 * @param {string} metricName - Name of the metric evaluated (optional).
 */
export function CandidateComparisonChart({ rankings = [], metricName = null }) {
  const svgRef = useRef(null);

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

  const sortedRankings = [...parsedItems].sort((a, b) => a.rankNum - b.rankNum);
  const maxVal = Math.max(...sortedRankings.map((p) => p.numericVal), 0.00001);
  const minVal = Math.min(...sortedRankings.map((p) => p.numericVal), 0);

  const displayMetricName = metricName
    || (sortedRankings[0]?.metricKey ? sortedRankings[0].metricKey.replace(/_/g, ' ') : 'Observed Value');

  const handleExportSvg = () => {
    exportSvgElement(svgRef, `candidate_comparison_${displayMetricName.replace(/\s+/g, '_').toLowerCase()}.svg`);
  };

  return (
    <div className="viz-card candidate-chart-card" role="region" aria-label="Candidate Comparison Chart">
      <div className="viz-header">
        <div className="viz-title-group">
          <span className="viz-icon" aria-hidden="true">📊</span>
          <h4 className="viz-title">Candidate Performance Ranking</h4>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span className="viz-metric-badge">
            Metric: {displayMetricName}
          </span>
          <button
            type="button"
            className="btn-export-svg"
            onClick={handleExportSvg}
            title="Download vector SVG chart image"
            style={{
              padding: '0.2rem 0.5rem',
              fontSize: '0.75rem',
              borderRadius: '0.25rem',
              border: '1px solid var(--border-medium)',
              backgroundColor: 'var(--bg-card-subtle)',
              color: 'var(--text-secondary)',
              cursor: 'pointer'
            }}
          >
            📥 SVG Export
          </button>
        </div>
      </div>

      <div className="candidate-bars-container" role="img" aria-label={`Candidate comparison for ${displayMetricName}`}>
        {sortedRankings.map((item) => {
          const isTopRank = item.rankNum === 1;
          const pct = maxVal > minVal
            ? Math.max(Math.round(((item.numericVal - Math.min(0, minVal)) / (maxVal - Math.min(0, minVal))) * 100), 15)
            : 100;

          return (
            <Tooltip key={item.r?.rank ?? item.idx} text={`Rank #${item.rankNum}: ${item.entityValue} (${item.numericVal.toLocaleString()})`}>
              <div className={`candidate-bar-row ${isTopRank ? 'row-leader' : ''}`} style={{ width: '100%' }}>
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
            </Tooltip>
          );
        })}
      </div>

      {/* Hidden SVG element specifically formatted for vector export */}
      <div style={{ display: 'none' }}>
        <svg ref={svgRef} width="600" height={sortedRankings.length * 50 + 60} viewBox={`0 0 600 ${sortedRankings.length * 50 + 60}`}>
          <rect width="100%" height="100%" fill="#1e293b" />
          <text x="20" y="30" fill="#ffffff" fontSize="16" fontWeight="bold">Candidate Performance Ranking</text>
          <text x="20" y="48" fill="#94a3b8" fontSize="12">Metric: {displayMetricName}</text>
          {sortedRankings.map((item, idx) => {
            const pct = maxVal > minVal
              ? Math.max(Math.round(((item.numericVal - Math.min(0, minVal)) / (maxVal - Math.min(0, minVal))) * 400), 30)
              : 400;
            const y = 70 + idx * 45;
            return (
              <g key={idx}>
                <text x="20" y={y + 15} fill="#38bdf8" fontSize="12" fontWeight="bold">#{item.rankNum} {item.entityValue}</text>
                <text x="560" y={y + 15} fill="#f8fafc" fontSize="12" textAnchor="end">{item.numericVal.toLocaleString()}</text>
                <rect x="150" y={y + 5} width="400" height="14" rx="4" fill="#334155" />
                <rect x="150" y={y + 5} width={pct} height="14" rx="4" fill={item.rankNum === 1 ? '#38bdf8' : '#64748b'} />
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
