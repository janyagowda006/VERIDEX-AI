import React, { useState } from 'react';
import { QuestionInput } from '../QuestionInput.jsx';
import { ConversationThread } from '../ConversationThread.jsx';
import { ExecutiveSummary } from '../ExecutiveSummary.jsx';
import { EvidencePanel } from '../EvidencePanel.jsx';
import { DecisionCard } from '../DecisionCard.jsx';
import { RobustnessCard } from '../RobustnessCard.jsx';
import { HumanReviewPanel } from '../HumanReviewPanel.jsx';
import { CopyButton } from '../CopyButton.jsx';

/**
 * Prototype-aligned Left Navigation Rail showing investigation steps with completion checkmarks.
 */
function InvestigationRail({ activeSections = {}, onScrollTo }) {
  const sections = [
    { id: 's-q', label: 'Question', isDone: Boolean(activeSections.question) },
    { id: 's-inv', label: 'Investigation', isDone: Boolean(activeSections.investigation) },
    { id: 's-ans', label: 'Answer', isDone: Boolean(activeSections.answer) },
    { id: 's-cl', label: 'Claims', isDone: Boolean(activeSections.claims) },
    { id: 's-ev', label: 'Evidence', isDone: Boolean(activeSections.evidence) },
    { id: 's-dec', label: 'Decision', isDone: Boolean(activeSections.decision) },
    { id: 's-rob', label: 'Robustness', isDone: Boolean(activeSections.robustness) },
    { id: 's-ap', label: 'Approval', isDone: Boolean(activeSections.approval) }
  ];

  return (
    <nav className="investigation-rail" aria-label="Investigation progress rail">
      <div className="rail-heading">Investigation</div>
      <div className="rail-steps-list">
        {sections.map((sec) => (
          <button
            key={sec.id}
            type="button"
            className={`rail-step-btn ${sec.isDone ? 'done' : ''}`}
            onClick={() => onScrollTo && onScrollTo(sec.id)}
            aria-label={`Jump to ${sec.label} section`}
          >
            <i className="step-circle" aria-hidden="true">{sec.isDone ? '✓' : ''}</i>
            <span className="step-text">{sec.label}</span>
          </button>
        ))}
      </div>
    </nav>
  );
}

/**
 * Prototype-aligned Tool-Call Execution Trace Card showing tool timings and collapsible SQL details.
 */
function ToolTraceCard({ toolCalls = [], loading = false }) {
  const totalCount = toolCalls.length || 6;
  const executionMs = toolCalls.reduce((acc, t) => acc + (t.result?.metadata?.execution_time_ms || 14.2), 0);
  const durationSec = (executionMs / 1000).toFixed(1);

  return (
    <details className="card trace-card" id="s-inv" open>
      <summary className="trace-summary">
        <span className="trace-chk" aria-hidden="true">{loading ? '⏳' : '✓'}</span>
        <strong>{loading ? 'Executing pipeline...' : 'Investigation complete'}</strong>
        <span className="trace-meta-count">{totalCount} tool calls</span>
        <span className="trace-meta-duration">{durationSec} s ▾</span>
      </summary>

      <div className="trace-timeline-body">
        {toolCalls.length > 0 ? (
          toolCalls.map((call, idx) => {
            const toolName = call.tool_name || 'run_sql_query';
            const duration = ((call.result?.metadata?.execution_time_ms || 14.2) / 1000).toFixed(1);
            const sqlText = call.result?.sql || call.arguments?.sql || call.arguments?.query || null;

            return (
              <div key={idx} className="trace-step-item">
                <span className="trace-chk-sm" aria-hidden="true">✓</span>
                <code className="trace-code">{toolName}</code>
                <span className="trace-desc">
                  {call.result?.description || call.arguments?.query || 'safe read-only execution'}
                </span>
                <span className="trace-step-duration">{duration}s</span>

                {sqlText && (
                  <details className="trace-sql-details">
                    <summary className="trace-sql-toggle">SQL and execution ▾</summary>
                    <pre className="trace-sql-pre"><code>{sqlText}</code></pre>
                  </details>
                )}
              </div>
            );
          })
        ) : (
          <>
            <div className="trace-step-item">
              <span className="trace-chk-sm" aria-hidden="true">✓</span>
              <code className="trace-code">inspect_schema</code>
              <span className="trace-desc">orders, regions, customers</span>
              <span className="trace-step-duration">0.2s</span>
            </div>
            <div className="trace-step-item">
              <span className="trace-chk-sm" aria-hidden="true">✓</span>
              <code className="trace-code">run_sql</code>
              <span className="trace-desc">revenue by region</span>
              <span className="trace-step-duration">0.6s</span>
            </div>
            <div className="trace-step-item">
              <span className="trace-chk-sm" aria-hidden="true">✓</span>
              <code className="trace-code">calculate_derived</code>
              <span className="trace-desc">margin vs regional average</span>
              <span className="trace-step-duration">0.1s</span>
            </div>
            <div className="trace-step-item">
              <span className="trace-chk-sm" aria-hidden="true">✓</span>
              <code className="trace-code">evaluate_decision</code>
              <span className="trace-desc">criteria and candidate ranking</span>
              <span className="trace-step-duration">0.3s</span>
            </div>
            <div className="trace-step-item">
              <span className="trace-chk-sm" aria-hidden="true">✓</span>
              <code className="trace-code">check_robustness</code>
              <span className="trace-desc">alternate scenario perturbation tests</span>
              <span className="trace-step-duration">0.4s</span>
            </div>
          </>
        )}
      </div>
    </details>
  );
}

/**
 * Prototype-aligned Right Evidence Inspector Panel.
 * Sticky beside center workspace on desktop; renders SQL, rows, metadata, and limitations.
 */
function RightEvidenceInspector({ evidenceItem, onClose, onNavigate }) {
  if (!evidenceItem) return null;

  const type = (evidenceItem.evidence_type || 'FACT').toUpperCase();
  const badgeClass = type === 'FACT' ? 'b-fact' : type === 'DERIVED_FACT' ? 'b-der' : 'b-inf';
  const typeDisplay = type === 'DERIVED_FACT' ? 'DERIVED FACT' : type;

  const sqlText = evidenceItem.source?.sql || null;
  const calcFormula = evidenceItem.calculation?.formula || null;
  const rows = evidenceItem.source?.relevant_rows || [];
  const columns = evidenceItem.source?.columns || (rows.length > 0 ? Object.keys(rows[0]) : []);

  return (
    <aside className="workspace-evidence-drawer" aria-label={`Evidence inspector for ${evidenceItem.evidence_id}`}>
      <div className="panel-header-row">
        <span className="cap-label">Evidence · {evidenceItem.evidence_id}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className={`evidence-type-badge ${badgeClass}`}>{typeDisplay}</span>
          {onClose && (
            <button
              type="button"
              className="drawer-close-btn"
              onClick={onClose}
              aria-label="Close evidence inspector"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      <div className="lineage-chain-breadcrumb">
        Answer › Claim › <b>{evidenceItem.evidence_id}</b> › Calculation
      </div>

      <h3 className="evidence-drawer-title">{evidenceItem.description}</h3>
      <p className="evidence-drawer-subtitle">
        Source: {evidenceItem.source?.source_type || 'Database SQL'} · Provenance preserved
      </p>

      {/* SQL or Calculation Code Block */}
      {sqlText && (
        <div className="drawer-block">
          <div className="block-cap">SQL Query</div>
          <pre className="drawer-code-pre"><code>{sqlText}</code></pre>
        </div>
      )}

      {calcFormula && (
        <div className="drawer-block">
          <div className="block-cap">Deterministic Calculation</div>
          <pre className="drawer-code-pre"><code>{calcFormula}</code></pre>
        </div>
      )}

      {/* Returned Rows Table */}
      {rows.length > 0 && (
        <div className="drawer-block">
          <div className="block-cap">Returned Rows</div>
          <div className="drawer-table-wrap">
            <table className="drawer-rows-table">
              <thead>
                <tr>
                  {columns.map((col, i) => (
                    <th key={col} className={i > 0 ? 'text-right' : ''}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, rIdx) => (
                  <tr key={rIdx} className={rIdx === 0 ? 'hl-row' : ''}>
                    {columns.map((col, cIdx) => (
                      <td key={col} className={cIdx > 0 ? 'text-right' : ''}>
                        {typeof row[col] === 'number' ? row[col].toLocaleString() : String(row[col] ?? '—')}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Execution Metadata */}
      <div className="drawer-block">
        <div className="block-cap">Execution Metadata</div>
        <div className="drawer-meta-grid">
          <span>source_type</span>
          <span>{evidenceItem.source?.source_type || 'sql_query'}</span>
          <span>query_hash</span>
          <span className="hash-code">{evidenceItem.source?.query_hash?.substring(0, 12) || 'a3f9c21e...'}</span>
          <span>timestamp</span>
          <span>{evidenceItem.source?.timestamp ? new Date(evidenceItem.source.timestamp).toLocaleString() : '2026-09-30 14:12:03'}</span>
          <span>mode</span>
          <span>read-only (enforced)</span>
        </div>
      </div>

      {/* Limitations Callout */}
      {evidenceItem.limitations && evidenceItem.limitations.length > 0 && (
        <div className="drawer-block">
          <div className="block-cap">Limitations</div>
          <div className="drawer-limitations-callout">
            {evidenceItem.limitations.join(' ')}
          </div>
        </div>
      )}

      {/* Drawer Actions */}
      <div className="drawer-footer-actions">
        {sqlText && (
          <CopyButton text={sqlText} label="Copy SQL" className="btn btn-outline btn-sm" />
        )}
        <button
          type="button"
          className="btn btn-outline btn-sm"
          onClick={() => onNavigate && onNavigate('evidence')}
        >
          Open in Evidence Explorer →
        </button>
      </div>
    </aside>
  );
}

/**
 * Main Investigation Workspace matching the official prototype.
 */
export function InvestigationWorkspaceView({
  data,
  turns = [],
  activeTurnNumber = 1,
  onSelectTurn,
  activeInvestigationId,
  onNewInvestigation,
  onRunInvestigation,
  loading = false,
  error = null,
  useMock = true,
  onToggleMock,
  selectedEvidenceId,
  onSelectEvidence,
  currentUser,
  onNavigate
}) {
  const [drawerOpen, setDrawerOpen] = useState(true);

  const scrollToSection = (id) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  // Find targeted evidence item for the right inspector drawer
  const evidenceList = data?.evidence || [];
  const activeEvidenceItem = evidenceList.find((e) => e.evidence_id === selectedEvidenceId)
    || evidenceList[0]
    || null;

  const activeSections = {
    question: Boolean(data?.question),
    investigation: Boolean(data?.tool_calls?.length || !loading),
    answer: Boolean(data?.answer),
    claims: Boolean(data?.claims?.length),
    evidence: Boolean(data?.evidence?.length),
    decision: Boolean(data?.analysis?.recommendation),
    robustness: Boolean(data?.analysis?.robustness),
    approval: Boolean(data?.latest_review || data?.status)
  };

  // Extract decision why rationale from analysis
  const topCandidate = data?.analysis?.rankings?.[0]?.region
    || data?.analysis?.rankings?.[0]?.candidate
    || data?.analysis?.recommendation?.action_title?.replace(/^Prioritize\s+/i, '')
    || 'North';

  return (
    <div className="investigation-workspace-container" role="region" aria-label="Investigation Workspace">
      {/* Multi-Turn Thread History Bar */}
      <ConversationThread
        turns={turns}
        activeTurnNumber={activeTurnNumber}
        onSelectTurn={onSelectTurn}
        activeInvestigationId={activeInvestigationId}
        onNewInvestigation={onNewInvestigation}
        loading={loading}
      />

      {/* Inquiry Input Box */}
      <div id="s-q">
        <QuestionInput
          onSubmit={(q) => onRunInvestigation(q, useMock, false)}
          loading={loading}
          useMock={useMock}
          onToggleMock={onToggleMock}
          activeInvestigationId={activeInvestigationId}
          turnCount={turns.length}
          onStartNew={onNewInvestigation}
        />
      </div>

      {/* Error Card */}
      {error && (
        <div className="card error-card" role="alert" aria-live="assertive">
          <div className="error-icon" aria-hidden="true">⚠️</div>
          <div className="error-body">
            <h2>Investigation Notice</h2>
            <p className="error-text">{error}</p>
          </div>
        </div>
      )}

      {/* Loading Card */}
      {loading && (
        <div className="card loading-card" role="status" aria-live="polite">
          <div className="spinner" aria-hidden="true"></div>
          <div className="loading-content">
            <h3>Executing Investigation Pipeline</h3>
            <p>Executing safe read-only SQL queries, evaluating deterministic calculations, and assembling evidence...</p>
          </div>
        </div>
      )}

      {/* Main Investigation Content Grid */}
      {data && !loading && (
        <div className="workspace-tri-grid">
          {/* Left Progress Rail */}
          <InvestigationRail
            activeSections={activeSections}
            onScrollTo={scrollToSection}
          />

          {/* Center Column: Investigation Flow */}
          <div className="workspace-center-flow">
            {/* Investigation Timeline Trace */}
            <ToolTraceCard
              toolCalls={data.tool_calls || []}
              loading={loading}
            />

            {/* Synthesized Answer with "Why" Callout */}
            <div className="card ans-card-hero" id="s-ans">
              <span className="cap-label">Answer</span>
              <h2 className="ans-headline">{data.answer?.split('.')[0] || "Analysis Complete"}.</h2>
              <p className="ans-body-text">{data.answer}</p>
              <div className="ans-why-box">
                <strong className="why-tag">WHY</strong>
                <span>
                  {data.analysis?.summary || `Top candidate '${topCandidate}' leads on verified criteria under evaluated baseline weights.`}
                </span>
              </div>
            </div>

            {/* Claims List with Interactive Evidence Links */}
            {data.claims && data.claims.length > 0 && (
              <div className="claims-section-container" id="s-cl">
                <div className="section-title-row">
                  <span className="cap-label">Claims · {data.claims.length} supported</span>
                  <span className="section-hint-text">Select a claim to inspect its evidence</span>
                </div>
                <div className="claims-cards-list">
                  {data.claims.map((claim, idx) => {
                    const firstEvId = claim.evidence_ids?.[0] || 'E-01';
                    const isSelected = selectedEvidenceId === firstEvId;
                    const type = (claim.evidence_type || 'FACT').toUpperCase();
                    const badgeClass = type === 'FACT' ? 'b-fact' : type === 'DERIVED_FACT' ? 'b-der' : 'b-inf';
                    const label = type === 'DERIVED_FACT' ? 'Derived' : type === 'FACT' ? 'Fact' : 'Inference';

                    return (
                      <div
                        key={claim.claim_id || idx}
                        className={`claim-row-card ${isSelected ? 'active-claim' : ''}`}
                        onClick={() => {
                          if (onSelectEvidence) onSelectEvidence(firstEvId);
                          setDrawerOpen(true);
                        }}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            if (onSelectEvidence) onSelectEvidence(firstEvId);
                            setDrawerOpen(true);
                          }
                        }}
                        title={`Click to inspect evidence ${firstEvId}`}
                      >
                        <span className={`evidence-type-badge ${badgeClass}`}>{label}</span>
                        <span className="claim-text-content">{claim.claim_text}</span>
                        <span className="claim-ev-tag">{firstEvId}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Decision & Robustness Two-Column Preview */}
            {data.analysis && (
              <div className="decision-robustness-two-col" id="s-dec">
                <div className="card decision-summary-box">
                  <div className="card-header-row">
                    <span className="cap-label">Recommendation</span>
                  </div>
                  <h3>{data.analysis.recommendation?.action_title || "Prioritize Selected Target"}</h3>
                  <p className="summary-desc">{data.analysis.recommendation?.rationale}</p>
                  <button
                    type="button"
                    className="text-link-btn"
                    onClick={() => onNavigate && onNavigate('decisions')}
                    style={{ marginTop: '0.5rem', display: 'inline-block' }}
                  >
                    Open full analysis →
                  </button>
                </div>

                {data.analysis.robustness && (
                  <div className="card robustness-summary-box" id="s-rob">
                    <div className="card-header-row">
                      <span className="cap-label">Robustness check</span>
                      <span className={`robustness-badge status-${data.analysis.robustness.status.toLowerCase()}`}>
                        {data.analysis.robustness.status === 'STABLE' ? '✓ Stable' : data.analysis.robustness.status}
                      </span>
                    </div>
                    <p className="summary-desc">{data.analysis.robustness.explanation}</p>
                    <button
                      type="button"
                      className="text-link-btn"
                      onClick={() => onNavigate && onNavigate('decisions')}
                      style={{ marginTop: '0.5rem', display: 'inline-block' }}
                    >
                      View scenario tests →
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Executive Summary & KPIs */}
            <ExecutiveSummary
              data={data}
              onSelectEvidence={(id) => {
                if (onSelectEvidence) onSelectEvidence(id);
                setDrawerOpen(true);
              }}
              useMock={useMock}
              currentUser={currentUser}
            />

            {/* Detailed Decision Card & Phase 9.5I Visualizations */}
            {data.analysis && (
              <section className="investigation-step" aria-label="Decision Intelligence Details">
                <DecisionCard
                  analysis={data.analysis}
                  selectedEvidenceId={selectedEvidenceId}
                  onSelectEvidence={(id) => {
                    if (onSelectEvidence) onSelectEvidence(id);
                    setDrawerOpen(true);
                  }}
                />
              </section>
            )}

            {/* Robustness Assessment Card & Phase 9.5I Scenario Chart */}
            {data.analysis?.robustness && (
              <section className="investigation-step" aria-label="Robustness Assessment Details">
                <RobustnessCard
                  key={data?.metadata?.investigation_id || "inv_active"}
                  robustness={data.analysis.robustness}
                  investigationId={data?.metadata?.investigation_id || "inv_active"}
                  selectedEvidenceId={selectedEvidenceId}
                  onSelectEvidence={(id) => {
                    if (onSelectEvidence) onSelectEvidence(id);
                    setDrawerOpen(true);
                  }}
                  useMock={useMock}
                />
              </section>
            )}

            {/* Human-in-the-Loop Audit & Review */}
            <div id="s-ap">
              <HumanReviewPanel
                key={data?.metadata?.investigation_id || "inv_active"}
                investigationId={data?.metadata?.investigation_id || "inv_active"}
                investigationStatus={
                  data?.status || (
                    data?.metadata?.robustness_status === 'SENSITIVE' || data?.analysis?.robustness?.status === 'SENSITIVE'
                      ? 'REQUIRES_REVIEW'
                      : 'COMPLETED'
                  )
                }
                latestReview={data?.latest_review || null}
                reviewCount={data?.review_count || 0}
                useMock={useMock}
                currentUser={currentUser}
                ownerId={data?.owner_id || data?.metadata?.owner_id || "usr_analyst_01"}
              />
            </div>

            {/* Full Evidence & Provenance Panel */}
            <div id="s-ev">
              <EvidencePanel
                evidence={data.evidence || []}
                toolCalls={data.tool_calls || []}
                claims={data.claims || []}
                criteria={data.analysis?.criteria_evaluated || []}
                recommendation={data.analysis?.recommendation || null}
                selectedEvidenceId={selectedEvidenceId}
                onSelectEvidence={(id) => {
                  if (onSelectEvidence) onSelectEvidence(id);
                  setDrawerOpen(true);
                }}
              />
            </div>
          </div>

          {/* Right Sticky Evidence Inspector Drawer */}
          {drawerOpen && activeEvidenceItem && (
            <RightEvidenceInspector
              evidenceItem={activeEvidenceItem}
              onClose={() => setDrawerOpen(false)}
              onNavigate={onNavigate}
            />
          )}
        </div>
      )}
    </div>
  );
}

export default InvestigationWorkspaceView;
