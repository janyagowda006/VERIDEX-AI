import React, { useState } from 'react';
import { reassessInvestigation } from '../api/client.js';
import { ScenarioDiffView } from './ScenarioDiffView.jsx';
import { RobustnessScenarioChart } from './visualization/RobustnessScenarioChart.jsx';

function formatMetricKey(key) {
  if (!key) return '';
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatMetricValue(val) {
  if (val === null || val === undefined) return '—';
  if (typeof val === 'boolean') return val ? 'True' : 'False';
  if (typeof val === 'object') return JSON.stringify(val);
  return String(val);
}

function ScenarioMetrics({ data, title }) {
  if (!data || Object.keys(data).length === 0) return null;

  return (
    <div className="metric-group">
      <span className="metric-group-title">{title}:</span>
      <div className="metric-chips">
        {Object.entries(data).map(([key, val]) => (
          <div key={key} className="metric-chip">
            <span className="chip-key">{formatMetricKey(key)}:</span>
            <span className="chip-val">{formatMetricValue(val)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function RobustnessStatusMeter({ status }) {
  const normalized = (status || 'STABLE').toUpperCase();

  const stages = [
    {
      id: 'INSUFFICIENT_EVIDENCE',
      label: 'Insufficient Evidence',
      desc: 'Lacks verified queries',
      icon: '○'
    },
    {
      id: 'SENSITIVE',
      label: 'Sensitive',
      desc: 'Altered by assumptions',
      icon: '▲'
    },
    {
      id: 'STABLE',
      label: 'Stable Finding',
      desc: 'Invariant to variations',
      icon: '✓'
    }
  ];

  return (
    <div className="robustness-meter" role="region" aria-label={`Robustness classification meter: ${normalized}`}>
      <div className="meter-track">
        {stages.map((stage) => {
          const isActive = normalized === stage.id;
          return (
            <div
              key={stage.id}
              className={`meter-step step-${stage.id.toLowerCase()} ${isActive ? 'active' : ''}`}
            >
              <div className="meter-node">
                <span className="meter-icon" aria-hidden="true">{stage.icon}</span>
              </div>
              <div className="meter-text">
                <span className="meter-label">{stage.label}</span>
                <span className="meter-desc">{stage.desc}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function RobustnessCard({
  robustness,
  investigationId,
  selectedEvidenceId,
  onSelectEvidence,
  useMock = false
}) {
  const [selectedShift, setSelectedShift] = useState(10);
  const [reassessLoading, setReassessLoading] = useState(false);
  const [reassessResult, setReassessResult] = useState(null);
  const [reassessError, setReassessError] = useState(null);

  if (!robustness) return null;

  const { status, explanation, baseline_scenario, alternate_scenarios = [], supporting_evidence_ids = [] } = robustness;
  const shiftPresets = [5, 10, 15, 20, 25, 30];

  const handleReassessSubmit = async (shiftVal = selectedShift) => {
    const targetInvId = investigationId || "inv_mock_123456";
    setReassessLoading(true);
    setReassessError(null);
    try {
      const res = await reassessInvestigation(targetInvId, shiftVal, useMock);
      setReassessResult(res);
    } catch (err) {
      setReassessError(err.message || "Unable to reassess investigation. Please try again.");
    } finally {
      setReassessLoading(false);
    }
  };

  return (
    <div className="card robustness-card">
      <div className="card-header">
        <h2>Deterministic Robustness Check</h2>
        <span className={`robustness-badge status-${status.toLowerCase()}`}>
          {status}
        </span>
      </div>

      {/* Visual Robustness Stability Gauge */}
      <RobustnessStatusMeter status={status} />

      <p className="robustness-explanation">{explanation}</p>

      {/* Visual Scenario Sensitivity Perturbation Chart */}
      <div className="robustness-viz-block">
        <RobustnessScenarioChart
          baselineScenario={baseline_scenario}
          alternateScenarios={alternate_scenarios}
          robustnessStatus={status}
        />
      </div>

      {/* Interactive Scenario Shift Control Section */}
      <div className="interactive-robustness-section">
        <div className="section-title-bar">
          <h3>Interactive Sensitivity Re-assessment</h3>
          <span className="section-hint">Select stress perturbation magnitude (% metric shift)</span>
        </div>

        <div className="shift-controls-bar">
          <div className="preset-buttons" role="group" aria-label="Scenario shift percentage presets">
            {shiftPresets.map((pct) => (
              <button
                key={pct}
                type="button"
                className={`shift-preset-btn ${selectedShift === pct ? 'active' : ''}`}
                onClick={() => setSelectedShift(pct)}
                disabled={reassessLoading}
              >
                {pct}%
              </button>
            ))}
          </div>

          <button
            type="button"
            className="reassess-action-btn"
            onClick={() => handleReassessSubmit(selectedShift)}
            disabled={reassessLoading}
          >
            {reassessLoading ? (
              <>
                <span className="btn-spinner" aria-hidden="true"></span>
                Re-assessing...
              </>
            ) : (
              `Re-assess @ ${selectedShift}%`
            )}
          </button>
        </div>

        {reassessError && (
          <div className="reassess-error-banner" role="alert">
            <span className="error-icon" aria-hidden="true">⚠️</span>
            <span>{reassessError}</span>
          </div>
        )}
      </div>

      {/* Render Scenario Diff View when Re-assessment Result is Available */}
      {reassessResult && (
        <ScenarioDiffView
          reassessResult={reassessResult}
          baselineRobustness={robustness}
        />
      )}

      {baseline_scenario && (
        <div className="scenario-box baseline-box">
          <div className="sc-header">
            <strong>Baseline Scenario: {formatMetricKey(baseline_scenario.scenario_name)}</strong>
            <span className="sc-flag flag-baseline">BASELINE (10%)</span>
          </div>
          <ScenarioMetrics data={baseline_scenario.assumptions} title="Assumptions" />
          <ScenarioMetrics data={baseline_scenario.result_summary} title="Observed Results" />
        </div>
      )}

      {alternate_scenarios.length > 0 && (
        <div className="alternate-scenarios-section">
          <h4>Baseline Alternate Scenario Tests ({alternate_scenarios.length})</h4>
          {alternate_scenarios.map((sc, idx) => (
            <div key={idx} className={`scenario-box alt-box ${sc.is_recommendation_changed ? 'changed' : 'unchanged'}`}>
              <div className="sc-header">
                <strong>Scenario: {formatMetricKey(sc.scenario_name)}</strong>
                <span className={`sc-flag ${sc.is_recommendation_changed ? 'flag-changed' : 'flag-unchanged'}`}>
                  {sc.is_recommendation_changed ? 'RECOMMENDATION CHANGED' : 'RECOMMENDATION STABLE'}
                </span>
              </div>
              <ScenarioMetrics data={sc.assumptions} title="Alternate Assumptions" />
              <ScenarioMetrics data={sc.result_summary} title="Sensitivity Results" />
            </div>
          ))}
        </div>
      )}

      {supporting_evidence_ids && supporting_evidence_ids.length > 0 && (
        <div className="rob-evidence">
          <span className="ev-label">Supporting Evidence:</span>
          <div className="ev-tags-group">
            {supporting_evidence_ids.map((id) => (
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
  );
}
