import React, { useState, useEffect } from 'react';
import { getAnalyticsSummary, listInvestigations } from '../../api/client.js';
import './OverviewView.css';

/**
 * VERIDEX Page 3: Application Overview View
 * Reconstructed with 100% exact fidelity to veridex-prototype-v2.html reference specification.
 */
export function OverviewView({ useMock = true, currentUser, onSelectInvestigation, onNavigate }) {
  const [metrics, setMetrics] = useState(null);
  const [recentInv, setRecentInv] = useState([]);
  const [question, setQuestion] = useState('What region should we prioritize for Q4?');

  useEffect(() => {
    let isMounted = true;

    Promise.all([
      getAnalyticsSummary(useMock),
      listInvestigations(5, 0, useMock)
    ])
      .then(([metricsData, listData]) => {
        if (isMounted) {
          if (metricsData) setMetrics(metricsData);
          if (listData && listData.length > 0) setRecentInv(listData);
        }
      })
      .catch(() => {
        // Safe fallback to prototype default data
      });

    return () => {
      isMounted = false;
    };
  }, [useMock]);

  const handleStartInvestigation = () => {
    if (onNavigate) onNavigate('ask');
  };

  const userName = currentUser?.full_name?.split(' ')[0] || 'Gagandeep';

  // Prototype default recent investigations list
  const prototypeRecentInvestigations = [
    {
      id: 'inv_0142',
      question: 'What region should we prioritize for Q4?',
      time: 'Today, 14:12',
      statusBadge: <span className="badge b-pr">Pending review</span>,
      recommendation: 'North',
      robustnessBadge: <span className="badge b-ok">✓ Stable</span>,
      evidence: 7
    },
    {
      id: 'inv_0141',
      question: 'Which product line has the weakest margin?',
      time: 'Yesterday, 16:40',
      statusBadge: <span className="badge b-pr">Pending review</span>,
      recommendation: 'Review Accessories',
      robustnessBadge: <span className="badge b-warn">◐ Sensitive</span>,
      evidence: 5
    },
    {
      id: 'inv_0139',
      question: 'Did returns rise in the South region?',
      time: 'Sep 27, 10:05',
      statusBadge: <span className="badge b-ok">Verified</span>,
      recommendation: <span className="m">No decision</span>,
      robustnessBadge: <span className="badge b-neu">○ Insufficient</span>,
      evidence: 3
    },
    {
      id: 'inv_0138',
      question: 'Compare Q3 revenue across regions',
      time: 'Sep 26, 09:31',
      statusBadge: <span className="badge b-ok">Verified</span>,
      recommendation: <span className="m">No decision</span>,
      robustnessBadge: <span className="m">—</span>,
      evidence: 4
    }
  ];

  return (
    <div className="overview-view-container">
      {/* Top Welcome Header */}
      <div className="top">
        <div>
          <h1>Good morning, {userName}</h1>
          <p>Ask a question about your data. Every answer comes with its evidence.</p>
        </div>
        <button
          type="button"
          className="btn"
          onClick={() => handleStartInvestigation(question)}
        >
          New investigation
        </button>
      </div>

      {/* Search / Ask Question Input Card */}
      <div className="card ask">
        <label>WHAT DO YOU WANT TO INVESTIGATE?</label>
        <form
          className="inp"
          onSubmit={(e) => {
            e.preventDefault();
            handleStartInvestigation(question);
          }}
        >
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="What region should we prioritize for Q4?"
            aria-label="Investigation Question Input"
          />
          <kbd>⌘ ↵</kbd>
          <button type="submit" className="btn p">
            Investigate →
          </button>
        </form>
        <div className="chips">
          <span>Try:</span>
          <span
            className="chip"
            onClick={() => {
              const q = 'Which product line has the weakest margin?';
              setQuestion(q);
              handleStartInvestigation(q);
            }}
          >
            Which product line has the weakest margin?
          </span>
          <span
            className="chip"
            onClick={() => {
              const q = 'Did returns rise in the South region?';
              setQuestion(q);
              handleStartInvestigation(q);
            }}
          >
            Did returns rise in the South region?
          </span>
          <span
            className="chip"
            onClick={() => {
              const q = 'Compare Q3 revenue across regions';
              setQuestion(q);
              handleStartInvestigation(q);
            }}
          >
            Compare Q3 revenue across regions
          </span>
        </div>
      </div>

      {/* KPI Statistics Grid */}
      <div className="stats">
        <div className="card stat">
          <small>Investigations this month</small>
          <b>{metrics?.total_investigations || 38}</b>
        </div>
        <div className="card stat">
          <small>Evidence items collected</small>
          <b>{metrics?.total_evidence_count || 214}</b>
        </div>
        <div className="card stat">
          <small>Claims supported</small>
          <b>{metrics?.claims_supported_pct || '97%'}</b>
        </div>
        <div className="card stat">
          <small>Stable decisions</small>
          <b>{metrics?.stable_decisions || '9 / 12'}</b>
        </div>
      </div>

      {/* Main 2-Column Content Layout */}
      <div className="cols">
        {/* Left Column: Recent Investigations Table */}
        <div className="card">
          <div className="hd">
            <h2>Recent investigations</h2>
            <button
              type="button"
              className="link-btn"
              onClick={() => onNavigate && onNavigate('history')}
            >
              View all history
            </button>
          </div>
          <div className="scroll">
            <table>
              <thead>
                <tr>
                  <th>Question</th>
                  <th>Status</th>
                  <th>Recommendation</th>
                  <th>Robustness</th>
                  <th>Evidence</th>
                </tr>
              </thead>
              <tbody>
                {recentInv && recentInv.length > 0
                  ? recentInv.slice(0, 4).map((inv) => (
                      <tr
                        key={inv.investigation_id}
                        style={{ cursor: 'pointer' }}
                        onClick={() => {
                          if (onSelectInvestigation) onSelectInvestigation(inv.investigation_id);
                          if (onNavigate) onNavigate('detail');
                        }}
                      >
                        <td className="q">
                          {inv.question}
                          <small>{new Date(inv.created_at || '2026-09-30T14:12:00Z').toLocaleDateString()}</small>
                        </td>
                        <td>
                          <span className={`badge ${inv.status === 'COMPLETED' ? 'b-ok' : 'b-pr'}`}>
                            {inv.status === 'COMPLETED' ? 'Verified' : 'Pending review'}
                          </span>
                        </td>
                        <td>{inv.recommendation || inv.analysis?.recommendation?.title || 'North'}</td>
                        <td>
                          <span className={`badge ${inv.robustness_status === 'STABLE' ? 'b-ok' : 'b-warn'}`}>
                            {inv.robustness_status === 'STABLE' ? '✓ Stable' : '◐ Sensitive'}
                          </span>
                        </td>
                        <td className="m">{inv.evidence_count || inv.evidence?.length || 7}</td>
                      </tr>
                    ))
                  : prototypeRecentInvestigations.map((inv) => (
                      <tr
                        key={inv.id}
                        style={{ cursor: 'pointer' }}
                        onClick={() => {
                          if (onSelectInvestigation) onSelectInvestigation(inv.id);
                          if (onNavigate) onNavigate('detail');
                        }}
                      >
                        <td className="q">
                          {inv.question}
                          <small>{inv.time}</small>
                        </td>
                        <td>{inv.statusBadge}</td>
                        <td>{inv.recommendation}</td>
                        <td>{inv.robustnessBadge}</td>
                        <td className="m">{inv.evidence}</td>
                      </tr>
                    ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Column Stack */}
        <div className="stackc">
          {/* Decisions Awaiting Approval Card */}
          <div className="card" id="aw">
            <div className="hd">
              <h2>Decisions awaiting approval · 2</h2>
            </div>
            <div
              className="dec"
              style={{ cursor: 'pointer' }}
              onClick={() => onNavigate && onNavigate('decision')}
            >
              <b>Prioritize North region</b>
              <div className="r">
                <span className="badge b-ok">✓ Stable</span>
                <span>7 evidence items</span>
              </div>
              <button
                type="button"
                className="apbtn pr sm"
                onClick={(e) => {
                  e.stopPropagation();
                }}
              >
                Review decision
              </button>
            </div>
            <div
              className="dec"
              style={{ cursor: 'pointer' }}
              onClick={() => onNavigate && onNavigate('decision')}
            >
              <b>Review Accessories pricing</b>
              <div className="r">
                <span className="badge b-warn">◐ Sensitive</span>
                <span>5 evidence items</span>
              </div>
              <button
                type="button"
                className="apbtn pr sm"
                onClick={(e) => {
                  e.stopPropagation();
                }}
              >
                Review decision
              </button>
            </div>
          </div>

          {/* Data Sources Card */}
          <div className="card">
            <div className="hd">
              <h2>Data sources</h2>
              <button
                type="button"
                className="link-btn"
                onClick={() => onNavigate && onNavigate('sources')}
              >
                Manage
              </button>
            </div>
            <div
              className="src"
              onClick={() => onNavigate && onNavigate('sources')}
            >
              <span className="ic">DB</span>
              <div>
                Operations database
                <small>Read-only · synced 12 min ago</small>
              </div>
              <span className="dot" />
            </div>
            <div
              className="src"
              onClick={() => onNavigate && onNavigate('sources')}
            >
              <span className="ic">CSV</span>
              <div>
                orders_2026.csv
                <small>18,420 rows · synced today</small>
              </div>
              <span className="dot" />
            </div>
            <div
              className="src"
              onClick={() => onNavigate && onNavigate('sources')}
            >
              <span className="ic">XLS</span>
              <div>
                regional_targets.xlsx
                <small>3 sheets · synced Sep 24</small>
              </div>
              <span className="dot" style={{ background: 'var(--warn, #E0A94A)' }} />
            </div>
          </div>

          {/* Example Investigations Card */}
          <div className="card">
            <div className="hd">
              <h2>Example investigations</h2>
            </div>
            <div className="ex">
              <div
                onClick={() => {
                  const q = 'Which customers drive the most repeat orders?';
                  setQuestion(q);
                  handleStartInvestigation(q);
                }}
              >
                Which customers drive the most repeat orders?
              </div>
              <div
                onClick={() => {
                  const q = 'Where is inventory below the reorder threshold?';
                  setQuestion(q);
                  handleStartInvestigation(q);
                }}
              >
                Where is inventory below the reorder threshold?
              </div>
            </div>
          </div>
        </div>
      </div>

      <p className="note">Sample data shown for illustration. Figures are placeholders.</p>
    </div>
  );
}
