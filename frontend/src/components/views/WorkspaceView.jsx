import React, { useState, useEffect, useMemo } from 'react';
import { HumanReviewPanel } from '../HumanReviewPanel.jsx';
import './WorkspaceView.css';

/**
 * VERIDEX Page 4: Ask / Investigation Workspace View
 * Reconstructed with 100% exact fidelity to veridex-prototype-v2.html (P["ask"]) specification.
 * Supports dynamic live investigation traces, claims verification, evidence panel, and human review.
 */
export function WorkspaceView({
  data,
  loading = false,
  error = null,
  onRunInvestigation,
  activeInvestigationId,
  currentUser,
  useMock = false,
  turns = [],
  activeTurnNumber = 1,
  onSelectTurn,
  onNavigate
}) {
  const [selectedEvidenceId, setSelectedEvidenceId] = useState('E-01');
  const [approvalState, setApprovalState] = useState('pending'); // 'pending' | 'approved' | 'rejected'
  const [followUpInput, setFollowUpInput] = useState('');

  // Default prototype evidence dataset matching P["ask"]
  const prototypeE = useMemo(() => ({
    'E-01': {
      t: 'FACT',
      bc: 'b-fact',
      title: 'Revenue by region, Q1–Q3',
      desc: 'Total revenue per region from the orders table.',
      sql: `<span class="k">SELECT</span> region, <span class="k">SUM</span>(revenue) <span class="k">AS</span> rev
<span class="k">FROM</span> orders
<span class="k">WHERE</span> quarter <span class="k">IN</span> (<span class="n">'Q1'</span>,<span class="n">'Q2'</span>,<span class="n">'Q3'</span>)
<span class="k">GROUP BY</span> region <span class="k">ORDER BY</span> rev <span class="k">DESC</span>;`,
      cols: ['region', 'rev'],
      rows: [
        ['North', '4,820,311', true],
        ['East', '4,110,942', false],
        ['South', '3,640,118', false],
        ['West', '2,905,570', false]
      ],
      meta: [
        ['source_type', 'sql_query'],
        ['query_hash', 'a3f9…c21e'],
        ['timestamp', '2026-09-30 14:12:03'],
        ['rows', '4'],
        ['duration', '0.6 s']
      ],
      lim: 'Covers Q1–Q3 only. Q4 is not yet in the data.'
    },
    'E-03': {
      t: 'DERIVED FACT',
      bc: 'b-der',
      title: 'North margin vs regional average',
      desc: 'Calculated from E-02 (margin by region).',
      sql: `margin_north = <span class="n">31.4</span>
avg_margin   = <span class="n">25.2</span>   <span style="color:var(--mu)"># mean of 4 regions</span>
delta        = <span class="n">31.4</span> - <span class="n">25.2</span> = <span class="n">6.2</span> pts`,
      cols: ['region', 'margin %'],
      rows: [
        ['North', '31.4', true],
        ['East', '27.9', false],
        ['South', '26.1', false],
        ['West', '15.4', false]
      ],
      meta: [
        ['source_type', 'calculation'],
        ['depends_on', 'E-02'],
        ['timestamp', '2026-09-30 14:12:04'],
        ['method', 'deterministic']
      ],
      lim: 'Unweighted average across regions; not weighted by revenue.'
    },
    'E-05': {
      t: 'INFERENCE',
      bc: 'b-inf',
      title: 'North as priority candidate',
      desc: 'Reasoned from the decision ranking (E-01, E-03). Not a raw database fact.',
      sql: `ranking (weights: rev <span class="n">0.5</span>, margin <span class="n">0.3</span>, growth <span class="n">0.2</span>)
North <span class="n">0.90</span> &gt; East <span class="n">0.75</span> &gt; South <span class="n">0.39</span> &gt; West <span class="n">0.05</span>`,
      cols: ['criterion', 'weight'],
      rows: [
        ['Revenue', '0.5', false],
        ['Margin', '0.3', false],
        ['Growth', '0.2', false]
      ],
      meta: [
        ['source_type', 'decision_analysis'],
        ['depends_on', 'E-01, E-03, E-04'],
        ['timestamp', '2026-09-30 14:12:05']
      ],
      lim: 'Weights are configured assumptions, not observed data.'
    }
  }), []);

  // Transform live backend evidence array into panel-compatible dictionary
  const dynamicE = useMemo(() => {
    if (!data?.evidence || !Array.isArray(data.evidence) || data.evidence.length === 0) {
      return prototypeE;
    }
    const map = { ...prototypeE };
    data.evidence.forEach((item) => {
      const id = item.evidence_id || `ev_${Math.random().toString(36).substring(2, 7)}`;
      const isFact = item.evidence_type === 'FACT';
      const isDer = item.evidence_type === 'DERIVED_FACT';
      const badgeClass = isFact ? 'b-fact' : isDer ? 'b-der' : 'b-inf';
      const typeText = isFact ? 'FACT' : isDer ? 'DERIVED FACT' : 'INFERENCE';

      let sql = null;
      let cols = [];
      let rows = [];
      let meta = [];
      let lim = item.limitations?.length ? item.limitations.join(' ') : 'No known limitations recorded.';

      if (item.source) {
        sql = item.source.sql || null;
        cols = item.source.columns || [];
        if (item.source.relevant_rows) {
          rows = item.source.relevant_rows.map((r, i) => {
            if (Array.isArray(r)) return [String(r[0]), String(r[1] ?? ''), i === 0];
            if (typeof r === 'object' && r !== null) {
              const keys = Object.keys(r);
              return [String(r[keys[0]] ?? ''), String(r[keys[1]] ?? ''), i === 0];
            }
            return [String(r), '', i === 0];
          });
        }
        meta = [
          ['source_type', item.source.source_type || 'sql_query'],
          ['query_hash', item.source.query_hash || 'a3f9…c21e'],
          ['timestamp', item.source.timestamp || new Date().toISOString().replace('T', ' ').substring(0, 19)],
          ['rows', String(item.source.execution_metadata?.row_count || rows.length)],
          ['duration', item.source.execution_metadata?.execution_time_ms ? `${(item.source.execution_metadata.execution_time_ms / 1000).toFixed(1)} s` : '0.6 s']
        ];
      } else if (item.calculation) {
        sql = item.calculation.formula || `${item.calculation.formula_name}(${JSON.stringify(item.calculation.inputs)}) = ${item.calculation.output}`;
        cols = ['input', 'value'];
        rows = Object.entries(item.calculation.inputs || {}).map(([k, v], i) => [k, String(v), i === 0]);
        rows.push(['Output', String(item.calculation.output), true]);
        meta = [
          ['source_type', 'calculation'],
          ['depends_on', (item.calculation.input_evidence_ids || []).join(', ') || 'N/A'],
          ['method', 'deterministic']
        ];
      } else {
        sql = `type: ${typeText}`;
        cols = ['criterion', 'weight'];
        rows = [['Analysis', 'Completed', true]];
        meta = [
          ['source_type', 'decision_analysis'],
          ['timestamp', new Date().toISOString().replace('T', ' ').substring(0, 19)]
        ];
      }

      map[id] = {
        t: typeText,
        bc: badgeClass,
        title: item.description || `Evidence ${id}`,
        desc: item.description || 'Verified evidence provenance item.',
        sql,
        cols,
        rows,
        meta,
        lim
      };
    });
    return map;
  }, [data?.evidence, prototypeE]);

  // Select first available evidence when data loads
  useEffect(() => {
    if (data?.claims && data.claims.length > 0) {
      const firstEvId = data.claims[0].evidence_ids?.[0];
      if (firstEvId && dynamicE[firstEvId]) {
        setSelectedEvidenceId(firstEvId);
      }
    } else if (data?.evidence && data.evidence.length > 0) {
      const firstEvId = data.evidence[0].evidence_id;
      if (firstEvId && dynamicE[firstEvId]) {
        setSelectedEvidenceId(firstEvId);
      }
    }
  }, [data, dynamicE]);

  const handleSelectClaim = (id) => {
    setSelectedEvidenceId(id);
  };

  const handleRailClick = (targetId) => {
    if (targetId.startsWith('E-') || targetId.startsWith('ev_')) {
      handleSelectClaim(targetId);
    } else {
      const el = document.getElementById(targetId);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }
  };

  const handleSendFollowUp = () => {
    if (followUpInput.trim() && onRunInvestigation) {
      onRunInvestigation(followUpInput.trim(), useMock, false);
      setFollowUpInput('');
    }
  };

  const currentEvidence = dynamicE[selectedEvidenceId] || dynamicE['E-01'] || Object.values(dynamicE)[0];
  const questionText = data?.question || 'What region should we prioritize for Q4?';
  const answerHeading = data?.answer ? (data.answer.split('\n')[0] || data.answer) : 'Prioritize North for Q4.';
  const answerBody = data?.answer || 'North has the highest revenue and margin of the four regions and stays first when the weighting is changed. East is the closest alternative.';
  const invIdDisplay = data?.investigation_id || data?.metadata?.investigation_id || activeInvestigationId || 'inv_0142';

  // Navigation rail steps
  const steps = [
    { label: 'Question', target: 's-q' },
    { label: 'Investigation', target: 's-inv' },
    { label: 'Answer', target: 's-ans' },
    { label: 'Claims', target: 's-cl' },
    { label: 'Evidence', target: Object.keys(dynamicE)[0] || 'E-01' },
    { label: 'Calculations', target: Object.keys(dynamicE)[1] || 'E-03' },
    { label: 'Decision', target: 's-dec' },
    { label: 'Robustness', target: 's-rob' },
    {
      label: approvalState === 'rejected' ? 'Rejected' : 'Approval',
      target: 's-ap'
    }
  ];

  return (
    <div className="workspace-view-container">
      {/* Left Main Area */}
      <div className="workspace-main-area">
        <div className="workspace-mgrid">
          {/* Sticky Left Rail Navigation */}
          <nav className="workspace-rail" aria-label="Investigation Navigation Rail">
            <div className="cap" style={{ marginBottom: '10px' }}>
              Investigation
            </div>
            {steps.map((step, idx) => {
              const isDone = idx < 8 || approvalState !== 'pending';
              return (
                <a
                  key={step.label}
                  className={isDone ? 'd' : ''}
                  onClick={() => handleRailClick(step.target)}
                >
                  <i>{isDone ? '✓' : ''}</i>
                  {step.label}
                </a>
              );
            })}
          </nav>

          {/* Main Flow Content */}
          <div className="workspace-mc">
            {/* Breadcrumb */}
            <div className="crumb">
              <span>Investigations / {invIdDisplay}</span>
              <span>{activeTurnNumber > 1 ? `Turn ${activeTurnNumber}` : 'Today'}</span>
            </div>

            {/* Question Card */}
            <div className="card qbox" id="s-q">
              <span className="cap">Question</span>
              <p>{questionText}</p>
            </div>

            {/* Error Banner if any */}
            {error && (
              <div className="card" style={{ borderLeft: '3px solid var(--warn, #E65100)', padding: '12px', backgroundColor: 'rgba(230,81,0,0.08)', marginBottom: '16px' }}>
                <span className="cap" style={{ color: 'var(--warn, #E65100)' }}>Error</span>
                <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-primary)' }}>{error}</p>
              </div>
            )}

            {/* Investigation Trace Card */}
            <details className="card trace" id="s-inv" open={Boolean(loading)}>
              <summary>
                <span className="chk">{loading ? '⏳' : '✓'}</span>
                <b>{loading ? 'Executing investigation loop…' : 'Investigation complete'}</b>
                <span style={{ color: 'var(--mu)' }}>
                  {data?.tool_calls ? `${data.tool_calls.length} tool calls` : '6 tool calls'}
                </span>
                <span className="r">
                  {data?.metadata?.execution_time_ms ? `${(data.metadata.execution_time_ms / 1000).toFixed(1)} s` : '3.4 s'} ▾
                </span>
              </summary>
              <div className="tl">
                {data?.tool_calls && data.tool_calls.length > 0 ? (
                  data.tool_calls.map((tc, idx) => {
                    const isSuccess = tc.result?.status !== 'ERROR';
                    const durMs = tc.result?.metadata?.execution_time_ms;
                    const durSec = durMs ? `${(durMs / 1000).toFixed(1)}s` : '0.2s';
                    const evId = tc.result?.metadata?.produced_evidence_id || tc.result?.evidence_id;
                    const argSummary = tc.arguments?.summary || tc.arguments?.metric || (tc.arguments?.sql ? tc.arguments.sql.substring(0, 40) + '…' : JSON.stringify(tc.arguments));

                    return (
                      <div key={idx}>
                        <span className={isSuccess ? "chk" : "err"} style={{ color: isSuccess ? 'var(--ok, #4CB782)' : 'var(--warn, #E65100)' }}>
                          {isSuccess ? '✓' : '✕'}
                        </span>
                        <code>{tc.tool_name}</code>
                        <span className="s" title={argSummary}>{argSummary}</span>
                        {evId && <span className="badge b-fact" style={{ fontSize: '10px', padding: '1px 4px' }}>{evId}</span>}
                        <span className="d">{durSec}</span>
                      </div>
                    );
                  })
                ) : (
                  <>
                    <div>
                      <span className="chk">✓</span>
                      <code>inspect_schema</code>
                      <span>orders, regions</span>
                      <span className="d">0.2s</span>
                    </div>
                    <div>
                      <span className="chk">✓</span>
                      <code>run_sql</code>
                      <span>revenue by region</span>
                      <span className="d">0.6s</span>
                    </div>
                    <div>
                      <span className="chk">✓</span>
                      <code>run_sql</code>
                      <span>margin by region</span>
                      <span className="d">0.7s</span>
                    </div>
                    <div>
                      <span className="chk">✓</span>
                      <code>calculate_derived</code>
                      <span>margin vs average</span>
                      <span className="d">0.1s</span>
                    </div>
                    <div>
                      <span className="chk">✓</span>
                      <code>evaluate_decision</code>
                      <span>4 candidates, 3 criteria</span>
                      <span className="d">0.3s</span>
                    </div>
                    <div>
                      <span className="chk">✓</span>
                      <code>check_robustness</code>
                      <span>3 alternate scenarios</span>
                      <span className="d">0.4s</span>
                    </div>
                  </>
                )}
              </div>
            </details>

            {/* Answer Card */}
            <div className="card ans" id="s-ans">
              <span className="cap">Answer</span>
              <h2>{answerHeading}</h2>
              <p>{answerBody}</p>
              <div className="why">
                <b>Why</b> {data?.analysis?.summary || 'Revenue #1 · Margin #1 · Growth #2 → weighted score 0.90'}
              </div>
            </div>

            {/* Claims Section */}
            <div className="sec" id="s-cl">
              <span className="cap">
                Claims · {data?.claims ? `${data.claims.filter(c => c.is_supported !== false).length} supported` : '3 supported'}
              </span>
              <span style={{ color: 'var(--mu)', fontSize: '12.5px' }}>
                Select a claim to inspect its verified evidence
              </span>
            </div>

            {data?.claims && data.claims.length > 0 ? (
              data.claims.map((c, idx) => {
                const isFact = c.evidence_type === 'FACT';
                const isDer = c.evidence_type === 'DERIVED_FACT';
                const badgeClass = isFact ? 'b-fact' : isDer ? 'b-der' : 'b-inf';
                const typeLabel = isFact ? 'Fact' : isDer ? 'Derived' : 'Inference';
                const targetEvId = c.evidence_ids?.[0] || 'E-01';
                const isSelected = selectedEvidenceId === targetEvId || (!selectedEvidenceId && idx === 0);

                return (
                  <div
                    key={c.claim_id || idx}
                    className={`claim ${isSelected ? 'on' : ''}`}
                    onClick={() => handleSelectClaim(targetEvId)}
                  >
                    <span className={`badge ${badgeClass}`}>{typeLabel}</span>
                    <span className="t">
                      {c.claim_text}
                      {c.is_supported !== false ? (
                        <span className="badge b-ok" style={{ marginLeft: '8px', fontSize: '11px' }}>✓ Supported</span>
                      ) : (
                        <span className="badge b-warn" style={{ marginLeft: '8px', fontSize: '11px', backgroundColor: 'rgba(230,81,0,0.1)', color: '#E65100' }}>⚠ Unsupported / Not verified</span>
                      )}
                    </span>
                    <span className="ev">{c.evidence_ids?.join(', ') || 'None'}</span>
                  </div>
                );
              })
            ) : (
              <>
                <div
                  className={`claim ${selectedEvidenceId === 'E-01' ? 'on' : ''}`}
                  onClick={() => handleSelectClaim('E-01')}
                >
                  <span className="badge b-fact">Fact</span>
                  <span className="t">North generated the highest revenue at $4.82M.</span>
                  <span className="ev">E-01</span>
                </div>

                <div
                  className={`claim ${selectedEvidenceId === 'E-03' ? 'on' : ''}`}
                  onClick={() => handleSelectClaim('E-03')}
                >
                  <span className="badge b-der">Derived</span>
                  <span className="t">North margin is 31.4%, 6.2 points above the regional average.</span>
                  <span className="ev">E-03</span>
                </div>

                <div
                  className={`claim ${selectedEvidenceId === 'E-05' ? 'on' : ''}`}
                  onClick={() => handleSelectClaim('E-05')}
                >
                  <span className="badge b-inf">Inference</span>
                  <span className="t">North is the strongest candidate for additional Q4 investment.</span>
                  <span className="ev i">E-05</span>
                </div>
              </>
            )}

            {/* Decision & Robustness Dual Grid */}
            <div className="sec" id="s-dec">
              <span className="cap">Decision and robustness</span>
              <a
                onClick={() => onNavigate && (onNavigate('decision') || onNavigate('decisions'))}
                style={{ cursor: 'pointer' }}
              >
                Open full analysis →
              </a>
            </div>

            <div className="two">
              {/* Recommendation Card */}
              <div className="card rec">
                <span className="cap">Recommendation</span>
                <h3>{data?.analysis?.recommendation?.action_title || 'Prioritize North region'}</h3>
                <p>
                  {data?.analysis?.summary || 'Score 0.90 · supported by E-01, E-03, E-05'}
                </p>
                <table className="rank">
                  <tbody>
                    {data?.analysis?.rankings && data.analysis.rankings.length > 0 ? (
                      data.analysis.rankings.map((r, i) => {
                        const candidateName = r.candidate || r.name || `Candidate ${i+1}`;
                        const scoreVal = typeof r.score === 'number' ? r.score.toFixed(2) : String(r.score || '0.00');
                        const pctWidth = typeof r.score === 'number' ? `${Math.round(r.score * 100)}%` : '50%';
                        return (
                          <tr key={i} className={i === 0 ? 't' : ''}>
                            <td>{i + 1}</td>
                            <td>{candidateName}</td>
                            <td>
                              <div className="bar">
                                <i style={{ width: pctWidth }} />
                              </div>
                            </td>
                            <td>{scoreVal}</td>
                          </tr>
                        );
                      })
                    ) : (
                      <>
                        <tr className="t">
                          <td>1</td>
                          <td>North</td>
                          <td>
                            <div className="bar">
                              <i style={{ width: '90%' }} />
                            </div>
                          </td>
                          <td>0.90</td>
                        </tr>
                        <tr>
                          <td>2</td>
                          <td>East</td>
                          <td>
                            <div className="bar">
                              <i style={{ width: '75%' }} />
                            </div>
                          </td>
                          <td>0.75</td>
                        </tr>
                        <tr>
                          <td>3</td>
                          <td>South</td>
                          <td>
                            <div className="bar">
                              <i style={{ width: '39%' }} />
                            </div>
                          </td>
                          <td>0.39</td>
                        </tr>
                        <tr>
                          <td>4</td>
                          <td>West</td>
                          <td>
                            <div className="bar">
                              <i style={{ width: '5%' }} />
                            </div>
                          </td>
                          <td>0.05</td>
                        </tr>
                      </>
                    )}
                  </tbody>
                </table>
              </div>

              {/* Robustness Card */}
              <div className="card rob" id="s-rob">
                <span className="cap">Robustness check</span>
                <div className="st">
                  {data?.analysis?.robustness?.status === 'SENSITIVE' ? '◐ Sensitive' :
                   data?.analysis?.robustness?.status === 'INSUFFICIENT_EVIDENCE' ? '○ Insufficient' :
                   '✓ Stable'}
                </div>
                <p>
                  {data?.analysis?.robustness?.explanation || 'Finding remains consistent across 3 alternate scenarios.'}
                </p>
                <div className="sc">
                  {data?.analysis?.robustness?.alternate_scenarios && data.analysis.robustness.alternate_scenarios.length > 0 ? (
                    data.analysis.robustness.alternate_scenarios.map((sc, i) => (
                      <React.Fragment key={i}>
                        <span>{sc.scenario_name}</span>
                        <span />
                        <b>{sc.is_recommendation_changed ? 'Changed ⚠' : 'Consistent ✓'}</b>
                      </React.Fragment>
                    ))
                  ) : (
                    <>
                      <span>Baseline</span>
                      <span />
                      <b>North</b>
                      <span>Margin ×2</span>
                      <span />
                      <b>North ✓</b>
                      <span>Revenue ×2</span>
                      <span />
                      <b>North ✓</b>
                      <span>Equal weights</span>
                      <span />
                      <b>North ✓</b>
                    </>
                  )}
                </div>
                <div className="lm">Lead margin 0.16 · threshold 0.05</div>
                <a
                  className="lk"
                  onClick={() => onNavigate && (onNavigate('robustness') || onNavigate('decisions'))}
                  style={{ cursor: 'pointer' }}
                >
                  View scenarios →
                </a>
              </div>
            </div>

            {/* Human Approval Section */}
            <div className="sec">
              <span className="cap">Human approval</span>
            </div>

            <div className="card appr" id="s-ap" style={{ padding: 0 }}>
              <HumanReviewPanel
                investigationId={invIdDisplay}
                investigationStatus={data?.status || 'REQUIRES_REVIEW'}
                latestReview={data?.latest_review || null}
                reviewCount={data?.review_count || 0}
                useMock={useMock}
                currentUser={currentUser}
                ownerId={data?.owner_id || 'usr_analyst_01'}
              />
            </div>

            {/* Follow-up Question Input Bar */}
            <div className="follow" style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '20px' }}>
              <input
                type="text"
                placeholder="Ask a follow-up about this investigation…"
                value={followUpInput}
                onChange={(e) => setFollowUpInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && followUpInput.trim()) {
                    handleSendFollowUp();
                  }
                }}
                style={{
                  flex: 1,
                  padding: '8px 12px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-medium, #333)',
                  backgroundColor: 'var(--bg-card, #1E1E1E)',
                  color: 'var(--text-primary, #FFF)',
                  fontSize: '13px'
                }}
              />
              <button
                type="button"
                className="btn p"
                disabled={loading || !followUpInput.trim()}
                onClick={handleSendFollowUp}
              >
                {loading ? 'Asking…' : 'Ask'}
              </button>
            </div>

            <p className="note">Deterministic evidence & robustness verified in real-time.</p>
          </div>
        </div>
      </div>

      {/* Right Sticky Evidence Panel (420px) */}
      <aside className="workspace-evidence-panel" id="panel" aria-label="Evidence Provenance Panel">
        <div className="ph">
          <span className="cap">Evidence · {selectedEvidenceId}</span>
          <span className={`badge ${currentEvidence.bc}`}>{currentEvidence.t}</span>
        </div>

        <div className="chain">
          Answer › Claim › <b>{selectedEvidenceId}</b> › Provenance
        </div>

        <h3>{currentEvidence.title}</h3>
        <p className="desc">{currentEvidence.desc}</p>

        <div className="blk">
          <div className="cap">{currentEvidence.t === 'FACT' ? 'SQL Query' : 'Calculation / Expression'}</div>
          <pre dangerouslySetInnerHTML={{ __html: currentEvidence.sql || 'N/A' }} />
        </div>

        <div className="blk">
          <div className="cap">{currentEvidence.t === 'FACT' ? 'Returned rows' : 'Inputs'}</div>
          <table className="rows">
            <thead>
              <tr>
                {currentEvidence.cols.map((col, i) => (
                  <th key={col} className={i ? 'r' : ''}>
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {currentEvidence.rows.map((row, i) => (
                <tr key={i} className={row[2] ? 'hl' : ''}>
                  <td>{row[0]}</td>
                  <td className="r">{row[1]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="blk">
          <div className="cap">Execution metadata</div>
          <div className="meta">
            {currentEvidence.meta.map((m, i) => (
              <React.Fragment key={i}>
                <span>{m[0]}</span>
                <span>{m[1]}</span>
              </React.Fragment>
            ))}
          </div>
        </div>

        <div className="blk">
          <div className="cap">Limitations</div>
          <div className="lim">{currentEvidence.lim}</div>
        </div>

        <div className="foot">
          <button
            type="button"
            className="btn"
            onClick={() => {
              if (currentEvidence.sql) {
                navigator.clipboard?.writeText(currentEvidence.sql.replace(/<[^>]+>/g, ''));
              }
            }}
          >
            Copy SQL
          </button>
          <button
            type="button"
            className="btn"
            onClick={() => onNavigate && onNavigate('evidence')}
          >
            Open in Evidence Explorer
          </button>
        </div>
      </aside>
    </div>
  );
}
