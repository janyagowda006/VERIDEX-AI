import React, { useRef } from 'react';
import { exportSvgElement } from '../../utils/svgExporter.js';
import { Tooltip } from '../Tooltip.jsx';

function formatScenarioTitle(name) {
  if (!name) return 'Scenario';
  return name
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

/**
 * Visualizes baseline vs alternate scenario perturbation tests from RobustnessEngine.
 * Displays sensitivity tipping points and recommendation stability.
 * Supports presentation-layer SVG export and tooltips.
 *
 * @param {Object} baselineScenario - Baseline scenario from robustness.baseline_scenario.
 * @param {Array<Object>} alternateScenarios - List of scenarios from robustness.alternate_scenarios.
 * @param {string} robustnessStatus - Classification status: STABLE, SENSITIVE, INSUFFICIENT_EVIDENCE.
 */
export function RobustnessScenarioChart({
  baselineScenario = null,
  alternateScenarios = [],
  robustnessStatus = 'STABLE'
}) {
  const svgRef = useRef(null);
  const normStatus = (robustnessStatus || 'STABLE').toUpperCase();

  const handleExportSvg = () => {
    exportSvgElement(svgRef, `robustness_scenarios_${normStatus.toLowerCase()}.svg`);
  };

  return (
    <div className="viz-card robustness-chart-card" role="region" aria-label="Robustness Scenario Sensitivity Chart">
      <div className="viz-header">
        <div className="viz-title-group">
          <span className="viz-icon" aria-hidden="true">🛡️</span>
          <h4 className="viz-title">Scenario Sensitivity & Perturbation Timeline</h4>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span className={`robustness-status-pill status-${normStatus.toLowerCase()}`}>
            Status: {normStatus}
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

      <div className="scenario-timeline-container">
        {/* Baseline Scenario Node */}
        {baselineScenario && (
          <Tooltip text={`Baseline Scenario: Top Candidate '${baselineScenario.result_summary?.top_candidate || 'N/A'}'`}>
            <div className="timeline-node node-baseline" style={{ width: '100%' }}>
              <div className="node-badge-col">
                <span className="node-pill pill-baseline">Baseline</span>
                <div className="node-line-connector" aria-hidden="true" />
              </div>
              <div className="node-content-box">
                <div className="node-title-row">
                  <strong>{formatScenarioTitle(baselineScenario.scenario_name)}</strong>
                  <span className="stability-tag tag-stable">Baseline Reference</span>
                </div>
                <div className="node-details">
                  {baselineScenario.result_summary?.top_candidate && (
                    <span>Top Candidate: <strong>{baselineScenario.result_summary.top_candidate}</strong></span>
                  )}
                  {baselineScenario.result_summary?.total_rows !== undefined && (
                    <span>Total Rows Evaluated: {baselineScenario.result_summary.total_rows}</span>
                  )}
                </div>
              </div>
            </div>
          </Tooltip>
        )}

        {/* Alternate Perturbation Scenarios */}
        {alternateScenarios.map((sc, idx) => {
          const isChanged = Boolean(sc.is_recommendation_changed);
          return (
            <Tooltip
              key={idx}
              text={`Scenario '${sc.scenario_name}': ${isChanged ? 'Recommendation Shift' : 'Recommendation Stable'}`}
            >
              <div className={`timeline-node node-alternate ${isChanged ? 'node-changed' : 'node-unchanged'}`} style={{ width: '100%' }}>
                <div className="node-badge-col">
                  <span className={`node-pill ${isChanged ? 'pill-changed' : 'pill-unchanged'}`}>
                    Alt #{idx + 1}
                  </span>
                  {idx < alternateScenarios.length - 1 && (
                    <div className="node-line-connector" aria-hidden="true" />
                  )}
                </div>
                <div className="node-content-box">
                  <div className="node-title-row">
                    <strong>{formatScenarioTitle(sc.scenario_name)}</strong>
                    <span className={`stability-tag ${isChanged ? 'tag-changed' : 'tag-stable'}`}>
                      {isChanged ? '⚠ Recommendation Shift' : '✓ Recommendation Stable'}
                    </span>
                  </div>

                  <div className="node-details">
                    {sc.assumptions?.lead_margin_threshold && (
                      <span>Threshold: {sc.assumptions.lead_margin_threshold}</span>
                    )}
                    {sc.result_summary?.lead_margin_percent !== undefined && (
                      <span>Observed Margin: <strong>{sc.result_summary.lead_margin_percent}%</strong></span>
                    )}
                    {sc.result_summary?.second_candidate && (
                      <span>Challenger: <strong>{sc.result_summary.second_candidate}</strong></span>
                    )}
                  </div>
                </div>
              </div>
            </Tooltip>
          );
        })}

        {alternateScenarios.length === 0 && (
          <p className="no-data-text">No baseline alternate scenario tests recorded.</p>
        )}
      </div>

      {/* Hidden SVG for vector export */}
      <div style={{ display: 'none' }}>
        <svg ref={svgRef} width="600" height={(alternateScenarios.length + 1) * 80 + 60} viewBox={`0 0 600 ${(alternateScenarios.length + 1) * 80 + 60}`}>
          <rect width="100%" height="100%" fill="#1e293b" />
          <text x="20" y="30" fill="#ffffff" fontSize="16" fontWeight="bold">Scenario Sensitivity & Perturbation Timeline</text>
          <text x="20" y="48" fill="#94a3b8" fontSize="12">Robustness Status: {normStatus}</text>
          {baselineScenario && (
            <g>
              <rect x="20" y="70" width="560" height="60" rx="6" fill="#0f172a" stroke="#38bdf8" strokeWidth="1" />
              <text x="35" y="95" fill="#38bdf8" fontSize="14" fontWeight="bold">Baseline Scenario</text>
              <text x="35" y="115" fill="#cbd5e1" fontSize="12">Top Candidate: {baselineScenario.result_summary?.top_candidate || 'N/A'}</text>
            </g>
          )}
          {alternateScenarios.map((sc, idx) => {
            const y = 140 + idx * 70;
            const isChanged = Boolean(sc.is_recommendation_changed);
            return (
              <g key={idx}>
                <rect x="20" y={y} width="560" height="60" rx="6" fill="#0f172a" stroke={isChanged ? '#fb7185' : '#34d399'} strokeWidth="1" />
                <text x="35" y={y + 25} fill={isChanged ? '#fb7185' : '#34d399'} fontSize="14" fontWeight="bold">Alt #{idx + 1}: {formatScenarioTitle(sc.scenario_name)}</text>
                <text x="560" y={y + 25} fill={isChanged ? '#fb7185' : '#34d399'} fontSize="12" fontWeight="bold" textAnchor="end">{isChanged ? 'SHIFT' : 'STABLE'}</text>
                <text x="35" y={y + 45} fill="#94a3b8" fontSize="12">Observed Margin: {sc.result_summary?.lead_margin_percent}%</text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
