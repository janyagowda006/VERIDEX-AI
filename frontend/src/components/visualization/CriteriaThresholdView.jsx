import React from 'react';

/**
 * Visualizes deterministic decision criteria evaluation matching backend schema.
 * Displays actual_value vs threshold_value, operator comparison, and backend is_met status.
 *
 * @param {Array<Object>} criteria - List of DecisionCriterion objects from analysis.criteria_evaluated.
 */
export function CriteriaThresholdView({ criteria = [] }) {
  if (!criteria || criteria.length === 0) {
    return (
      <div className="viz-empty-state" role="status">
        <p className="no-data-text">No evaluated decision criteria recorded for this analysis.</p>
      </div>
    );
  }

  const passedCount = criteria.filter((c) => c.is_met).length;

  return (
    <div className="viz-card criteria-threshold-card" role="region" aria-label="Decision Criteria Threshold Compliance">
      <div className="viz-header">
        <div className="viz-title-group">
          <span className="viz-icon" aria-hidden="true">🎯</span>
          <h4 className="viz-title">Decision Criteria & Threshold Compliance</h4>
        </div>
        <span className={`compliance-summary-pill ${passedCount === criteria.length ? 'all-passed' : 'some-failed'}`}>
          {passedCount} / {criteria.length} Satisfied
        </span>
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
            <div
              key={crit.criterion_id}
              className={`criterion-gauge-box ${isMet ? 'gauge-satisfied' : 'gauge-unsatisfied'}`}
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
          );
        })}
      </div>
    </div>
  );
}
