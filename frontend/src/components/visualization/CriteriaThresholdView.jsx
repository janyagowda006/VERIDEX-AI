import React, { useRef } from 'react';
import { exportSvgElement } from '../../utils/svgExporter.js';
import { Tooltip } from '../Tooltip.jsx';

/**
 * Visualizes deterministic decision criteria evaluation matching backend schema.
 * Displays actual_value vs threshold_value, operator comparison, and backend is_met status.
 * Supports presentation-layer SVG export and tooltips.
 *
 * @param {Array<Object>} criteria - List of DecisionCriterion objects from analysis.criteria_evaluated.
 */
export function CriteriaThresholdView({ criteria = [] }) {
  const svgRef = useRef(null);

  if (!criteria || criteria.length === 0) {
    return (
      <div className="viz-empty-state" role="status">
        <p className="no-data-text">No evaluated decision criteria recorded for this analysis.</p>
      </div>
    );
  }

  const passedCount = criteria.filter((c) => c.is_met).length;

  const handleExportSvg = () => {
    exportSvgElement(svgRef, 'criteria_threshold_compliance.svg');
  };

  return (
    <div className="viz-card criteria-threshold-card" role="region" aria-label="Decision Criteria Threshold Compliance">
      <div className="viz-header">
        <div className="viz-title-group">
          <span className="viz-icon" aria-hidden="true">🎯</span>
          <h4 className="viz-title">Decision Criteria & Threshold Compliance</h4>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span className={`compliance-summary-pill ${passedCount === criteria.length ? 'all-passed' : 'some-failed'}`}>
            {passedCount} / {criteria.length} Satisfied
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

      <div className="criteria-gauges-grid">
        {criteria.map((crit) => {
          const isMet = Boolean(crit.is_met);
          const actNum = typeof crit.actual_value === 'number' ? crit.actual_value : parseFloat(crit.actual_value);
          const threshNum = typeof crit.threshold_value === 'number' ? crit.threshold_value : parseFloat(crit.threshold_value);

          const hasNumericComparison = !isNaN(actNum) && !isNaN(threshNum);
          let progressPercent = 50;

          if (hasNumericComparison && threshNum !== 0) {
            const maxVal = Math.max(actNum, threshNum) * 1.15;
            progressPercent = Math.min(Math.max(Math.round((actNum / (maxVal || 1)) * 100), 10), 100);
          } else if (isMet) {
            progressPercent = 100;
          } else {
            progressPercent = 25;
          }

          return (
            <Tooltip
              key={crit.criterion_id}
              text={`${crit.criterion_name}: Actual (${crit.actual_value}) ${crit.operator || '>= '} Threshold (${crit.threshold_value})`}
            >
              <div
                className={`criterion-gauge-box ${isMet ? 'gauge-satisfied' : 'gauge-unsatisfied'}`}
                style={{ width: '100%' }}
              >
                <div className="gauge-top-row">
                  <div className="criterion-identity">
                    <span className={`criterion-status-icon ${isMet ? 'icon-met' : 'icon-unmet'}`} aria-hidden="true">
                      {isMet ? '✓' : '✕'}
                    </span>
                    <span className="criterion-name-text">{crit.criterion_name}</span>
                  </div>
                  <span className={`criterion-status-badge ${isMet ? 'badge-met' : 'badge-unmet'}`}>
                    {isMet ? 'SATISFIED' : 'NOT SATISFIED'}
                  </span>
                </div>

                <div className="gauge-values-row">
                  <div className="val-block actual-val-block">
                    <span className="val-label">Observed Actual:</span>
                    <span className="val-num">
                      {typeof crit.actual_value === 'number'
                        ? crit.actual_value.toLocaleString()
                        : (crit.actual_value ?? 'N/A')}
                    </span>
                  </div>
                  <div className="operator-divider">
                    <span className="operator-chip">{crit.operator || '>= '}</span>
                  </div>
                  <div className="val-block threshold-val-block">
                    <span className="val-label">Required Threshold:</span>
                    <span className="val-num">
                      {typeof crit.threshold_value === 'number'
                        ? crit.threshold_value.toLocaleString()
                        : (crit.threshold_value ?? 'N/A')}
                    </span>
                  </div>
                </div>

                {/* Threshold Progress Visual Bar */}
                <div className="threshold-track-outer" aria-hidden="true">
                  <div
                    className={`threshold-fill ${isMet ? 'fill-satisfied' : 'fill-unsatisfied'}`}
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>

                <p className="criterion-explanation-text">{crit.explanation}</p>
              </div>
            </Tooltip>
          );
        })}
      </div>

      {/* Hidden SVG for vector export */}
      <div style={{ display: 'none' }}>
        <svg ref={svgRef} width="600" height={criteria.length * 90 + 60} viewBox={`0 0 600 ${criteria.length * 90 + 60}`}>
          <rect width="100%" height="100%" fill="#1e293b" />
          <text x="20" y="30" fill="#ffffff" fontSize="16" fontWeight="bold">Decision Criteria & Threshold Compliance</text>
          <text x="20" y="48" fill="#94a3b8" fontSize="12">Satisfied: {passedCount} / {criteria.length}</text>
          {criteria.map((crit, idx) => {
            const y = 70 + idx * 80;
            const isMet = Boolean(crit.is_met);
            return (
              <g key={idx}>
                <rect x="20" y={y} width="560" height="70" rx="6" fill="#0f172a" stroke={isMet ? '#10b981' : '#f43f5e'} strokeWidth="1" />
                <text x="35" y={y + 25} fill={isMet ? '#10b981' : '#f43f5e'} fontSize="14" fontWeight="bold">{isMet ? '✓' : '✕'} {crit.criterion_name}</text>
                <text x="560" y={y + 25} fill={isMet ? '#34d399' : '#fb7185'} fontSize="12" fontWeight="bold" textAnchor="end">{isMet ? 'SATISFIED' : 'NOT SATISFIED'}</text>
                <text x="35" y={y + 50} fill="#cbd5e1" fontSize="12">Actual: {String(crit.actual_value)} | Req: {crit.operator || '>= '} {String(crit.threshold_value)}</text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
