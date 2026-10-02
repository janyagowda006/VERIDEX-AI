import React, { useState, useEffect } from 'react';
import './DecisionsView.css';

// Candidate dataset C & weights W (veridex-prototype-v2.html P["decision"])
const C = [
  { n: "North", raw: ["$4.82M", "31.4%", "+3.1%"], nm: [1, 1, 0.523], ok: 1 },
  { n: "East", raw: ["$4.11M", "27.9%", "+5.2%"], nm: [0.628, 0.781, 1], ok: 1 },
  { n: "South", raw: ["$3.64M", "26.1%", "+0.8%"], nm: [0.382, 0.669, 0], ok: 1 },
  { n: "West", raw: ["$2.91M", "15.4%", "+1.9%"], nm: [0, 0, 0.25], ok: 0 }
];

const W = [0.5, 0.3, 0.2];
const COL = ["#4C8DFF", "#7DAEFF", "#3B4C6B"];

/**
 * VERIDEX Page 7: Decision Intelligence View
 * Reconstructed with 100% exact visual, structural, and behavioral fidelity to veridex-prototype-v2.html P["decision"].
 */
export function DecisionsView({
  data,
  useMock = true,
  currentUser,
  onNavigate,
  onSelectInvestigation
}) {
  const [viewMode, setViewMode] = useState('norm'); // 'norm' | 'raw'
  const [approvalState, setApprovalState] = useState('pending'); // 'pending' | 'approved' | 'rejected'

  useEffect(() => {
    document.title = 'VERIDEX — Decision Intelligence';
  }, []);

  const invId = data?.investigation_id || data?.metadata?.investigation_id || 'inv_0142';
  const questionText = data?.question || 'What region should we prioritize for Q4?';
  const recTitle = data?.analysis?.recommendation?.action_title || 'Prioritize North region';
  const recRationale = data?.analysis?.summary || data?.analysis?.recommendation?.rationale || 'North ranks first on revenue and margin and clears the minimum-margin threshold. Its growth is moderate, and East is the closest alternative.';
  const recScore = data?.analysis?.rankings?.[0]?.score ? (data.analysis.rankings[0].score).toFixed(2) : '0.90';
  const robustStatus = data?.analysis?.robustness?.status || 'STABLE';
  const supportingEv = data?.analysis?.recommendation?.supporting_evidence_ids?.length ? data.analysis.recommendation.supporting_evidence_ids : ['E-01', 'E-02', 'E-03', 'E-05'];

  // Compute weighted contributions and total score for each candidate
  const processedCandidates = React.useMemo(() => {
    if (data?.analysis?.rankings && data.analysis.rankings.length > 0) {
      return data.analysis.rankings.map((r, idx) => ({
        n: r.candidate || r.name || `Candidate ${idx+1}`,
        raw: [String(r.revenue || '$4.82M'), String(r.margin || '31.4%'), String(r.growth || '+3.1%')],
        nm: r.normalized || [1 - idx * 0.2, 1 - idx * 0.2, 0.5],
        ok: 1,
        ct: [0.5 * (1 - idx * 0.2), 0.3 * (1 - idx * 0.2), 0.1],
        s: typeof r.score === 'number' ? r.score : 0.90 - idx * 0.15
      }));
    }
    const computed = C.map((c) => {
      const ct = c.nm.map((v, i) => v * W[i]);
      const s = ct.reduce((a, b) => a + b, 0);
      return { ...c, ct, s };
    });
    const eligible = computed.filter((c) => c.ok).sort((a, b) => b.s - a.s);
    const ineligible = computed.filter((c) => !c.ok);
    return [...eligible, ...ineligible];
  }, [data]);

  const handleNavigate = (targetView) => {
    if (onNavigate) {
      onNavigate(targetView);
    }
  };

  return (
    <div className="decision-intelligence-container">
      {/* Breadcrumb Context */}
      <div className="crumb">
        <a
          href="#"
          onClick={(e) => {
            e.preventDefault();
          }}
        >
          Decisions
        </a>{' '}
        / from {invId}
      </div>

      {/* Main Page Title & Subtitle */}
      <h1>{questionText}</h1>
      <p className="sub">{processedCandidates.length} candidates · {data?.analysis?.criteria_evaluated?.length || 3} criteria · 1 threshold condition</p>

      {/* Hero Recommendation Card */}
      <div className="card rec">
        <div>
          <span className="cap">Recommendation</span>
          <h2>{recTitle}</h2>
          <p>{recRationale}</p>
          <div className="eids">
            <span>Supported by</span>
            {supportingEv.map((evId) => (
              <span key={evId} className="eid">{evId}</span>
            ))}
          </div>
        </div>

        <div className="side">
          <span className="cap">Weighted score</span>
          <div className="score">{recScore}</div>
          <span className={`badge ${robustStatus === 'SENSITIVE' ? 'b-warn' : robustStatus === 'INSUFFICIENT_EVIDENCE' ? 'b-neu' : 'b-ok'}`}>
            {robustStatus === 'SENSITIVE' ? '◐ Sensitive' : robustStatus === 'INSUFFICIENT_EVIDENCE' ? '○ Insufficient' : '✓ Stable'}
          </span>
          <div style={{ marginTop: '8px' }}>
            <a
              style={{ color: 'var(--pr)', fontSize: '12.5px', cursor: 'pointer' }}
              onClick={(e) => {
                e.preventDefault();
                handleNavigate('robustness');
              }}
            >
              View robustness →
            </a>
          </div>
        </div>
      </div>

      {/* State-Driven Human Approval Card */}
      <div
        className="card appr"
        data-appr
        style={{
          marginBottom: '18px',
          borderLeftColor:
            approvalState === 'approved' ? '#4CB782' : approvalState === 'rejected' ? '#8B95A5' : '#4C8DFF'
        }}
      >
        {approvalState === 'pending' ? (
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
                type="button"
                className="apbtn"
                data-a="ev"
                onClick={() => handleNavigate('evidence')}
              >
                Review evidence
              </button>
              <button
                type="button"
                className="apbtn"
                data-a="rej"
                onClick={() => setApprovalState('rejected')}
              >
                Reject
              </button>
              <button
                type="button"
                className="apbtn pr"
                data-a="ok"
                onClick={() => setApprovalState('approved')}
              >
                Approve
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="ah">
              <span className="cap">Human approval</span>
              {approvalState === 'approved' ? (
                <span className="badge b-ok">Approved</span>
              ) : (
                <span className="badge b-neu">Rejected</span>
              )}
            </div>
            <p>
              <b>{approvalState === 'approved' ? 'Approved' : 'Rejected'}</b> by Gagandeep · Sep 30, 14:31
              <br />
              Recorded with 7 evidence items and a Stable robustness check.
            </p>
            <div className="ab">
              <button
                type="button"
                className="apbtn"
                data-a="undo"
                onClick={() => setApprovalState('pending')}
              >
                Undo
              </button>
            </div>
          </>
        )}
      </div>

      {/* Two-Column Grid Layout */}
      <div className="cols">
        {/* Left Column Stack */}
        <div className="stk">
          {/* Candidate Comparison Table Card */}
          <div className="card">
            <div className="hd">
              <span className="cap">Candidate comparison</span>
              <div className="seg">
                <button
                  type="button"
                  className={viewMode === 'norm' ? 'on' : ''}
                  data-v="norm"
                  onClick={() => setViewMode('norm')}
                >
                  Normalized
                </button>
                <button
                  type="button"
                  className={viewMode === 'raw' ? 'on' : ''}
                  data-v="raw"
                  onClick={() => setViewMode('raw')}
                >
                  Raw values
                </button>
              </div>
            </div>

            <div className="scroll">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Candidate</th>
                    <th className="r">
                      Revenue<small>weight 0.5</small>
                    </th>
                    <th className="r">
                      Margin<small>weight 0.3</small>
                    </th>
                    <th className="r">
                      Growth<small>weight 0.2</small>
                    </th>
                    <th className="r">Score</th>
                  </tr>
                </thead>
                <tbody id="tb">
                  {processedCandidates.map((c, i) => (
                    <tr
                      key={c.n}
                      className={`${i === 0 ? 'top' : ''} ${c.ok ? '' : 'inel'}`}
                    >
                      <td className="rk">{c.ok ? i + 1 : '—'}</td>
                      <td>
                        {c.n}
                        {!c.ok && <span className="badge b-neu">Below threshold</span>}
                      </td>
                      {viewMode === 'raw'
                        ? c.raw.map((x, idx) => (
                            <td key={idx} className="r m">
                              {x}
                            </td>
                          ))
                        : c.nm.map((x, idx) => (
                            <td key={idx} className="r m">
                              {x.toFixed(2)}
                            </td>
                          ))}
                      <td className="r m">{c.s.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Score Composition Card */}
          <div className="card">
            <div className="hd">
              <span className="cap">Score composition</span>
            </div>
            <div className="bars" id="bars">
              {processedCandidates.map((c) => (
                <div className="br" key={c.n}>
                  <span style={c.ok ? {} : { color: 'var(--mu)' }}>{c.n}</span>
                  <div className="t">
                    {c.ct.map((v, i) => (
                      <i
                        key={i}
                        style={{
                          width: `${v * 100}%`,
                          background: COL[i],
                          ...(c.ok ? {} : { opacity: 0.4 })
                        }}
                      />
                    ))}
                  </div>
                  <b>{c.s.toFixed(2)}</b>
                </div>
              ))}
            </div>
            <div className="lg">
              <span style={{ '--c': '#4C8DFF' }}>Revenue</span>
              <span style={{ '--c': '#7DAEFF' }}>Margin</span>
              <span style={{ '--c': '#3B4C6B' }}>Growth</span>
            </div>
          </div>
        </div>

        {/* Right Column Stack */}
        <div className="stk">
          {/* Criteria and Weights Card */}
          <div className="card">
            <div className="hd">
              <span className="cap">Criteria and weights</span>
            </div>
            <div className="crit">
              <div style={{ '--c': '#4C8DFF' }}>
                <div className="l">
                  <span>Revenue</span>
                  <b>0.5</b>
                </div>
                <div className="w">
                  <i style={{ width: '50%' }} />
                </div>
                <small>Higher is better · E-01</small>
              </div>

              <div style={{ '--c': '#7DAEFF' }}>
                <div className="l">
                  <span>Margin</span>
                  <b>0.3</b>
                </div>
                <div className="w">
                  <i style={{ width: '30%' }} />
                </div>
                <small>Higher is better · E-02</small>
              </div>

              <div style={{ '--c': '#3B4C6B' }}>
                <div className="l">
                  <span>Growth (QoQ)</span>
                  <b>0.2</b>
                </div>
                <div className="w">
                  <i style={{ width: '20%' }} />
                </div>
                <small>Higher is better · E-04</small>
              </div>
            </div>
          </div>

          {/* Threshold Conditions Card */}
          <div className="card">
            <div className="hd">
              <span className="cap">Threshold conditions</span>
            </div>
            <div className="th">
              <div>
                <span>Margin ≥ 20%</span>
                <span className="badge b-ok">3 pass</span>
              </div>
              <div style={{ color: 'var(--mu)', fontSize: '12.5px', justifyContent: 'flex-start' }}>
                West (15.4%) does not meet the threshold and is not eligible.
              </div>
            </div>
          </div>

          {/* Robustness Check Card */}
          <div className="card">
            <div className="hd">
              <span className="cap">Robustness check</span>
              <span className="badge b-ok">✓ Stable</span>
            </div>
            <div className="rbb">
              <p>Finding remains consistent across 3 alternate scenarios.</p>
              <div className="sc2">
                <div>
                  <span>Baseline</span>
                  <b>North</b>
                </div>
                <div>
                  <span>Margin ×2</span>
                  <b>North ✓</b>
                </div>
                <div>
                  <span>Revenue ×2</span>
                  <b>North ✓</b>
                </div>
                <div>
                  <span>Equal weights</span>
                  <b>North ✓</b>
                </div>
              </div>
              <div className="lm2">
                <span>
                  Lead margin <b>0.16</b>
                </span>
                <span>
                  Threshold <b>0.05</b>
                </span>
              </div>
              <a
                href="#"
                onClick={(e) => {
                  e.preventDefault();
                  handleNavigate('robustness');
                }}
              >
                View scenarios →
              </a>
            </div>
          </div>

          {/* Supporting Evidence Card */}
          <div className="card">
            <div className="hd">
              <span className="cap">Supporting evidence</span>
              <a
                style={{ color: 'var(--pr)', fontSize: '12.5px', cursor: 'pointer' }}
                href="#"
                onClick={(e) => {
                  e.preventDefault();
                  handleNavigate('evidence');
                }}
              >
                Explorer
              </a>
            </div>
            <div className="ev">
              <div>
                <span className="eid">E-01</span>
                <span className="badge b-fact">Fact</span>
                <span>Revenue by region</span>
              </div>
              <div>
                <span className="eid">E-03</span>
                <span className="badge b-der">Derived</span>
                <span>Margin vs average</span>
              </div>
              <div>
                <span className="eid">E-05</span>
                <span className="badge b-inf">Inference</span>
                <span>North as priority</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Footnote */}
      <p className="note">Sample data shown for illustration. Scores use min–max normalization across candidates.</p>
    </div>
  );
}
