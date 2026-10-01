import React, { useRef } from 'react';
import { exportSvgElement } from '../../utils/svgExporter.js';
import { Tooltip } from '../Tooltip.jsx';

/**
 * End-to-End Evidence Lineage Flowchart for VERIDEX Decision Intelligence.
 * Visualizes existing provenance:
 * FACT (SQL Provenance) -> DERIVED_FACT (Formula) -> CLAIM -> DECISION CRITERION -> RECOMMENDATION
 * Supports presentation-layer SVG vector export and accessible tooltips.
 *
 * @param {Array<Object>} evidence - Categorized EvidenceItem list.
 * @param {Array<Object>} claims - ClaimEvidence mappings list.
 * @param {Array<Object>} criteria - Evaluated DecisionCriterion list.
 * @param {Object} recommendation - Actionable Recommendation payload.
 * @param {Function} onSelectEvidence - Handler to select/highlight targeted evidence item.
 */
export function EvidenceDecisionTrace({
  evidence = [],
  claims = [],
  criteria = [],
  recommendation = null,
  onSelectEvidence = null
}) {
  const svgRef = useRef(null);

  const factItems = evidence.filter((e) => (e.evidence_type || '').toUpperCase() === 'FACT');
  const derivedItems = evidence.filter((e) => (e.evidence_type || '').toUpperCase() === 'DERIVED_FACT');
  const inferenceItems = evidence.filter((e) => (e.evidence_type || '').toUpperCase() === 'INFERENCE');

  const handleExportSvg = () => {
    exportSvgElement(svgRef, 'evidence_decision_trace.svg');
  };

  return (
    <div className="viz-card evidence-trace-card" role="region" aria-label="Evidence to Decision Lineage Trace">
      <div className="viz-header">
        <div className="viz-title-group">
          <span className="viz-icon" aria-hidden="true">🔗</span>
          <h4 className="viz-title">Evidence $\rightarrow$ Claim $\rightarrow$ Decision Lineage Trace</h4>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span className="viz-subtitle-tag">Traceable Audit Pipeline</span>
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

      <div className="trace-pipeline-flow">
        {/* Pipeline Stage 1: Database Facts (SQL Provenance) */}
        <div className="pipeline-stage stage-facts">
          <div className="stage-header">
            <span className="stage-badge badge-fact-stage">1. FACT</span>
            <span className="stage-count">{factItems.length} Verified SQL Fact(s)</span>
          </div>
          <div className="stage-nodes-list">
            {factItems.length > 0 ? (
              factItems.map((item) => (
                <Tooltip key={item.evidence_id} text={`Fact ID: ${item.evidence_id} (Click to inspect query)`}>
                  <div
                    className="trace-node node-fact pointer"
                    onClick={() => onSelectEvidence && onSelectEvidence(item.evidence_id)}
                    title={`Inspect SQL provenance for ${item.evidence_id}`}
                    style={{ width: '100%' }}
                  >
                    <div className="node-head">
                      <span className="node-id">{item.evidence_id}</span>
                      {item.source?.query_hash && (
                        <span className="hash-tag" title={item.source.query_hash}>
                          # {item.source.query_hash.substring(0, 8)}...
                        </span>
                      )}
                    </div>
                    <p className="node-desc">{item.description}</p>
                  </div>
                </Tooltip>
              ))
            ) : (
              <div className="trace-node node-empty">No direct SQL database facts.</div>
            )}
          </div>
        </div>

        <div className="stage-connector" aria-hidden="true">➔</div>

        {/* Pipeline Stage 2: Derived Facts (Deterministic Formulas) */}
        <div className="pipeline-stage stage-derived">
          <div className="stage-header">
            <span className="stage-badge badge-derived-stage">2. DERIVED FACT</span>
            <span className="stage-count">{derivedItems.length} Arithmetic Calculation(s)</span>
          </div>
          <div className="stage-nodes-list">
            {derivedItems.length > 0 ? (
              derivedItems.map((item) => (
                <Tooltip key={item.evidence_id} text={`Formula: ${item.calculation?.formula || item.description}`}>
                  <div
                    className="trace-node node-derived pointer"
                    onClick={() => onSelectEvidence && onSelectEvidence(item.evidence_id)}
                    title={`Inspect derived formula for ${item.evidence_id}`}
                    style={{ width: '100%' }}
                  >
                    <div className="node-head">
                      <span className="node-id">{item.evidence_id}</span>
                      {item.calculation?.formula_name && (
                        <span className="formula-tag">{item.calculation.formula_name}</span>
                      )}
                    </div>
                    <p className="node-desc">{item.description}</p>
                    {item.calculation?.formula && (
                      <code className="formula-code">{item.calculation.formula}</code>
                    )}
                  </div>
                </Tooltip>
              ))
            ) : (
              <div className="trace-node node-empty">No derived fact calculations.</div>
            )}

            {/* Qualitative Inferences separated visually */}
            {inferenceItems.length > 0 && (
              <div className="inference-section">
                <span className="inference-subhead">Qualitative Inferences ({inferenceItems.length})</span>
                {inferenceItems.map((inf) => (
                  <Tooltip key={inf.evidence_id} text={`Inference ID: ${inf.evidence_id}`}>
                    <div className="trace-node node-inference" style={{ width: '100%' }}>
                      <span className="node-id">{inf.evidence_id}</span>
                      <p className="node-desc">{inf.description}</p>
                    </div>
                  </Tooltip>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="stage-connector" aria-hidden="true">➔</div>

        {/* Pipeline Stage 3: Synthesized Claims & Criteria */}
        <div className="pipeline-stage stage-claims">
          <div className="stage-header">
            <span className="stage-badge badge-claim-stage">3. CLAIMS & CRITERIA</span>
            <span className="stage-count">{claims.length} Claim(s) · {criteria.length} Rule(s)</span>
          </div>
          <div className="stage-nodes-list">
            {criteria.map((crit) => (
              <Tooltip key={crit.criterion_id} text={`Criterion: ${crit.criterion_name} (${crit.is_met ? 'SATISFIED' : 'NOT SATISFIED'})`}>
                <div className={`trace-node node-criterion ${crit.is_met ? 'crit-pass' : 'crit-fail'}`} style={{ width: '100%' }}>
                  <div className="node-head">
                    <span className="node-id">{crit.criterion_id}</span>
                    <span className={`crit-badge ${crit.is_met ? 'pass' : 'fail'}`}>
                      {crit.is_met ? '✓ SATISFIED' : '✕ NOT SATISFIED'}
                    </span>
                  </div>
                  <p className="node-desc">{crit.criterion_name}</p>
                </div>
              </Tooltip>
            ))}
          </div>
        </div>

        <div className="stage-connector" aria-hidden="true">➔</div>

        {/* Pipeline Stage 4: Actionable Recommendation */}
        <div className="pipeline-stage stage-recommendation">
          <div className="stage-header">
            <span className="stage-badge badge-rec-stage">4. RECOMMENDATION</span>
            <span className="stage-count">Actionable Output</span>
          </div>
          <div className="stage-nodes-list">
            {recommendation ? (
              <Tooltip text={`Recommendation: ${recommendation.action_title}`}>
                <div className="trace-node node-recommendation" style={{ width: '100%' }}>
                  <div className="node-head">
                    <span className="rec-id">{recommendation.recommendation_id}</span>
                    <span className={`robustness-badge status-${(recommendation.robustness_status || 'STABLE').toLowerCase()}`}>
                      {recommendation.robustness_status}
                    </span>
                  </div>
                  <h5 className="rec-title">{recommendation.action_title}</h5>
                  <p className="node-desc">{recommendation.rationale}</p>
                </div>
              </Tooltip>
            ) : (
              <div className="trace-node node-empty">No recommendation generated.</div>
            )}
          </div>
        </div>
      </div>

      {/* Hidden SVG for vector export */}
      <div style={{ display: 'none' }}>
        <svg ref={svgRef} width="800" height="400" viewBox="0 0 800 400">
          <rect width="100%" height="100%" fill="#1e293b" />
          <text x="20" y="30" fill="#ffffff" fontSize="16" fontWeight="bold">Evidence to Decision Lineage Trace</text>
          <text x="20" y="50" fill="#94a3b8" fontSize="12">Traceable Audit Pipeline</text>

          {/* Stage 1: Facts */}
          <rect x="20" y="70" width="170" height="300" rx="6" fill="#0f172a" stroke="#38bdf8" strokeWidth="1" />
          <text x="30" y="95" fill="#38bdf8" fontSize="13" fontWeight="bold">1. FACT ({factItems.length})</text>
          {factItems.slice(0, 3).map((f, i) => (
            <text key={i} x="30" y={125 + i * 40} fill="#f8fafc" fontSize="11">{f.evidence_id}: {f.description.substring(0, 20)}...</text>
          ))}

          {/* Connector 1 */}
          <text x="200" y="200" fill="#94a3b8" fontSize="20">→</text>

          {/* Stage 2: Derived */}
          <rect x="220" y="70" width="170" height="300" rx="6" fill="#0f172a" stroke="#a855f7" strokeWidth="1" />
          <text x="230" y="95" fill="#a855f7" fontSize="13" fontWeight="bold">2. DERIVED ({derivedItems.length})</text>
          {derivedItems.slice(0, 3).map((d, i) => (
            <text key={i} x="230" y={125 + i * 40} fill="#f8fafc" fontSize="11">{d.evidence_id}: {d.description.substring(0, 20)}...</text>
          ))}

          {/* Connector 2 */}
          <text x="400" y="200" fill="#94a3b8" fontSize="20">→</text>

          {/* Stage 3: Criteria */}
          <rect x="420" y="70" width="170" height="300" rx="6" fill="#0f172a" stroke="#eab308" strokeWidth="1" />
          <text x="430" y="95" fill="#eab308" fontSize="13" fontWeight="bold">3. CRITERIA ({criteria.length})</text>
          {criteria.slice(0, 3).map((c, i) => (
            <text key={i} x="430" y={125 + i * 40} fill={c.is_met ? '#34d399' : '#fb7185'} fontSize="11">{c.is_met ? '✓' : '✕'} {c.criterion_name.substring(0, 18)}...</text>
          ))}

          {/* Connector 3 */}
          <text x="600" y="200" fill="#94a3b8" fontSize="20">→</text>

          {/* Stage 4: Recommendation */}
          <rect x="620" y="70" width="160" height="300" rx="6" fill="#0f172a" stroke="#10b981" strokeWidth="1" />
          <text x="630" y="95" fill="#10b981" fontSize="13" fontWeight="bold">4. OUTPUT</text>
          {recommendation && (
            <text x="630" y="125" fill="#f8fafc" fontSize="11" fontWeight="bold">{recommendation.action_title.substring(0, 20)}...</text>
          )}
        </svg>
      </div>
    </div>
  );
}
