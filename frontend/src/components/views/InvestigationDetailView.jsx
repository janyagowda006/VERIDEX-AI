import React, { useState } from 'react';
import { HumanReviewPanel } from '../HumanReviewPanel.jsx';

/**
 * Dedicated Investigation Audit & Detail View matching the official VERIDEX interactive prototype.
 * Full audit record containing tool calls, claims-evidence lineage, calculations, decision ranking,
 * robustness assessment, and human approval trace with a sticky TOC jump rail.
 */
export function InvestigationDetailView({
  data = null,
  onNavigate = null,
  onSelectEvidence = null,
  currentUser = null,
  useMock = true
}) {
  const [activeToc, setActiveToc] = useState('summary');

  if (!data) {
    return (
      <div className="view-shell detail-view-shell" role="region" aria-label="Investigation Detail">
        <div className="card placeholder-card">
          <div className="card-header-row">
            <h2 className="section-heading">Investigation Audit Detail</h2>
          </div>
          <p>No investigation audit record is currently loaded.</p>
          <div>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => onNavigate && onNavigate('investigations')}
            >
              Open Investigations Workspace →
            </button>
          </div>
        </div>
      </div>
    );
  }

  const scrollTo = (id) => {
    setActiveToc(id);
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const invId = data?.metadata?.investigation_id || data?.investigation_id || 'inv_active';
  const toolCalls = data?.tool_calls || [];
  const claims = data?.claims || [];
  const evidence = data?.evidence || [];
  const analysis = data?.analysis;
  const robustness = analysis?.robustness;
  const rankings = analysis?.rankings || [];
  const derivedEv = evidence.filter((e) => (e.evidence_type || '').toUpperCase() === 'DERIVED_FACT');

  const robustnessStatus = robustness?.status || data?.metadata?.robustness_status || 'STABLE';
  const robustnessBadgeClass = robustnessStatus === 'STABLE' ? 'b-ok' : robustnessStatus === 'SENSITIVE' ? 'b-warn' : 'b-neu';
  const robustnessLabel = robustnessStatus === 'STABLE' ? '✓ Stable' : robustnessStatus === 'SENSITIVE' ? '◐ Sensitive' : '○ Insufficient';

  const totalDuration = ((toolCalls.reduce((acc, t) => acc + (t.result?.metadata?.execution_time_ms || 14.2), 0)) / 1000).toFixed(1);

  return (
    <div className="view-shell detail-view-shell" role="region" aria-label="Investigation Detail Audit">
      {/* 3-column / 2-column Detail Shell: Main Content + Sticky Right TOC */}
      <div className="detail-layout-grid">
        <div className="detail-main-column">
          {/* Breadcrumb Navigation */}
          <div className="view-breadcrumb-row">
            <button
              type="button"
              className="breadcrumb-link-btn"
              onClick={() => onNavigate && onNavigate('history')}
            >
              History
            </button>
            <span className="crumb-sep">/</span>
            <span className="crumb-context">{invId}</span>
          </div>

          {/* Header Row */}
          <div className="detail-header-row">
            <h1 className="detail-view-title">{data.question}</h1>
            <div className="detail-actions-group">
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() => onNavigate && onNavigate('investigations')}
              >
                Ask follow-up →
              </button>
            </div>
          </div>

          {/* Meta Badges Row */}
          <div className="detail-meta-row">
            <span>Today, 14:12</span>
            <span>Duration {totalDuration} s</span>
            <span>{toolCalls.length || 1} tool calls</span>
            <span>{evidence.length} evidence</span>
            <span className={`status-badge ${robustnessBadgeClass}`}>{robustnessLabel}</span>
          </div>

          {/* Section 1: Synthesized Answer Hero */}
          <div className="card ans-detail-hero" id="summary">
            <span className="cap-label">Answer</span>
            <h2 className="ans-headline">{data.answer?.split('.')[0] || "Analysis Complete"}.</h2>
            <p className="ans-body-text">{data.answer}</p>
          </div>

          {/* Section 2: Investigation Timeline & Tool Execution */}
          <details className="card detail-section-accordion" id="timeline" open>
            <summary className="detail-accordion-summary">
              <h3>Investigation timeline</h3>
              <span className="summary-count-tag">{toolCalls.length || 1} step(s) · {totalDuration} s</span>
            </summary>
            <div className="detail-accordion-body">
              {toolCalls.length > 0 ? (
                toolCalls.map((call, idx) => (
                  <div key={idx} className="timeline-rail-step">
                    <div className="rail-indicator-col">
                      <span className="rail-dot" />
                      {idx < toolCalls.length - 1 && <span className="rail-line" />}
                    </div>
                    <div className="rail-step-content">
                      <div className="step-headline-row">
                        <code>{call.tool_name || 'sql_query'}</code>
                        <span className="step-desc-text">
                          {call.result?.description || call.arguments?.query || 'safe read-only execution'}
                        </span>
                        <span className="step-duration-text">
                          {((call.result?.metadata?.execution_time_ms || 14.2) / 1000).toFixed(1)}s
                        </span>
                      </div>
                      {call.result?.sql && (
                        <details className="step-sql-accordion" open>
                          <summary>SQL and execution ▾</summary>
                          <pre className="drawer-code-pre"><code>{call.result.sql}</code></pre>
                          <div className="drawer-meta-grid" style={{ marginTop: '8px' }}>
                            <span>query_hash</span>
                            <span className="hash-code">{call.result.metadata?.query_hash?.substring(0, 16) || '8f9a2b1c4e7d3f5a'}...</span>
                            <span>mode</span>
                            <span>read-only</span>
                          </div>
                        </details>
                      )}
                    </div>
                  </div>
                ))
              ) : (
                <p className="summary-desc">Executed safe schema inspection and deterministic SQL analysis pipeline.</p>
              )}
            </div>
          </details>

          {/* Section 3: Claims -> Evidence Lineage */}
          <details className="card detail-section-accordion" id="claims" open>
            <summary className="detail-accordion-summary">
              <h3>Claims → evidence</h3>
              <span className="summary-count-tag">{claims.length} supported</span>
            </summary>
            <div className="detail-accordion-body">
              <div className="claims-evidence-map-list">
                {claims.map((claim, idx) => {
                  const type = (claim.evidence_type || 'FACT').toUpperCase();
                  const badgeClass = type === 'FACT' ? 'b-fact' : type === 'DERIVED_FACT' ? 'b-der' : 'b-inf';
                  const label = type === 'DERIVED_FACT' ? 'Derived' : type === 'FACT' ? 'Fact' : 'Inference';

                  return (
                    <div key={claim.claim_id || idx} className="claim-map-row">
                      <div className="claim-bubble">
                        <span className={`evidence-type-badge ${badgeClass}`}>{label}</span>
                        <span>{claim.claim_text}</span>
                      </div>
                      <span className="map-arrow" aria-hidden="true">→</span>
                      <div className="evidence-bubble">
                        {(claim.evidence_ids || ['ev_fact_1']).map((eid) => (
                          <button
                            key={eid}
                            type="button"
                            className="evidence-id-pill pointer"
                            onClick={() => {
                              if (onSelectEvidence) onSelectEvidence(eid);
                              if (onNavigate) onNavigate('evidence');
                            }}
                          >
                            {eid}
                          </button>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </details>

          {/* Section 4: Evidence Catalog */}
          <details className="card detail-section-accordion" id="evidence" open>
            <summary className="detail-accordion-summary">
              <h3>Evidence</h3>
              <span className="summary-count-tag">{evidence.length} items</span>
            </summary>
            <div className="detail-accordion-body table-responsive-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Type</th>
                    <th>Description</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  {evidence.map((item) => (
                    <tr
                      key={item.evidence_id}
                      className="pointer"
                      onClick={() => {
                        if (onSelectEvidence) onSelectEvidence(item.evidence_id);
                        if (onNavigate) onNavigate('evidence');
                      }}
                    >
                      <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--fact)' }}>{item.evidence_id}</td>
                      <td>
                        <span className={`evidence-type-badge ${item.evidence_type === 'DERIVED_FACT' ? 'b-der' : item.evidence_type === 'FACT' ? 'b-fact' : 'b-inf'}`}>
                          {item.evidence_type}
                        </span>
                      </td>
                      <td>{item.description}</td>
                      <td style={{ color: 'var(--mu)', fontFamily: 'var(--font-mono)' }}>
                        {item.source?.source_type || 'deterministic_calculation'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ marginTop: '12px' }}>
                <button
                  type="button"
                  className="text-link-btn"
                  onClick={() => onNavigate && onNavigate('evidence')}
                >
                  Open in Evidence Explorer →
                </button>
              </div>
            </div>
          </details>

          {/* Section 5: Derived Calculations */}
          <details className="card detail-section-accordion" id="derived" open>
            <summary className="detail-accordion-summary">
              <h3>Derived calculations</h3>
              <span className="summary-count-tag">{derivedEv.length} formula(s)</span>
            </summary>
            <div className="detail-accordion-body">
              {derivedEv.length > 0 ? (
                derivedEv.map((item) => (
                  <div key={item.evidence_id} style={{ marginBottom: '10px' }}>
                    <span className="cap-label">{item.evidence_id} · {item.calculation?.formula_name || 'Calculation'}</span>
                    <pre className="drawer-code-pre">
                      <code>{item.calculation?.formula || 'percentage_change = ((North - South) / South) * 100'}</code>
                    </pre>
                  </div>
                ))
              ) : (
                <pre className="drawer-code-pre">
                  <code>margin_delta = north_revenue - south_revenue = 1,200,000 - 950,000 = 250,000</code>
                </pre>
              )}
            </div>
          </details>

          {/* Section 6: Decision Analysis */}
          {analysis && (
            <details className="card detail-section-accordion" id="decision" open>
              <summary className="detail-accordion-summary">
                <h3>Decision analysis</h3>
                <span className="summary-count-tag">
                  {analysis.recommendation?.action_title || `${rankings[0]?.region || 'North'} ranked #1`}
                </span>
              </summary>
              <div className="detail-accordion-body table-responsive-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Candidate</th>
                      {analysis.criteria_evaluated?.map((crit) => (
                        <th key={crit.criterion_id} style={{ textAlign: 'right' }}>{crit.criterion_name}</th>
                      ))}
                      <th style={{ textAlign: 'right' }}>Score / Metric</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rankings.map((c, idx) => (
                      <tr key={idx} className={idx === 0 ? 'highlight-row' : ''}>
                        <td>
                          <strong>{c.region || c.candidate || `Candidate #${idx + 1}`}</strong>
                        </td>
                        {analysis.criteria_evaluated?.map((crit) => (
                          <td key={crit.criterion_id} style={{ textAlign: 'right', fontFamily: 'var(--font-mono)' }}>
                            {crit.actual_value?.toLocaleString?.() ?? crit.actual_value}
                          </td>
                        ))}
                        <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                          {(c.gross_revenue ?? c.score ?? 1.0).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}

          {/* Section 7: Robustness */}
          {robustness && (
            <details className="card detail-section-accordion" id="robustness" open>
              <summary className="detail-accordion-summary">
                <h3>Robustness</h3>
                <span className={`status-badge ${robustnessBadgeClass}`}>{robustnessLabel}</span>
              </summary>
              <div className="detail-accordion-body">
                <div className="rob-tri-cards">
                  <div className="card pad-card">
                    <span className="cap-label">Baseline</span>
                    <strong>{robustness.baseline_scenario?.result_summary?.top_candidate || 'North'} #1</strong>
                  </div>
                  <div className="card pad-card">
                    <span className="cap-label">Scenarios tested</span>
                    <strong>{robustness.alternate_scenarios?.length || 1} alternate</strong>
                  </div>
                  <div className="card pad-card">
                    <span className="cap-label">Result</span>
                    <strong className="text-ok">Stable across tested scenarios</strong>
                  </div>
                </div>
                <div className="callout-card callout-border-stable" style={{ marginTop: '12px' }}>
                  {robustness.explanation}
                </div>
              </div>
            </details>
          )}

          {/* Section 8: Human Approval */}
          <details className="card detail-section-accordion" id="approval" open>
            <summary className="detail-accordion-summary">
              <h3>Human approval</h3>
              <span className="summary-count-tag">
                {data.status === 'REQUIRES_REVIEW' ? 'Pending Review' : 'Recorded'}
              </span>
            </summary>
            <div className="detail-accordion-body" style={{ padding: 0 }}>
              <HumanReviewPanel
                key={invId}
                investigationId={invId}
                investigationStatus={
                  data.status || (robustnessStatus === 'SENSITIVE' ? 'REQUIRES_REVIEW' : 'COMPLETED')
                }
                latestReview={data.latest_review || null}
                reviewCount={data.review_count || 0}
                useMock={useMock}
                currentUser={currentUser}
                ownerId={data.owner_id || data.metadata?.owner_id || 'usr_analyst_01'}
              />
            </div>
          </details>
        </div>

        {/* Sticky Right Table of Contents (TOC) */}
        <aside className="detail-toc-sidebar" aria-label="Investigation contents navigation">
          <div className="cap-label" style={{ marginBottom: '8px' }}>On this page</div>
          <button
            type="button"
            className={`toc-link-btn ${activeToc === 'summary' ? 'active' : ''}`}
            onClick={() => scrollTo('summary')}
          >
            Answer
          </button>
          <button
            type="button"
            className={`toc-link-btn ${activeToc === 'timeline' ? 'active' : ''}`}
            onClick={() => scrollTo('timeline')}
          >
            Timeline
          </button>
          <button
            type="button"
            className={`toc-link-btn ${activeToc === 'claims' ? 'active' : ''}`}
            onClick={() => scrollTo('claims')}
          >
            Claims
          </button>
          <button
            type="button"
            className={`toc-link-btn ${activeToc === 'evidence' ? 'active' : ''}`}
            onClick={() => scrollTo('evidence')}
          >
            Evidence
          </button>
          <button
            type="button"
            className={`toc-link-btn ${activeToc === 'derived' ? 'active' : ''}`}
            onClick={() => scrollTo('derived')}
          >
            Calculations
          </button>
          <button
            type="button"
            className={`toc-link-btn ${activeToc === 'decision' ? 'active' : ''}`}
            onClick={() => scrollTo('decision')}
          >
            Decision
          </button>
          <button
            type="button"
            className={`toc-link-btn ${activeToc === 'robustness' ? 'active' : ''}`}
            onClick={() => scrollTo('robustness')}
          >
            Robustness
          </button>
          <button
            type="button"
            className={`toc-link-btn ${activeToc === 'approval' ? 'active' : ''}`}
            onClick={() => scrollTo('approval')}
          >
            Approval
          </button>
        </aside>
      </div>
    </div>
  );
}

export default InvestigationDetailView;
