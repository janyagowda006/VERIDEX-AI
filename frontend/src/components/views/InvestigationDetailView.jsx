import React, { useState } from 'react';
import { HumanReviewPanel } from '../HumanReviewPanel.jsx';
import './InvestigationDetailView.css';

/**
 * VERIDEX Page 4: Investigation Detail View
 * Reconstructed with 100% exact fidelity to veridex-prototype-v2.html reference specification.
 */
export function InvestigationDetailView({
  data,
  useMock = true,
  currentUser,
  onNavigate
}) {
  const [activeToc, setActiveToc] = useState('summary');

  // Question & metadata fallback matching prototype P["detail"]
  const invId = data?.metadata?.investigation_id || 'inv_0142';
  const questionText = data?.question || 'What region should we prioritize for Q4?';
  const answerHeading = data?.answer?.heading || 'Prioritize North for Q4.';
  const answerBody = data?.answer?.body || 'North has the highest revenue and margin of the four regions and stays first when the weighting is changed. East is the closest alternative.';

  const handleTocClick = (sectionId) => {
    setActiveToc(sectionId);
    const element = document.getElementById(sectionId);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const handleExportTrace = () => {
    const traceJson = JSON.stringify(data || { investigation_id: invId, question: questionText }, null, 2);
    const blob = new Blob([traceJson], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${invId}_trace.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="detail-view-container">
      {/* Main Content Center Column */}
      <div className="detail-main-area">
        {/* Breadcrumb */}
        <div className="crumb">
          <a onClick={() => onNavigate && onNavigate('history')} style={{ cursor: 'pointer' }}>
            History
          </a>{' '}
          / {invId}
        </div>

        {/* Header Title & Actions */}
        <div className="hd">
          <h1>{questionText}</h1>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button type="button" className="btn" onClick={handleExportTrace}>
              Export trace
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => onNavigate && onNavigate('workspace')}
            >
              Ask follow-up
            </button>
          </div>
        </div>

        {/* Metadata Line */}
        <div className="meta">
          <span>Today, 14:12</span>
          <span>Duration 3.4 s</span>
          <span>6 tool calls</span>
          <span>7 evidence</span>
          <span className="badge b-ok">✓ Stable</span>
        </div>

        {/* 1. Answer Card */}
        <div className="card ans" id="summary">
          <span className="cap">Answer</span>
          <h2>{answerHeading}</h2>
          <p>{answerBody}</p>
        </div>

        {/* 2. Investigation Timeline */}
        <details className="card sec" id="timeline" open>
          <summary onClick={() => setActiveToc('timeline')}>
            <h3>Investigation timeline</h3>
            <span className="ct">6 steps · 3.4 s</span>
          </summary>
          <div className="inner">
            <div className="step">
              <div className="rail">
                <span className="d" />
                <span className="l" />
              </div>
              <div className="st">
                <div>
                  <code>inspect_schema</code>
                  <span className="s">orders, regions</span>
                  <span className="du">0.2s</span>
                </div>
              </div>
            </div>

            <div className="step">
              <div className="rail">
                <span className="d" />
                <span className="l" />
              </div>
              <div className="st">
                <div>
                  <code>run_sql</code>
                  <span className="s">revenue by region</span>
                  <span className="du">0.6s</span>
                </div>
                <details open>
                  <summary>SQL and execution ▾</summary>
                  <pre>
                    <span className="k">SELECT</span> region, <span className="k">SUM</span>(revenue) <span className="k">AS</span> rev{"\n"}
                    <span className="k">FROM</span> orders <span className="k">WHERE</span> quarter <span className="k">IN</span> (<span className="n">'Q1'</span>,<span className="n">'Q2'</span>,<span className="n">'Q3'</span>){"\n"}
                    <span className="k">GROUP BY</span> region <span className="k">ORDER BY</span> rev <span class="k">DESC</span>;
                  </pre>
                  <div className="kv">
                    <span>query_hash</span>
                    <span>a3f9…c21e</span>
                    <span>timestamp</span>
                    <span>2026-09-30 14:12:03</span>
                    <span>rows_returned</span>
                    <span>4</span>
                    <span>mode</span>
                    <span>read-only</span>
                    <span>produced</span>
                    <span>E-01</span>
                  </div>
                </details>
              </div>
            </div>

            <div className="step">
              <div className="rail">
                <span className="d" />
                <span className="l" />
              </div>
              <div className="st">
                <div>
                  <code>run_sql</code>
                  <span className="s">margin by region</span>
                  <span className="du">0.7s</span>
                </div>
                <details>
                  <summary>SQL and execution ▸</summary>
                </details>
              </div>
            </div>

            <div className="step">
              <div className="rail">
                <span className="d" />
                <span className="l" />
              </div>
              <div className="st">
                <div>
                  <code>calculate_derived</code>
                  <span className="s">margin vs average</span>
                  <span className="du">0.1s</span>
                </div>
              </div>
            </div>

            <div className="step">
              <div className="rail">
                <span className="d" />
                <span className="l" />
              </div>
              <div className="st">
                <div>
                  <code>evaluate_decision</code>
                  <span className="s">4 candidates, 3 criteria</span>
                  <span className="du">0.3s</span>
                </div>
              </div>
            </div>

            <div className="step">
              <div className="rail">
                <span className="d" />
                <span className="l" />
              </div>
              <div className="st">
                <div>
                  <code>check_robustness</code>
                  <span className="s">3 alternate scenarios</span>
                  <span className="du">0.4s</span>
                </div>
              </div>
            </div>
          </div>
        </details>

        {/* 3. Claims -> Evidence */}
        <details className="card sec" id="claims" open>
          <summary onClick={() => setActiveToc('claims')}>
            <h3>Claims → evidence</h3>
            <span className="ct">3 supported</span>
          </summary>
          <div className="inner">
            <div className="map">
              <div className="c">
                <span className="badge b-fact">Fact</span> North generated the highest revenue at $4.82M.
              </div>
              <span className="a">→</span>
              <div className="e">
                <span className="eid">E-01</span>Revenue by region, Q1–Q3
              </div>

              <div className="c">
                <span className="badge b-der">Derived</span> North margin is 6.2 points above average.
              </div>
              <span className="a">→</span>
              <div className="e">
                <span className="eid">E-03</span>Margin vs regional average
              </div>

              <div className="c">
                <span className="badge b-inf">Inference</span> North is the strongest Q4 candidate.
              </div>
              <span className="a">→</span>
              <div className="e">
                <span className="eid">E-01</span>
                <span className="eid">E-03</span>
                <span className="eid">E-05</span>
              </div>
            </div>
          </div>
        </details>

        {/* 4. Evidence List */}
        <details className="card sec" id="evidence" open>
          <summary onClick={() => setActiveToc('evidence')}>
            <h3>Evidence</h3>
            <span className="ct">7 items</span>
          </summary>
          <div className="inner sc">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Type</th>
                  <th>Description</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="m">E-01</td>
                  <td><span className="badge b-fact">Fact</span></td>
                  <td>Revenue by region, Q1–Q3</td>
                  <td className="m">sql · 4 rows</td>
                </tr>
                <tr>
                  <td className="m">E-02</td>
                  <td><span className="badge b-fact">Fact</span></td>
                  <td>Margin by region, Q1–Q3</td>
                  <td className="m">sql · 4 rows</td>
                </tr>
                <tr>
                  <td className="m">E-03</td>
                  <td><span className="badge b-der">Derived</span></td>
                  <td>North margin vs regional average</td>
                  <td className="m">calc · from E-02</td>
                </tr>
                <tr>
                  <td className="m">E-05</td>
                  <td><span className="badge b-inf">Inference</span></td>
                  <td>North as priority candidate</td>
                  <td className="m">decision</td>
                </tr>
              </tbody>
            </table>
            <div style={{ marginTop: '8px', fontSize: '12.5px', color: 'var(--mu, #8B95A5)' }}>
              3 more items ·{' '}
              <a
                onClick={() => onNavigate && onNavigate('evidence')}
                style={{ color: 'var(--pr, #4C8DFF)', cursor: 'pointer' }}
              >
                Open in Evidence Explorer
              </a>
            </div>
          </div>
        </details>

        {/* 5. Derived Calculations */}
        <details className="card sec" id="derived">
          <summary onClick={() => setActiveToc('derived')}>
            <h3>Derived calculations</h3>
            <span className="ct">2</span>
          </summary>
          <div className="inner">
            <pre>
              delta = margin_north - avg_margin{"\n"}
              {"      "}= <span className="n">31.4</span> - <span className="n">25.2</span> = <span className="n">6.2</span> pts   <span style={{ color: 'var(--mu, #8B95A5)' }}># E-03, inputs: E-02</span>
            </pre>
          </div>
        </details>

        {/* 6. Decision Analysis */}
        <details className="card sec" id="decision" open>
          <summary onClick={() => setActiveToc('decision')}>
            <h3>Decision analysis</h3>
            <span className="ct">North ranked #1</span>
          </summary>
          <div className="inner sc">
            <table>
              <thead>
                <tr>
                  <th>Candidate</th>
                  <th className="r">Revenue · 0.5</th>
                  <th className="r">Margin · 0.3</th>
                  <th className="r">Growth · 0.2</th>
                  <th className="r">Score</th>
                </tr>
              </thead>
              <tbody>
                <tr className="top">
                  <td>1 · North</td>
                  <td className="m r">1.00</td>
                  <td className="m r">1.00</td>
                  <td className="m r">0.52</td>
                  <td className="m r">0.90</td>
                </tr>
                <tr>
                  <td>2 · East</td>
                  <td className="m r">0.63</td>
                  <td className="m r">0.78</td>
                  <td className="m r">1.00</td>
                  <td className="m r">0.75</td>
                </tr>
                <tr>
                  <td>3 · South</td>
                  <td className="m r">0.38</td>
                  <td className="m r">0.67</td>
                  <td className="m r">0.00</td>
                  <td className="m r">0.39</td>
                </tr>
                <tr>
                  <td>4 · West</td>
                  <td className="m r">0.00</td>
                  <td className="m r">0.00</td>
                  <td className="m r">0.25</td>
                  <td className="m r">0.05</td>
                </tr>
              </tbody>
            </table>
          </div>
        </details>

        {/* 7. Robustness */}
        <details className="card sec" id="robustness" open>
          <summary onClick={() => setActiveToc('robustness')}>
            <h3>Robustness</h3>
            <span className="ct">
              <span className="badge b-ok">✓ Stable</span>
            </span>
          </summary>
          <div className="inner">
            <div className="rob">
              <div className="card">
                <span className="cap">Baseline</span>
                <b>North #1</b>
              </div>
              <div className="card">
                <span className="cap">Scenarios tested</span>
                <b>3 alternate</b>
              </div>
              <div className="card">
                <span className="cap">Result</span>
                <b style={{ color: 'var(--ok, #4CB782)' }}>North #1 in 3 of 3</b>
              </div>
            </div>
            <div className="callout">
              Finding remains consistent across 3 alternate scenarios (margin ×2, revenue ×2, equal weights).
            </div>
          </div>
        </details>

        {/* 8. Human Approval */}
        <details className="card sec" id="approval" open>
          <summary onClick={() => setActiveToc('approval')}>
            <h3>Human approval</h3>
          </summary>
          <div className="inner" style={{ padding: 0 }}>
            <div className="appr" style={{ borderRadius: '0 0 10px 10px' }}>
              <HumanReviewPanel
                investigationId={invId}
                investigationStatus={data?.status || 'REQUIRES_REVIEW'}
                latestReview={data?.latest_review || null}
                reviewCount={data?.review_count || 0}
                useMock={useMock}
                currentUser={currentUser}
                ownerId={data?.owner_id || 'usr_analyst_01'}
              />
            </div>
          </div>
        </details>

        <p className="note">Sample data shown for illustration.</p>
      </div>

      {/* Right Table of Contents Sidebar (190px) */}
      <aside className="detail-toc-sidebar" aria-label="Table of Contents">
        <div className="cap">On this page</div>
        <a
          className={activeToc === 'summary' ? 'on' : ''}
          onClick={() => handleTocClick('summary')}
        >
          Answer
        </a>
        <a
          className={activeToc === 'timeline' ? 'on' : ''}
          onClick={() => handleTocClick('timeline')}
        >
          Timeline
        </a>
        <a
          className={activeToc === 'claims' ? 'on' : ''}
          onClick={() => handleTocClick('claims')}
        >
          Claims
        </a>
        <a
          className={activeToc === 'evidence' ? 'on' : ''}
          onClick={() => handleTocClick('evidence')}
        >
          Evidence
        </a>
        <a
          className={activeToc === 'derived' ? 'on' : ''}
          onClick={() => handleTocClick('derived')}
        >
          Calculations
        </a>
        <a
          className={activeToc === 'decision' ? 'on' : ''}
          onClick={() => handleTocClick('decision')}
        >
          Decision
        </a>
        <a
          className={activeToc === 'robustness' ? 'on' : ''}
          onClick={() => handleTocClick('robustness')}
        >
          Robustness
        </a>
        <a
          className={activeToc === 'approval' ? 'on' : ''}
          onClick={() => handleTocClick('approval')}
        >
          Approval
        </a>
      </aside>
    </div>
  );
}
