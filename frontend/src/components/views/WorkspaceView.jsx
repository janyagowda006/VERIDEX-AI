import React, { useState } from 'react';
import './WorkspaceView.css';

/**
 * VERIDEX Page 4: Ask / Investigation Workspace View
 * Reconstructed with 100% exact fidelity to veridex-prototype-v2.html (P["ask"]) specification.
 */
export function WorkspaceView({
  onNavigate
}) {
  const [selectedEvidenceId, setSelectedEvidenceId] = useState('E-01');
  const [approvalState, setApprovalState] = useState('pending'); // 'pending' | 'approved' | 'rejected'

  // Prototype evidence dataset matching P["ask"]
  const E = {
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
  };

  const handleSelectClaim = (id) => {
    setSelectedEvidenceId(id);
  };

  const handleRailClick = (targetId) => {
    if (targetId.startsWith('E-')) {
      handleSelectClaim(targetId);
    } else {
      const el = document.getElementById(targetId);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }
  };

  const currentEvidence = E[selectedEvidenceId] || E['E-01'];

  // Rail steps data matching prototype rail() script
  const steps = [
    { label: 'Question', target: 's-q' },
    { label: 'Investigation', target: 's-inv' },
    { label: 'Answer', target: 's-ans' },
    { label: 'Claims', target: 's-cl' },
    { label: 'Evidence', target: 'E-01' },
    { label: 'Calculations', target: 'E-03' },
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
              <span>Investigations / New</span>
              <span>inv_0142 · Today 14:12</span>
            </div>

            {/* Question Card */}
            <div className="card qbox" id="s-q">
              <span className="cap">Question</span>
              <p>What region should we prioritize for Q4?</p>
            </div>

            {/* Investigation Trace Card (Collapsed by default matching prototype) */}
            <details className="card trace" id="s-inv">
              <summary>
                <span className="chk">✓</span>
                <b>Investigation complete</b>
                <span style={{ color: 'var(--mu)' }}>6 tool calls</span>
                <span className="r">3.4 s ▾</span>
              </summary>
              <div className="tl">
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
              </div>
            </details>

            {/* Answer Card */}
            <div className="card ans" id="s-ans">
              <span className="cap">Answer</span>
              <h2>Prioritize North for Q4.</h2>
              <p>
                North has the highest revenue and margin of the four regions and stays first when the weighting is changed. East is the closest alternative.
              </p>
              <div className="why">
                <b>Why</b> Revenue #1 · Margin #1 · Growth #2 → weighted score 0.90
              </div>
            </div>

            {/* Claims Section */}
            <div className="sec" id="s-cl">
              <span className="cap">Claims · 3 supported</span>
              <span style={{ color: 'var(--mu)', fontSize: '12.5px' }}>
                Select a claim to inspect its evidence
              </span>
            </div>

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
                <h3>Prioritize North region</h3>
                <p>Score 0.90 · supported by E-01, E-03, E-05</p>
                <table className="rank">
                  <tbody>
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
                  </tbody>
                </table>
              </div>

              {/* Robustness Card */}
              <div className="card rob" id="s-rob">
                <span className="cap">Robustness check</span>
                <div className="st">✓ Stable</div>
                <p>Finding remains consistent across 3 alternate scenarios.</p>
                <div className="sc">
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

            <div
              className="card appr"
              id="s-ap"
              style={{
                '--ap':
                  approvalState === 'approved'
                    ? '#4CB782'
                    : approvalState === 'rejected'
                    ? '#8B95A5'
                    : '#4C8DFF',
                borderLeft: '3px solid var(--ap)'
              }}
            >
              {approvalState === 'pending' && (
                <>
                  <div className="ah">
                    <span className="cap">Human approval</span>
                    <span className="badge b-pr">Pending review</span>
                  </div>
                  <p>
                    <b>Prioritize North region</b>
                    <br />
                    Review the evidence, then approve or reject. VERIDEX recommends; you decide.
                  </p>
                  <div className="ab">
                    <button
                      className="apbtn"
                      onClick={() => handleSelectClaim('E-01')}
                    >
                      Review evidence
                    </button>
                    <button
                      className="apbtn"
                      onClick={() => setApprovalState('rejected')}
                    >
                      Reject
                    </button>
                    <button
                      className="apbtn pr"
                      onClick={() => setApprovalState('approved')}
                    >
                      Approve
                    </button>
                  </div>
                </>
              )}

              {approvalState === 'approved' && (
                <>
                  <div className="ah">
                    <span className="cap">Human approval</span>
                    <span className="badge b-ok">Approved</span>
                  </div>
                  <p>
                    <b>Approved</b> by Gagandeep · Sep 30, 14:31
                    <br />
                    Recorded with 7 evidence items and a Stable robustness check.
                  </p>
                  <div className="ab">
                    <button
                      className="apbtn"
                      onClick={() => setApprovalState('pending')}
                    >
                      Undo
                    </button>
                  </div>
                </>
              )}

              {approvalState === 'rejected' && (
                <>
                  <div className="ah">
                    <span className="cap">Human approval</span>
                    <span className="badge b-neu">Rejected</span>
                  </div>
                  <p>
                    <b>Rejected</b> by Gagandeep · Sep 30, 14:31
                    <br />
                    Recorded with 7 evidence items and a Stable robustness check.
                  </p>
                  <div className="ab">
                    <button
                      className="apbtn"
                      onClick={() => setApprovalState('pending')}
                    >
                      Undo
                    </button>
                  </div>
                </>
              )}
            </div>

            {/* Follow-up Question Static Bar (Matching Prototype) */}
            <div className="follow">
              <span>Ask a follow-up about this investigation…</span>
              <button type="button" className="btn p">
                Ask
              </button>
            </div>

            <p className="note">Sample data shown for illustration.</p>
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
          Answer › Claim › <b>{selectedEvidenceId}</b> › Calculation
        </div>

        <h3>{currentEvidence.title}</h3>
        <p className="desc">{currentEvidence.desc}</p>

        <div className="blk">
          <div className="cap">{currentEvidence.t === 'FACT' ? 'SQL' : 'Calculation'}</div>
          <pre dangerouslySetInnerHTML={{ __html: currentEvidence.sql }} />
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
          <button type="button" className="btn">
            Copy SQL
          </button>
          <button type="button" className="btn">
            Open in Evidence Explorer
          </button>
        </div>
      </aside>
    </div>
  );
}
