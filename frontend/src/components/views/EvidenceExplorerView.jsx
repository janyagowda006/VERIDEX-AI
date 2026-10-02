import React, { useState, useEffect } from 'react';
import './EvidenceExplorerView.css';

// Syntax highlighted SQL snippets matching prototype
const SQL1 = `<span class="k">SELECT</span> region, <span class="k">SUM</span>(revenue) <span class="k">AS</span> rev
<span class="k">FROM</span> orders
<span class="k">WHERE</span> quarter <span class="k">IN</span> (<span class="n">'Q1'</span>,<span class="n">'Q2'</span>,<span class="n">'Q3'</span>)
<span class="k">GROUP BY</span> region <span class="k">ORDER BY</span> rev <span class="k">DESC</span>;`;

const SQL2 = `<span class="k">SELECT</span> region, <span class="k">ROUND</span>(<span class="k">SUM</span>(profit)*<span class="n">100.0</span>/<span class="k">SUM</span>(revenue),<span class="n">1</span>) <span class="k">AS</span> margin
<span class="k">FROM</span> orders <span class="k">WHERE</span> quarter <span class="k">IN</span> (<span class="n">'Q1'</span>,<span class="n">'Q2'</span>,<span class="n">'Q3'</span>)
<span class="k">GROUP BY</span> region;`;

const SQL3 = `<span class="k">SELECT</span> region, <span class="k">COUNT</span>(*) <span class="k">FILTER</span> (<span class="k">WHERE</span> returned)*<span class="n">1.0</span>/<span class="k">COUNT</span>(*) <span class="k">AS</span> rate
<span class="k">FROM</span> orders <span class="k">WHERE</span> quarter=<span class="n">'Q3'</span> <span class="k">GROUP BY</span> region;`;

// Authoritative prototype dataset D (veridex-prototype-v2.html P["evidence"])
const D = [
  {
    id: "E-01",
    t: "Fact",
    bc: "b-fact",
    d: "Revenue by region, Q1–Q3",
    s: "sql · orders",
    inv: "inv_0142",
    ts: "Sep 30 14:12",
    u: 2,
    sql: SQL1,
    cols: ["region", "rev"],
    rows: [["North", "4,820,311", 1], ["East", "4,110,942"], ["South", "3,640,118"], ["West", "2,905,570"]],
    meta: [["source_type", "sql_query"], ["query_hash", "a3f9…c21e"], ["rows", "4"], ["duration", "0.6 s"], ["mode", "read-only"]],
    calc: null,
    lim: "Covers Q1–Q3 only. Q4 is not in the data.",
    cl: ["North generated the highest revenue at $4.82M."]
  },
  {
    id: "E-02",
    t: "Fact",
    bc: "b-fact",
    d: "Margin by region, Q1–Q3",
    s: "sql · orders",
    inv: "inv_0142",
    ts: "Sep 30 14:12",
    u: 1,
    sql: SQL2,
    cols: ["region", "margin %"],
    rows: [["North", "31.4", 1], ["East", "27.9"], ["South", "26.1"], ["West", "15.4"]],
    meta: [["source_type", "sql_query"], ["query_hash", "7be2…09d4"], ["rows", "4"], ["duration", "0.7 s"], ["mode", "read-only"]],
    calc: null,
    lim: "Margin uses recorded profit; returns are not netted out.",
    cl: ["North margin is 6.2 points above average."]
  },
  {
    id: "E-03",
    t: "Derived",
    bc: "b-der",
    d: "North margin vs regional average",
    s: "calculation · from E-02",
    inv: "inv_0142",
    ts: "Sep 30 14:12",
    u: 1,
    sql: null,
    cols: ["input", "value"],
    rows: [["North margin", "31.4", 1], ["Average margin", "25.2"], ["Delta", "6.2 pts"]],
    meta: [["source_type", "calculation"], ["depends_on", "E-02"], ["method", "deterministic"]],
    calc: `delta = <span class="n">31.4</span> - <span class="n">25.2</span> = <span class="n">6.2</span> pts`,
    lim: "Unweighted average across regions.",
    cl: ["North margin is 6.2 points above average."]
  },
  {
    id: "E-05",
    t: "Inference",
    bc: "b-inf",
    d: "North as priority candidate for Q4",
    s: "decision analysis",
    inv: "inv_0142",
    ts: "Sep 30 14:12",
    u: 1,
    sql: null,
    cols: ["criterion", "weight"],
    rows: [["Revenue", "0.5"], ["Margin", "0.3"], ["Growth", "0.2"]],
    meta: [["source_type", "decision_analysis"], ["depends_on", "E-01, E-03, E-04"]],
    calc: `North <span class="n">0.90</span> &gt; East <span class="n">0.75</span> &gt; South <span class="n">0.39</span> &gt; West <span class="n">0.05</span>`,
    lim: "Weights are configured assumptions, not observed data.",
    cl: ["North is the strongest candidate for Q4."]
  },
  {
    id: "E-11",
    t: "Fact",
    bc: "b-fact",
    d: "Return rate by region, Q3",
    s: "sql · returns",
    inv: "inv_0139",
    ts: "Sep 27 10:05",
    u: 0,
    sql: SQL3,
    cols: ["region", "rate"],
    rows: [["South", "0.062", 1], ["North", "0.041"]],
    meta: [["source_type", "sql_query"], ["query_hash", "c410…5aa7"], ["rows", "4"]],
    calc: null,
    lim: "Only one quarter available; trend cannot be established.",
    cl: []
  }
];

/**
 * VERIDEX Page 6: Evidence Explorer View
 * Reconstructed with 100% exact visual, structural, and behavioral fidelity to veridex-prototype-v2.html P["evidence"].
 */
export function EvidenceExplorerView({
  onNavigate,
  onSelectInvestigation
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('ALL');
  const [selectedId, setSelectedId] = useState('E-01');
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [drawerItemId, setDrawerItemId] = useState('E-01');

  useEffect(() => {
    document.title = 'VERIDEX — Evidence Explorer';
  }, []);

  // Filter evidence items based on chip and search input
  const filteredList = D.filter((e) => {
    const matchesType = typeFilter === 'ALL' || e.t === typeFilter;
    const q = searchQuery.trim().toLowerCase();
    const matchesQuery = !q || e.d.toLowerCase().includes(q) || e.id.toLowerCase().includes(q);
    return matchesType && matchesQuery;
  });

  // Drawer item content persists even when drawer is closed (.h)
  const activeDrawerItem = D.find((item) => item.id === drawerItemId) || D[0];

  const handleOpenRow = (id) => {
    setSelectedId(id);
    setDrawerItemId(id);
    setDrawerOpen(true);
  };

  const handleCloseDrawer = () => {
    setDrawerOpen(false);
    setSelectedId(null);
  };

  const handleOpenInv = (invId) => {
    if (onSelectInvestigation) {
      onSelectInvestigation(invId);
    }
    if (onNavigate) {
      onNavigate('detail');
    }
  };

  return (
    <div className="evidence-explorer-container">
      <h1>Evidence Explorer</h1>
      <p className="sub">Every fact, calculation and inference behind your answers, with its source.</p>

      {/* Toolbar */}
      <div className="tb">
        <input
          className="search"
          id="q"
          placeholder="Search description or ID…"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        <button
          type="button"
          className={`chip ${typeFilter === 'ALL' ? 'on' : ''}`}
          data-t="ALL"
          onClick={() => setTypeFilter('ALL')}
        >
          All
        </button>
        <button
          type="button"
          className={`chip ${typeFilter === 'Fact' ? 'on' : ''}`}
          data-t="Fact"
          onClick={() => setTypeFilter('Fact')}
        >
          Fact
        </button>
        <button
          type="button"
          className={`chip ${typeFilter === 'Derived' ? 'on' : ''}`}
          data-t="Derived"
          onClick={() => setTypeFilter('Derived')}
        >
          Derived fact
        </button>
        <button
          type="button"
          className={`chip ${typeFilter === 'Inference' ? 'on' : ''}`}
          data-t="Inference"
          onClick={() => setTypeFilter('Inference')}
        >
          Inference
        </button>

        <span className="sel">Investigation: All ▾</span>
        <span className="cnt" id="cnt">
          {filteredList.length} of {D.length} items
        </span>
      </div>

      {/* Evidence Table */}
      <div className="card scroll">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Type</th>
              <th>Description</th>
              <th>Source</th>
              <th>Investigation</th>
              <th>Timestamp</th>
              <th>Used by</th>
            </tr>
          </thead>
          <tbody id="tb">
            {filteredList.length > 0 ? (
              filteredList.map((e) => (
                <tr
                  key={e.id}
                  data-id={e.id}
                  className={selectedId === e.id ? 'on' : ''}
                  onClick={() => handleOpenRow(e.id)}
                >
                  <td className="id">{e.id}</td>
                  <td>
                    <span className={`badge ${e.bc}`}>{e.t}</span>
                  </td>
                  <td className="d">{e.d}</td>
                  <td className="m">{e.s}</td>
                  <td className="m">{e.inv}</td>
                  <td className="m">{e.ts}</td>
                  <td className="m">
                    {e.u} claim{e.u === 1 ? '' : 's'}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="7" style={{ textAlign: 'center', color: 'var(--mu)', padding: '28px' }}>
                  No evidence matches these filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Badge Legend */}
      <div className="leg">
        <span>
          <span className="badge b-fact">Fact</span>Directly observed
        </span>
        <span>
          <span className="badge b-der">Derived</span>Calculated from evidence
        </span>
        <span>
          <span className="badge b-inf">Inference</span>Reasoned conclusion
        </span>
      </div>

      {/* Footnote */}
      <p className="note">Sample data shown for illustration. Click a row to open its full provenance.</p>

      {/* Slide-over Right Drawer */}
      <div className={`dr ${!drawerOpen ? 'h' : ''}`} id="dr">
        <div className="ph">
          <span className="cap">Evidence · {activeDrawerItem.id}</span>
          <span style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <span className={`badge ${activeDrawerItem.bc}`}>{activeDrawerItem.t}</span>
            <button type="button" className="x" id="cl" onClick={handleCloseDrawer}>
              ×
            </button>
          </span>
        </div>

        <h3>{activeDrawerItem.d}</h3>
        <p className="desc">
          From investigation {activeDrawerItem.inv}, {activeDrawerItem.ts}.
        </p>

        {activeDrawerItem.sql && (
          <div className="blk">
            <div className="cap">SQL</div>
            <pre dangerouslySetInnerHTML={{ __html: activeDrawerItem.sql }} />
          </div>
        )}

        {activeDrawerItem.calc && (
          <div className="blk">
            <div className="cap">Calculation</div>
            <pre dangerouslySetInnerHTML={{ __html: activeDrawerItem.calc }} />
          </div>
        )}

        <div className="blk">
          <div className="cap">{activeDrawerItem.sql ? 'Returned rows' : 'Inputs'}</div>
          <table className="rows">
            <tbody>
              <tr>
                {activeDrawerItem.cols.map((c, i) => (
                  <th key={i} className={i ? 'r' : ''}>
                    {c}
                  </th>
                ))}
              </tr>
              {activeDrawerItem.rows.map((r, idx) => (
                <tr key={idx} className={r[2] ? 'hl' : ''}>
                  <td>{r[0]}</td>
                  <td className="r">{r[1]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="blk">
          <div className="cap">Source and execution</div>
          <div className="kv">
            {activeDrawerItem.meta.map((m, idx) => (
              <React.Fragment key={idx}>
                <span>{m[0]}</span>
                <span>{m[1]}</span>
              </React.Fragment>
            ))}
          </div>
        </div>

        <div className="blk">
          <div className="cap">Limitations</div>
          <div className="lim">{activeDrawerItem.lim}</div>
        </div>

        <div className="blk">
          <div className="cap">Supports claims</div>
          <div className="used">
            {activeDrawerItem.cl.length ? (
              activeDrawerItem.cl.map((c, idx) => <div key={idx}>{c}</div>)
            ) : (
              <div style={{ color: 'var(--mu)' }}>Not yet used by any claim.</div>
            )}
          </div>
        </div>

        <div className="foot">
          <button type="button" className="btn">
            {activeDrawerItem.sql ? 'Copy SQL' : 'Copy calculation'}
          </button>
          <button type="button" className="btn" onClick={() => handleOpenInv(activeDrawerItem.inv)}>
            Open {activeDrawerItem.inv}
          </button>
        </div>
      </div>
    </div>
  );
}
