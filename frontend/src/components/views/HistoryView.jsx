import React, { useState } from 'react';
import './HistoryView.css';

// Prototype robustness badges mapping
const ROBUSTNESS_MAP = {
  Stable: ["b-ok", "✓ Stable"],
  Sensitive: ["b-warn", "◐ Sensitive"],
  Insufficient: ["b-neu", "○ Insufficient"]
};

// Prototype historical investigations dataset matching P["history"]
const PROTOTYPE_HISTORY = [
  { q: "What region should we prioritize for Q4?", id: "inv_0142", d: "Sep 30, 14:12", t: 1, s: "Pending review", rec: "Prioritize North region", r: "Stable", e: 7 },
  { q: "Which product line has the weakest margin?", id: "inv_0141", d: "Sep 29, 16:40", t: 2, s: "Pending review", rec: "Review Accessories pricing", r: "Sensitive", e: 5 },
  { q: "Did returns rise in the South region?", id: "inv_0139", d: "Sep 27, 10:05", t: 3, s: "Verified", rec: "", r: "Insufficient", e: 3 },
  { q: "Compare Q3 revenue across regions", id: "inv_0138", d: "Sep 26, 09:31", t: 4, s: "Verified", rec: "", r: "", e: 4 },
  { q: "Where is inventory below the reorder threshold?", id: "inv_0136", d: "Sep 24, 15:18", t: 5, s: "Failed", rec: "", r: "", e: 0, err: "The query could not be completed." },
  { q: "Which customer segment should we target first?", id: "inv_0133", d: "Sep 22, 11:47", t: 6, s: "Approved", rec: "Target Mid-market segment", r: "Stable", e: 6 },
  { q: "Should we expand the West region team?", id: "inv_0130", d: "Sep 19, 13:02", t: 7, s: "Rejected", rec: "Hold headcount in West", r: "Sensitive", e: 5 },
  { q: "What drove the Q2 margin decline?", id: "inv_0127", d: "Sep 17, 09:55", t: 8, s: "Verified", rec: "", r: "", e: 4 }
];

/**
 * VERIDEX Page 9: Investigation History View
 * Reconstructed with 100% exact visual and functional fidelity to veridex-prototype-v2.html P["history"].
 */
export function HistoryView({
  useMock: _useMock = true,
  currentUser: _currentUser,
  onSelectInvestigation,
  onNavigate
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [robustnessFilter, setRobustnessFilter] = useState('ALL');
  const [dateDesc, setDateDesc] = useState(true);

  const getStatusGroup = (s) => (s === 'Approved' || s === 'Rejected' ? 'Reviewed' : s);

  const getStatusColor = (s) => {
    if (s === 'Failed') return 'var(--err, #D46A6A)';
    if (s === 'Pending review') return 'var(--pr, #4C8DFF)';
    if (s === 'Rejected') return 'var(--mu, #8B95A5)';
    return 'var(--ok, #4CB782)';
  };

  // Filter and sort items matching prototype logic
  const filteredList = React.useMemo(() => {
    const q = searchQuery.toLowerCase().trim();

    const filtered = PROTOTYPE_HISTORY.filter((item) => {
      const matchStatus = statusFilter === 'ALL' || getStatusGroup(item.s) === statusFilter;
      const matchRob = robustnessFilter === 'ALL' || item.r === robustnessFilter;
      const matchSearch =
        !q ||
        item.q.toLowerCase().includes(q) ||
        (item.rec && item.rec.toLowerCase().includes(q)) ||
        item.id.toLowerCase().includes(q);
      return matchStatus && matchRob && matchSearch;
    });

    return [...filtered].sort((a, b) => (dateDesc ? a.t - b.t : b.t - a.t));
  }, [searchQuery, statusFilter, robustnessFilter, dateDesc]);

  const handleRowClick = (invId) => {
    if (onSelectInvestigation) {
      onSelectInvestigation(invId);
    }
    if (onNavigate) {
      onNavigate('detail');
    }
  };

  const handleStartNew = () => {
    if (onNavigate) {
      onNavigate('workspace');
    }
  };

  return (
    <div className="history-page-container">
      {/* Top Header & New Investigation Button */}
      <div className="top">
        <div>
          <h1>Investigation history</h1>
          <p className="sub">Every question asked, with its outcome and evidence.</p>
        </div>
        <button className="btn p" onClick={handleStartNew}>
          New investigation
        </button>
      </div>

      {/* Toolbar Controls: Search, Status Filter, Robustness Filter, Item Counter */}
      <div className="tb">
        <input
          className="search"
          placeholder="Search questions or recommendations…"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />

        {/* Status Segmented Filter */}
        <div className="fg">
          Status
          <div className="seg">
            {['ALL', 'Verified', 'Pending review', 'Reviewed', 'Failed'].map((val) => (
              <button
                key={val}
                className={statusFilter === val ? 'on' : ''}
                onClick={() => setStatusFilter(val)}
              >
                {val === 'Pending review' ? 'Pending' : val === 'ALL' ? 'All' : val}
              </button>
            ))}
          </div>
        </div>

        {/* Robustness Segmented Filter */}
        <div className="fg">
          Robustness
          <div className="seg">
            {['ALL', 'Stable', 'Sensitive', 'Insufficient'].map((val) => (
              <button
                key={val}
                className={robustnessFilter === val ? 'on' : ''}
                onClick={() => setRobustnessFilter(val)}
              >
                {val === 'ALL' ? 'All' : val}
              </button>
            ))}
          </div>
        </div>

        <span className="cnt">
          {filteredList.length} of {PROTOTYPE_HISTORY.length} investigations
        </span>
      </div>

      {/* History Table Card */}
      <div className="card">
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>Question</th>
                <th className="s" onClick={() => setDateDesc(!dateDesc)}>
                  Date {dateDesc ? '↓' : '↑'}
                </th>
                <th>Status</th>
                <th>Recommendation</th>
                <th>Robustness</th>
                <th style={{ textAlign: 'right' }}>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {filteredList.length > 0 ? (
                filteredList.map((item) => (
                  <tr key={item.id} onClick={() => handleRowClick(item.id)}>
                    <td className="q">
                      {item.q}
                      <small>
                        {item.id}
                        {item.err ? ` · ${item.err}` : ''}
                      </small>
                    </td>
                    <td className="m">{item.d}</td>
                    <td>
                      <span className="st" style={{ '--c': getStatusColor(item.s) }}>
                        {item.s}
                      </span>
                    </td>
                    <td>
                      {item.rec ? (
                        item.rec
                      ) : (
                        <span style={{ color: 'var(--mu)' }}>No decision</span>
                      )}
                    </td>
                    <td>
                      {item.r && ROBUSTNESS_MAP[item.r] ? (
                        <span className={`badge ${ROBUSTNESS_MAP[item.r][0]}`}>
                          {ROBUSTNESS_MAP[item.r][1]}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--mu)' }}>—</span>
                      )}
                    </td>
                    <td className="m" style={{ textAlign: 'right' }}>
                      {item.e}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="6">
                    <div className="empty">
                      <b>No investigations match</b>
                      Try clearing a filter or searching for something else.
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="pg">
          <span>Showing 1–{filteredList.length}</span>
          <div>
            <button disabled>← Prev</button>
            <button disabled>Next →</button>
          </div>
        </div>
      </div>

      {/* Footnote */}
      <p className="note">Sample data shown for illustration. Click a row to open the investigation detail (Page 4).</p>
    </div>
  );
}
