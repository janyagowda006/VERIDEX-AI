import React from 'react';
import './LandingPage.css';

/**
 * Public VERIDEX Landing Page (Page 1) & VERIDEX Design System v0.1 Specification.
 * Reconstructed with 100% exact fidelity to veridex-prototype-v2.html reference specification.
 */
export function LandingPage({ onNavigate }) {
  const handleGo = (target) => {
    if (onNavigate) onNavigate(target);
  };

  return (
    <div className="veridex-landing">
      <div className="wrap">
        {/* Navigation Bar (64px Height) */}
        <nav role="navigation" aria-label="Landing Header Navigation">
          <div
            className="logo"
            onClick={() => handleGo('landing')}
            style={{ cursor: 'pointer' }}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && handleGo('landing')}
          >
            <div className="mark" aria-hidden="true" />
            VERIDEX
          </div>
          <div className="links">
            <span>Product</span>
            <span onClick={() => handleGo('model')} style={{ cursor: 'pointer' }}>
              How it works
            </span>
            <span onClick={() => handleGo('model')} style={{ cursor: 'pointer' }}>
              Evidence model
            </span>
            <span>Docs</span>
          </div>
          <div className="stack">
            <button className="btn" type="button" onClick={() => handleGo('overview')}>
              Sign in
            </button>
            <button className="btn p" type="button" onClick={() => handleGo('overview')}>
              Open workspace
            </button>
          </div>
        </nav>

        {/* Hero Section */}
        <section className="hero" aria-label="Hero Section">
          <div>
            <div className="eyebrow">Evidence-First AI Decision Intelligence</div>
            <h1>Turn business data into decisions you can defend.</h1>
            <p className="sub">
              Ask a question in plain language. VERIDEX investigates your data with safe read-only SQL, traces every claim to its evidence, and tests whether the recommendation holds up.
            </p>
            <div className="cta">
              <button className="btn p" type="button" onClick={() => handleGo('ask')}>
                Start an investigation →
              </button>
              <button className="btn" type="button" onClick={() => handleGo('detail')}>
                See a sample trace
              </button>
            </div>
            <div className="trust">
              <span>Read-only queries</span>
              <span>Every claim linked to evidence</span>
              <span>Deterministic calculations</span>
            </div>
          </div>

          {/* Hero Product Preview Card */}
          <div className="card prev" aria-label="VERIDEX Product Preview">
            <div className="bar">
              <i aria-hidden="true" />
              <i aria-hidden="true" />
              <i aria-hidden="true" />
              &nbsp; veridex / investigations / inv_0142
            </div>
            <div className="q">
              <small>QUESTION</small>What region should we prioritize for Q4?
            </div>
            <div className="body">
              <div className="ans">
                <b>Prioritize North.</b> It leads on revenue and margin, and ranks first across the tested scenarios.
              </div>
              <div className="claim">
                <span className="badge b-fact">Fact</span>
                <span>North generated the highest revenue: $4.82M.</span>
                <span className="ev">E-01 · SQL</span>
              </div>
              <div className="claim">
                <span className="badge b-der">Derived</span>
                <span>North margin is 31.4%, 6.2 pts above the average.</span>
                <span className="ev">E-03 · calc</span>
              </div>
              <pre>
                <span className="k">SELECT</span> region, <span className="k">SUM</span>(revenue) <span className="k">AS</span> rev{"\n"}
                <span className="k">FROM</span> orders <span class="k">WHERE</span> quarter <span class="k">IN</span> (<span class="n">'Q1'</span>,<span class="n">'Q2'</span>,<span class="n">'Q3'</span>){"\n"}
                <span className="k">GROUP BY</span> region <span class="k">ORDER BY</span> rev <span class="k">DESC</span>;
              </pre>
              <div className="row">
                <div className="card rec">
                  <h4>Recommendation</h4>
                  <p>Prioritize North region</p>
                  <div style={{ color: 'var(--mu)', fontSize: '12.5px', marginTop: '4px' }}>
                    Score 0.90 · 3 supporting evidence items
                  </div>
                </div>
                <div className="card rob">
                  <h4>Robustness</h4>
                  <div className="st">✓ Stable</div>
                  <div style={{ color: 'var(--mu)', fontSize: '12.5px' }}>
                    Unchanged under tested scenario.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Horizontal Answer → Approval Chain */}
        <section className="chain" aria-label="Evidence Chain Pipeline">
          <h2>Every important answer has a reason behind it</h2>
          <div className="steps">
            <div className="step">
              <div className="dot" aria-hidden="true" />
              <b>Answer</b>
              <span>What was concluded</span>
            </div>
            <div className="step">
              <div className="dot" aria-hidden="true" />
              <b>Claim</b>
              <span>Each assertion, isolated</span>
            </div>
            <div className="step">
              <div className="dot" aria-hidden="true" />
              <b>Evidence</b>
              <span>SQL, rows, source</span>
            </div>
            <div className="step">
              <div className="dot" aria-hidden="true" />
              <b>Calculation</b>
              <span>Deterministic code</span>
            </div>
            <div className="step">
              <div className="dot" aria-hidden="true" />
              <b>Decision</b>
              <span>Criteria and ranking</span>
            </div>
            <div className="step">
              <div className="dot" aria-hidden="true" />
              <b>Robustness</b>
              <span>Does it survive change?</span>
            </div>
            <div className="step">
              <div className="dot" aria-hidden="true" />
              <b>Approval</b>
              <span>You make the call</span>
            </div>
          </div>
        </section>

        {/* Three Feature Cards */}
        <section className="grid3" aria-label="Core Capabilities">
          <div className="card">
            <div className="tag">AI FOR REASONING</div>
            <h3>Investigates, doesn't guess</h3>
            <p>
              The model plans the investigation and calls a safe read-only SQL tool. Real tool calls, shown as they happened.
            </p>
          </div>
          <div className="card">
            <div className="tag">CODE FOR CORRECTNESS</div>
            <h3>Numbers computed, not written</h3>
            <p>
              Totals, margins and rankings come from deterministic calculations, never from model arithmetic.
            </p>
          </div>
          <div className="card">
            <div className="tag">DECISIONS YOU CAN DEFEND</div>
            <h3>Tested against alternatives</h3>
            <p>
              Recommendations are re-scored under alternate assumptions and labeled stable, sensitive, or under-evidenced.
            </p>
          </div>
        </section>

        {/* Final CTA Section */}
        <section className="final" aria-label="Final Call to Action">
          <h2>Ask a question. Inspect the proof.</h2>
          <button className="btn p" type="button" onClick={() => handleGo('ask')}>
            Start an investigation →
          </button>
        </section>

        {/* Landing Footer */}
        <footer role="contentinfo">
          <span>© 2026 VERIDEX</span>
          <span>Evidence-First AI Decision Intelligence</span>
        </footer>
      </div>

      {/* VERIDEX Design System v0.1 Specification Section */}
      <section className="ds" aria-label="VERIDEX Design System Specification">
        <div className="wrap">
          <h2>VERIDEX Design System v0.1</h2>
          <p className="lead">Dark-first, restrained, evidence-led. Color carries meaning only.</p>
          <div className="dsg">
            <div className="card">
              <h3>Color · surfaces & brand</h3>
              <div className="sw">
                <div><i style={{ background: '#0A0C10' }} />bg #0A0C10</div>
                <div><i style={{ background: '#11141A' }} />s1 #11141A</div>
                <div><i style={{ background: '#181C24' }} />s2 #181C24</div>
                <div><i style={{ background: '#242A35' }} />line #242A35</div>
                <div><i style={{ background: '#E8ECF2' }} />text #E8ECF2</div>
                <div><i style={{ background: '#8B95A5' }} />muted #8B95A5</div>
                <div><i style={{ background: '#4C8DFF' }} />primary #4C8DFF</div>
              </div>
            </div>

            <div className="card">
              <h3>Color · semantic</h3>
              <div className="sw">
                <div><i style={{ background: '#5B9DFF' }} />fact</div>
                <div><i style={{ background: '#9A87F5' }} />derived</div>
                <div><i style={{ background: '#E0A94A' }} />inference / sensitive</div>
                <div><i style={{ background: '#4CB782' }} />stable</div>
                <div><i style={{ background: '#8B95A5' }} />insufficient</div>
                <div><i style={{ background: '#D46A6A' }} />error only</div>
              </div>
            </div>

            <div className="card">
              <h3>Evidence badges</h3>
              <div className="stack">
                <span className="badge b-fact">Fact</span>
                <span className="badge b-der">Derived fact</span>
                <span className="badge b-inf">Inference</span>
              </div>
              <ul className="li" style={{ marginTop: '12px' }}>
                <li><b>Fact</b> — directly observed</li>
                <li><b>Derived fact</b> — calculated from evidence</li>
                <li><b>Inference</b> — reasoned conclusion</li>
              </ul>
            </div>

            <div className="card">
              <h3>Robustness states (analytical, not errors)</h3>
              <ul className="li">
                <li><span className="badge b-ok">✓ Stable</span>&nbsp; Recommendation unchanged.</li>
                <li><span className="badge b-warn">◐ Sensitive</span>&nbsp; Changes under an alternate scenario.</li>
                <li><span className="badge b-neu">○ Insufficient evidence</span>&nbsp; Cannot establish robustness.</li>
              </ul>
            </div>

            <div className="card">
              <h3>Typography</h3>
              <div style={{ fontSize: '28px', fontWeight: '650', letterSpacing: '-.02em' }}>Inter — headings & UI</div>
              <div style={{ color: 'var(--mu)', margin: '6px 0 10px' }}>Display 52/56 · H2 32 · H3 17 · Body 15/1.55 · Caption 12–13</div>
              <div style={{ font: '14px var(--mono)' }}>JetBrains Mono — SQL, IDs, <span className="n">4,820,311</span></div>
            </div>

            <div className="card">
              <h3>Table · decision ranking</h3>
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Region</th>
                    <th className="num">Revenue</th>
                    <th className="num">Margin</th>
                    <th className="num">Score</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="top">
                    <td>1</td>
                    <td>North</td>
                    <td className="num">4.82M</td>
                    <td className="num">31.4%</td>
                    <td className="num">0.87</td>
                  </tr>
                  <tr>
                    <td>2</td>
                    <td>East</td>
                    <td className="num">4.11M</td>
                    <td className="num">27.9%</td>
                    <td className="num">0.74</td>
                  </tr>
                  <tr>
                    <td>3</td>
                    <td>South</td>
                    <td className="num">3.64M</td>
                    <td className="num">26.1%</td>
                    <td className="num">0.61</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="card">
              <h3>Buttons · spacing · shape</h3>
              <div className="stack">
                <button className="btn p" type="button">Primary</button>
                <button className="btn" type="button">Secondary</button>
              </div>
              <ul className="li" style={{ marginTop: '12px' }}>
                <li><b>Grid</b> 4px base: 4·8·12·16·24·32·56</li>
                <li><b>Radius</b> 6–8px controls, 10px cards</li>
                <li><b>Depth</b> 1px borders first, shadow only for overlays</li>
              </ul>
            </div>

            <div className="card">
              <h3>Signature pattern</h3>
              <div className="stack" style={{ font: '12px var(--mono)', color: 'var(--mu)' }}>
                Answer → Claim → Evidence → Calculation → Decision → Robustness
              </div>
              <ul className="li" style={{ marginTop: '12px' }}>
                <li><b>Claim row</b> — badge + text + dashed evidence-ID link</li>
                <li><b>Evidence link</b> — opens right drawer with SQL, rows, limitations</li>
                <li><b>Disclosure</b> — answer first; “Why?” then “View evidence”</li>
              </ul>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
