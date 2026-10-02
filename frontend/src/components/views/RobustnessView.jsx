import React, { useState, useEffect } from 'react';
import './RobustnessView.css';

// Prototype baseline data & normalization math
const N_CANDIDATES = {
  North: [1, 1, 0.523],
  East: [0.628, 0.781, 1],
  South: [0.382, 0.669, 0]
};

const BASELINE_WEIGHTS = [0.5, 0.3, 0.2];

const normWeights = (w) => {
  const tot = w.reduce((a, b) => a + b, 0);
  return w.map((x) => x / tot);
};

const rankCandidates = (w) => {
  const nw = normWeights(w);
  return Object.entries(N_CANDIDATES)
    .map(([k, v]) => ({
      k,
      s: v.reduce((a, x, i) => a + x * nw[i], 0)
    }))
    .sort((a, b) => b.s - a.s);
};

const BASELINE_RANK = rankCandidates(BASELINE_WEIGHTS);
const BASELINE_POS = Object.fromEntries(BASELINE_RANK.map((r, i) => [r.k, i + 1]));
const BASELINE_SCORE = Object.fromEntries(BASELINE_RANK.map((r) => [r.k, r.s]));

const SCENARIOS = {
  m: { t: "Margin weight ×2", d: "Margin matters more than revenue growth.", w: [0.5, 0.6, 0.2], ch: 1 },
  g: { t: "Growth weight ×3", d: "Recent momentum matters much more.", w: [0.5, 0.3, 0.6], ch: 2 },
  r: { t: "Revenue weight ×2", d: "Scale matters more than margin.", w: [1, 0.3, 0.2], ch: 0 },
  e: { t: "Equal weights", d: "All criteria count the same.", w: [1, 1, 1], ch: -1 }
};

const LEAD_MARGIN_LINE = {
  STABLE: 'Lead margin 0.16 · minimum required 0.05',
  SENSITIVE: 'Lead flips by 0.03 in one scenario · minimum required 0.05',
  INSUFFICIENT_EVIDENCE: null
};

const CONFIGS = {
  STABLE: {
    c: "var(--ok)",
    b: "b-ok",
    l: "✓ Stable",
    p: "Finding remains consistent across 3 alternate scenarios.",
    sc: ["m", "r", "e"],
    next: "You can act on this recommendation. Conclusions stay the same across the tested assumptions."
  },
  SENSITIVE: {
    c: "var(--warn)",
    b: "b-warn",
    l: "◐ Sensitive",
    p: "The recommended candidate changes under the alternate scenario.",
    sc: ["m", "g"],
    next: "North leads on the baseline weights, but East is ahead if growth is weighted heavily. Confirm how much weight growth deserves before committing."
  },
  INSUFFICIENT_EVIDENCE: {
    c: "var(--neu)",
    b: "b-neu",
    l: "○ Insufficient evidence",
    p: "Insufficient evidence to determine robustness.",
    sc: [],
    next: "Treat the recommendation as provisional. More periods of growth data would allow scenarios to be tested."
  }
};

const fmt = (x) => x.toFixed(2);

/**
 * VERIDEX Page 8: Robustness Analysis View
 * Reconstructed with 100% exact visual, structural, mathematical, and behavioral fidelity to veridex-prototype-v2.html P["robustness"].
 */
export function RobustnessView({ onNavigate }) {
  const [selectedStatus, setSelectedStatus] = useState('STABLE');

  useEffect(() => {
    document.title = 'VERIDEX — Robustness Analysis';
  }, []);

  const activeCfg = CONFIGS[selectedStatus] || CONFIGS.STABLE;

  const handleNavigate = (targetView) => {
    if (onNavigate) {
      onNavigate(targetView);
    }
  };

  const renderScenarioCard = (key) => {
    const s = SCENARIOS[key];
    if (!s) return null;

    const r = rankCandidates(s.w);
    const weightLabels = ["Revenue", "Margin", "Growth"];
    const n = normWeights(s.w);
    const topCandidate = r[0].k;
    const isChanged = topCandidate !== BASELINE_RANK[0].k;

    return (
      <div key={key} className="card scn">
        <div className="sh">
          <div>
            <span className="cap">Scenario</span>
            <h3>{s.t}</h3>
            <p>{s.d}</p>
            <div className="w">
              {weightLabels.map((lbl, idx) => (
                <span key={idx} className={idx === s.ch ? 'ch' : ''}>
                  {lbl} {fmt(n[idx])}
                </span>
              ))}
            </div>
          </div>
          <span className={`badge ${isChanged ? 'b-warn' : 'b-ok'}`}>
            {isChanged ? `${topCandidate} becomes #1` : `${BASELINE_RANK[0].k} remains #1`}
          </span>
        </div>

        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>Rank</th>
                <th>Candidate</th>
                <th className="r">Baseline</th>
                <th className="r">Scenario score</th>
                <th className="r">Shift</th>
              </tr>
            </thead>
            <tbody>
              {r.map((x, i) => {
                const shift = BASELINE_POS[x.k] - (i + 1);
                const isRowChanged = BASELINE_POS[x.k] !== i + 1;
                return (
                  <tr key={x.k} className={isRowChanged ? 'chg' : ''}>
                    <td className="m">{i + 1}</td>
                    <td>{x.k}</td>
                    <td className="r m">
                      #{BASELINE_POS[x.k]} · {fmt(BASELINE_SCORE[x.k])}
                    </td>
                    <td className="r m">
                      <span
                        className="mini"
                        style={{
                          width: `${x.s * 70}px`,
                          background: isChanged && i === 0 ? 'var(--warn)' : 'var(--pr)'
                        }}
                      />
                      {fmt(x.s)}
                    </td>
                    <td className={`r m ${shift > 0 ? 'up' : shift < 0 ? 'dn' : 'eq'}`}>
                      {shift > 0 ? `▲ ${shift}` : shift < 0 ? `▼ ${-shift}` : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  return (
    <div className="robustness-page-container">
      {/* Breadcrumb Navigation */}
      <div className="crumb">
        <a
          href="#"
          onClick={(e) => {
            e.preventDefault();
            handleNavigate('decision');
          }}
        >
          Decisions
        </a>{' '}
        /{' '}
        <a
          href="#"
          onClick={(e) => {
            e.preventDefault();
            handleNavigate('decision');
          }}
        >
          Prioritize North region
        </a>{' '}
        / Robustness
      </div>

      {/* Top Header & Demo State Switch */}
      <div className="top">
        <div>
          <h1>Robustness analysis</h1>
          <p className="sub">Does the recommendation survive different assumptions?</p>
        </div>
        <div className="demo">
          Preview state
          <div className="seg" id="sw">
            <button
              type="button"
              className={selectedStatus === 'STABLE' ? 'on' : ''}
              data-s="STABLE"
              onClick={() => setSelectedStatus('STABLE')}
            >
              Stable
            </button>
            <button
              type="button"
              className={selectedStatus === 'SENSITIVE' ? 'on' : ''}
              data-s="SENSITIVE"
              onClick={() => setSelectedStatus('SENSITIVE')}
            >
              Sensitive
            </button>
            <button
              type="button"
              className={selectedStatus === 'INSUFFICIENT_EVIDENCE' ? 'on' : ''}
              data-s="INSUFFICIENT_EVIDENCE"
              onClick={() => setSelectedStatus('INSUFFICIENT_EVIDENCE')}
            >
              Insufficient
            </button>
          </div>
        </div>
      </div>

      {/* Dynamic Output Container */}
      <div id="out">
        {/* Status Hero Card */}
        <div className="card status" style={{ '--c': activeCfg.c }}>
          <div>
            <span className="cap">Robustness check</span>
            <div className="st">{activeCfg.l}</div>
            <p>{activeCfg.p}</p>
            {LEAD_MARGIN_LINE[selectedStatus] && (
              <div className="lm">{LEAD_MARGIN_LINE[selectedStatus]}</div>
            )}
          </div>

          <div className="cmp">
            {selectedStatus === 'STABLE' && (
              <>
                <div className="box">
                  <span className="cap">Baseline</span>
                  <b>North #1</b>
                </div>
                <span className="ar">→</span>
                <div className="box">
                  <span className="cap">All 3 scenarios</span>
                  <b>North #1</b>
                </div>
              </>
            )}

            {selectedStatus === 'SENSITIVE' && (
              <>
                <div className="box">
                  <span className="cap">Baseline</span>
                  <b>North #1</b>
                </div>
                <span className="ar">→</span>
                <div className="box" style={{ borderColor: '#6E5526' }}>
                  <span className="cap">Growth ×3</span>
                  <b style={{ color: 'var(--warn)' }}>East #1</b>
                </div>
              </>
            )}

            {selectedStatus === 'INSUFFICIENT_EVIDENCE' && (
              <>
                <div className="box">
                  <span className="cap">Baseline</span>
                  <b>North #1</b>
                </div>
                <span className="ar">→</span>
                <div className="box">
                  <span className="cap">Scenario</span>
                  <b style={{ color: 'var(--mu)' }}>Not tested</b>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Section Header */}
        <div className="sec">
          <span className="cap">
            {activeCfg.sc.length > 0
              ? `${activeCfg.sc.length} alternate scenario${activeCfg.sc.length > 1 ? 's' : ''}`
              : 'Scenarios'}
          </span>
          <span className="badge b-mu">Baseline: Revenue 0.50 · Margin 0.30 · Growth 0.20</span>
        </div>

        {/* Alternate Scenarios or Empty Box */}
        {selectedStatus === 'INSUFFICIENT_EVIDENCE' ? (
          <div className="card scn">
            <div className="empty">
              No alternate scenario could be evaluated. Only one quarter of growth data is available, so a growth-weighted scenario would not be reliable.
            </div>
          </div>
        ) : (
          activeCfg.sc.map((key) => renderScenarioCard(key))
        )}

        {/* Outliers Section (only in STABLE and SENSITIVE) */}
        {selectedStatus !== 'INSUFFICIENT_EVIDENCE' && (
          <>
            <div className="sec">
              <span className="cap">Outliers</span>
            </div>
            <div className="grid2">
              <div className="card pad">
                <span className="cap">Outlier sensitivity</span>
                <h3>Largest single order removed</h3>
                <p>
                  Excluding North's largest order (−$0.31M, 6.4% of its revenue) leaves North first. Its lead over East narrows from 0.16 to 0.10.
                </p>
                <div className="kv">
                  <span>Result</span>
                  <span>North #1 · unchanged</span>
                </div>
              </div>

              <div className="card pad">
                <span className="cap">Metric changes</span>
                <h3>North revenue $4.82M → $4.51M</h3>
                <p>East, South and West are unaffected by this exclusion.</p>
                <div className="kv">
                  <span>Margin</span>
                  <span>31.4% → 31.6%</span>
                  <span>Score</span>
                  <span>0.90 → 0.90</span>
                </div>
              </div>
            </div>
          </>
        )}

        {/* "What this means" Callout Box */}
        <div className="next" style={{ '--c': activeCfg.c }}>
          <span className="cap">What this means</span>
          <div style={{ marginTop: '4px' }}>{activeCfg.next}</div>
        </div>
      </div>

      {/* Footnote */}
      <p className="note">Sample data shown for illustration. The state switch above is a design preview control, not a product feature.</p>
    </div>
  );
}
