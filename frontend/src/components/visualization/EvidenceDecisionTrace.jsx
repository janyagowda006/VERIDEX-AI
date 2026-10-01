import React from 'react';

/**
 * End-to-End Evidence Lineage Flowchart for VERIDEX Decision Intelligence.
 * Visualizes existing provenance:
 * FACT (SQL Provenance) -> DERIVED_FACT (Formula) -> CLAIM -> DECISION CRITERION -> RECOMMENDATION
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
  const factItems = evidence.filter((e) => (e.evidence_type || '').toUpperCase() === 'FACT');
  const derivedItems = evidence.filter((e) => (e.evidence_type || '').toUpperCase() === 'DERIVED_FACT');
  const inferenceItems = evidence.filter((e) => (e.evidence_type || '').toUpperCase() === 'INFERENCE');

  return (
    <div className="viz-card evidence-trace-card" role="region" aria-label="Evidence to Decision Lineage Trace">
      <div className="viz-header">
        <div className="viz-title-group">
          <span className="viz-icon" aria-hidden="true">🔗</span>
          <h4 className="viz-title">Evidence $\rightarrow$ Claim $\rightarrow$ Decision Lineage Trace</h4>
        </div>
        <span className="viz-subtitle-tag">Traceable Audit Pipeline</span>
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
                <div
                  key={item.evidence_id}
                  className="trace-node node-fact pointer"
                  onClick={() => onSelectEvidence && onSelectEvidence(item.evidence_id)}
                  title={`Inspect SQL provenance for ${item.evidence_id}`}
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
                <div
                  key={item.evidence_id}
                  className="trace-node node-derived pointer"
                  onClick={() => onSelectEvidence && onSelectEvidence(item.evidence_id)}
                  title={`Inspect derived formula for ${item.evidence_id}`}
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
              ))
            ) : (
              <div className="trace-node node-empty">No derived fact calculations.</div>
            )}

            {/* Qualitative Inferences separated visually */}
            {inferenceItems.length > 0 && (
              <div className="inference-section">
                <span className="inference-subhead">Qualitative Inferences ({inferenceItems.length})</span>
                {inferenceItems.map((inf) => (
                  <div key={inf.evidence_id} className="trace-node node-inference">
                    <span className="node-id">{inf.evidence_id}</span>
                    <p className="node-desc">{inf.description}</p>
                  </div>
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
              <div key={crit.criterion_id} className={`trace-node node-criterion ${crit.is_met ? 'crit-pass' : 'crit-fail'}`}>
                <div className="node-head">
                  <span className="node-id">{crit.criterion_id}</span>
                  <span className={`crit-badge ${crit.is_met ? 'pass' : 'fail'}`}>
                    {crit.is_met ? '✓ SATISFIED' : '✕ NOT SATISFIED'}
                  </span>
                </div>
                <p className="node-desc">{crit.criterion_name}</p>
              </div>
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
              <div className="trace-node node-recommendation">
                <div className="node-head">
                  <span className="rec-id">{recommendation.recommendation_id}</span>
                  <span className={`robustness-badge status-${(recommendation.robustness_status || 'STABLE').toLowerCase()}`}>
                    {recommendation.robustness_status}
                  </span>
                </div>
                <h5 className="rec-title">{recommendation.action_title}</h5>
                <p className="node-desc">{recommendation.rationale}</p>
              </div>
            ) : (
              <div className="trace-node node-empty">No recommendation generated.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
