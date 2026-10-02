import React from 'react';
import './EvidenceModelView.css';

/**
 * Public VERIDEX Evidence Model Page (Page 2 - P["model"]).
 * Reconstructed with 100% exact fidelity to veridex-prototype-v2.html reference specification.
 */
export function EvidenceModelView({ onNavigate }) {
  const handleGo = (target) => {
    if (onNavigate) onNavigate(target);
  };

  return (
    <div className="veridex-evidence-model">
      <div className="wrap">
        {/* Navigation Bar (64px Height, 3 Links) */}
        <nav role="navigation" aria-label="Evidence Model Navigation">
          <div
            className="logo"
            onClick={() => handleGo('landing')}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && handleGo('landing')}
          >
            <div className="mark" aria-hidden="true" />
            VERIDEX
          </div>
          <div className="links">
            <span onClick={() => handleGo('landing')}>Product</span>
            <span>How it works</span>
            <span className="on">Evidence model</span>
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
          <div className="eyebrow">The evidence model</div>
          <h1>AI for reasoning. Code for correctness.</h1>
          <p className="sub">
            VERIDEX never asks you to trust a sentence. Every answer is broken into claims, and every claim is tied to evidence of a known kind.
          </p>
        </section>

        {/* How It Works Section */}
        <section className="sec" aria-label="How It Works Pipeline">
          <h2>How it works</h2>
          <p>Four steps, with a human making the final call.</p>
          <div className="loop">
            <div className="card">
              <span className="n">01</span>
              <b>Investigate</b>
              <span>The AI plans the investigation and asks your data questions with safe read-only SQL.</span>
            </div>
            <div className="card">
              <span className="n">02</span>
              <b>Verify</b>
              <span>Deterministic code runs the queries, calculations, rankings and robustness checks.</span>
            </div>
            <div className="card">
              <span className="n">03</span>
              <b>Trace</b>
              <span>Every claim links to the evidence, SQL and rows behind it.</span>
            </div>
            <div className="card">
              <span className="n">04</span>
              <b>Approve</b>
              <span>You review the evidence and robustness, then approve or reject.</span>
            </div>
          </div>
        </section>

        {/* Three Kinds of Evidence Section */}
        <section className="sec" aria-label="Three Kinds of Evidence Taxonomy">
          <h2>Three kinds of evidence</h2>
          <p>Each piece of evidence says what it is and where it came from.</p>

          <div className="card et" style={{ '--c': 'var(--fact)' }}>
            <div>
              <span className="badge b-fact">Fact</span>
              <h3>Observed directly</h3>
            </div>
            <div>
              <span className="cap">What it is</span>
              <p>A value read straight from your data.</p>
            </div>
            <div>
              <span className="cap">Produced by</span>
              <p>A read-only SQL query.</p>
            </div>
            <div>
              <span className="cap">Example</span>
              <p>North generated $4.82M in revenue.</p>
              <code>E-01 · SQL + rows</code>
            </div>
          </div>

          <div className="ar">▼ used as input</div>

          <div className="card et" style={{ '--c': 'var(--der)' }}>
            <div>
              <span className="badge b-der">Derived fact</span>
              <h3>Calculated from evidence</h3>
            </div>
            <div>
              <span className="cap">What it is</span>
              <p>A number computed from verified facts.</p>
            </div>
            <div>
              <span className="cap">Produced by</span>
              <p>Deterministic code, not the model.</p>
            </div>
            <div>
              <span className="cap">Example</span>
              <p>North margin is 6.2 points above average.</p>
              <code>E-03 · formula + inputs</code>
            </div>
          </div>

          <div className="ar">▼ used as input</div>

          <div className="card et" style={{ '--c': 'var(--inf)' }}>
            <div>
              <span className="badge b-inf">Inference</span>
              <h3>Reasoned conclusion</h3>
            </div>
            <div>
              <span className="cap">What it is</span>
              <p>An interpretation, not a raw database fact.</p>
            </div>
            <div>
              <span className="cap">Produced by</span>
              <p>AI reasoning over the evidence above.</p>
            </div>
            <div>
              <span className="cap">Example</span>
              <p>North is the strongest candidate for Q4.</p>
              <code>E-05 · assumptions shown</code>
            </div>
          </div>
        </section>

        {/* Path Flow Section */}
        <section className="sec" aria-label="Path Pipeline Flow">
          <h2>Every answer follows the same path</h2>
          <p>The same chain appears on every investigation.</p>
          <div className="flow">
            <span>Answer</span>
            <i aria-hidden="true">→</i>
            <span>Claim</span>
            <i aria-hidden="true">→</i>
            <span>Evidence</span>
            <i aria-hidden="true">→</i>
            <span>Calculation</span>
            <i aria-hidden="true">→</i>
            <span>Decision</span>
            <i aria-hidden="true">→</i>
            <span>Robustness</span>
            <i aria-hidden="true">→</i>
            <span className="h">Human approval</span>
          </div>
        </section>

        {/* Final CTA Section */}
        <section className="final" aria-label="Final Call to Action">
          <h2>See the proof behind an answer.</h2>
          <button className="btn p" type="button" onClick={() => handleGo('ask')}>
            Start an investigation →
          </button>
        </section>
      </div>
    </div>
  );
}
