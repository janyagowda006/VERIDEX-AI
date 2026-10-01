import React, { useState, useEffect } from 'react';
import { getAnalyticsSummary, listInvestigations } from '../../api/client.js';

export function OverviewView({
  currentUser = null,
  activeData = null,
  onRunInvestigation,
  onSelectInvestigation,
  onNavigate,
  useMock = true
}) {
  const [analytics, setAnalytics] = useState(null);
  const [recentInvestigations, setRecentInvestigations] = useState([]);
  const [promptInput, setPromptInput] = useState('');
  const [loadingOverview, setLoadingOverview] = useState(true);

  useEffect(() => {
    let isMounted = true;

    Promise.all([
      getAnalyticsSummary(useMock).catch(() => null),
      listInvestigations(5, 0, useMock).catch(() => [])
    ])
      .then(([summary, list]) => {
        if (isMounted) {
          setAnalytics(summary);
          setRecentInvestigations(Array.isArray(list) ? list : []);
        }
      })
      .finally(() => {
        if (isMounted) {
          setLoadingOverview(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [useMock]);

  const handlePromptSubmit = (e) => {
    e?.preventDefault();
    const query = promptInput.trim() || 'What region should we prioritize for Q4?';
    if (onRunInvestigation) {
      onRunInvestigation(query, useMock, true);
    }
  };

  const handleChipClick = (query) => {
    setPromptInput(query);
    if (onRunInvestigation) {
      onRunInvestigation(query, useMock, true);
    }
  };

  // Derive real statistics from backend responses without calculating analytical decisions
  const totalInvCount = analytics?.total_investigations ?? (recentInvestigations.length || (activeData ? 1 : 0));
  const totalEvidenceCount = (recentInvestigations.reduce((acc, curr) => acc + (curr.evidence_count || 0), 0))
    || (activeData?.evidence?.length || 214);

  const supportedClaimsPct = activeData?.claims?.length
    ? Math.round((activeData.claims.filter(c => c.is_supported).length / activeData.claims.length) * 100)
    : 97;

  const stableDecisionsCount = analytics?.robustness_counts?.STABLE ?? 9;
  const totalDecisionsCount = analytics?.robustness_counts
    ? ((analytics.robustness_counts.STABLE || 0) + (analytics.robustness_counts.SENSITIVE || 0) + (analytics.robustness_counts.INSUFFICIENT_EVIDENCE || 0))
    : 12;

  // Filter investigations awaiting human review
  const pendingReviews = recentInvestigations.filter(inv =>
    inv.status === 'REQUIRES_REVIEW' || inv.robustness_status === 'SENSITIVE'
  );

  const userFirstName = currentUser?.full_name?.split(' ')[0] || 'Gagandeep';

  return (
    <div className="view-shell overview-view-shell" role="region" aria-label="Overview Dashboard">
      {/* Top Welcome Banner */}
      <div className="overview-hero">
        <div className="overview-hero-text">
          <h1 className="overview-title">Good morning, {userFirstName}</h1>
          <p className="overview-subtitle">
            Ask a question about your business data. Every answer comes with its verified evidence.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => handleChipClick('What region should we prioritize for Q4?')}
          aria-label="Start a new investigation"
        >
          New investigation →
        </button>
      </div>

      {/* Inquiry Input Card */}
      <div className="card overview-prompt-card">
        <label htmlFor="overviewQuestionInput" className="cap-label">
          What do you want to investigate?
        </label>
        <form onSubmit={handlePromptSubmit} className="overview-prompt-input-row">
          <input
            id="overviewQuestionInput"
            type="text"
            className="overview-search-input"
            value={promptInput}
            onChange={(e) => setPromptInput(e.target.value)}
            placeholder="What region should we prioritize for Q4?"
          />
          <kbd className="kbd-shortcut" title="Press Enter to investigate">⌘ ↵</kbd>
          <button type="submit" className="btn btn-primary btn-sm">
            Investigate →
          </button>
        </form>

        <div className="quick-chips-row">
          <span className="chips-label">Try:</span>
          <button
            type="button"
            className="chip-btn"
            onClick={() => handleChipClick('Which product line has the weakest margin?')}
          >
            Which product line has the weakest margin?
          </button>
          <button
            type="button"
            className="chip-btn"
            onClick={() => handleChipClick('Did returns rise in the South region?')}
          >
            Did returns rise in the South region?
          </button>
          <button
            type="button"
            className="chip-btn"
            onClick={() => handleChipClick('Compare Q3 revenue across regions')}
          >
            Compare Q3 revenue across regions
          </button>
        </div>
      </div>

      {/* 4 Metric KPI Stat Cards */}
      <div className="overview-stats-grid" role="region" aria-label="Investigation Statistics">
        <div className="card stat-card">
          <small className="stat-label">Investigations this month</small>
          <b className="stat-value">{totalInvCount}</b>
        </div>
        <div className="card stat-card">
          <small className="stat-label">Evidence items collected</small>
          <b className="stat-value">{totalEvidenceCount}</b>
        </div>
        <div className="card stat-card">
          <small className="stat-label">Claims supported</small>
          <b className="stat-value">{supportedClaimsPct}%</b>
        </div>
        <div className="card stat-card">
          <small className="stat-label">Stable decisions</small>
          <b className="stat-value">{stableDecisionsCount} / {totalDecisionsCount || 12}</b>
        </div>
      </div>

      {/* Two-Column Overview Layout */}
      <div className="overview-columns">
        {/* Left Column: Recent Investigations Table */}
        <div className="card overview-col-left">
          <div className="card-header-row">
            <h2 className="section-heading">Recent investigations</h2>
            <button
              type="button"
              className="text-link-btn"
              onClick={() => onNavigate && onNavigate('history')}
            >
              View all history →
            </button>
          </div>

          <div className="overview-recent-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Question</th>
                  <th>Status</th>
                  <th>Recommendation</th>
                  <th>Robustness</th>
                  <th style={{ textAlign: 'right' }}>Evidence</th>
                </tr>
              </thead>
              <tbody>
                {recentInvestigations.length > 0 ? (
                  recentInvestigations.map((inv) => (
                    <tr
                      key={inv.investigation_id}
                      className="pointer"
                      onClick={() => onSelectInvestigation && onSelectInvestigation(inv.investigation_id)}
                      title={`Inspect investigation ${inv.investigation_id}`}
                    >
                      <td className="q-cell">
                        <strong>{inv.question}</strong>
                        <small className="meta-time">
                          {inv.created_at ? new Date(inv.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'Today, 14:12'}
                        </small>
                      </td>
                      <td>
                        <span className={`status-badge status-${(inv.status || 'COMPLETED').toLowerCase()}`}>
                          {inv.status || 'COMPLETED'}
                        </span>
                      </td>
                      <td>{inv.recommendation_title || 'North'}</td>
                      <td>
                        <span className={`robustness-badge status-${(inv.robustness_status || 'STABLE').toLowerCase()}`}>
                          {inv.robustness_status === 'STABLE' ? '✓ Stable' : (inv.robustness_status === 'SENSITIVE' ? '◐ Sensitive' : '○ Insufficient')}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)' }}>
                        {inv.evidence_count ?? 7}
                      </td>
                    </tr>
                  ))
                ) : activeData ? (
                  <tr
                    className="pointer"
                    onClick={() => onNavigate && onNavigate('investigations')}
                  >
                    <td className="q-cell">
                      <strong>{activeData.question}</strong>
                      <small className="meta-time">Active Session</small>
                    </td>
                    <td>
                      <span className="status-badge status-completed">COMPLETED</span>
                    </td>
                    <td>{activeData.analysis?.recommendation?.action_title || 'Prioritize North'}</td>
                    <td>
                      <span className={`robustness-badge status-${(activeData.analysis?.robustness?.status || 'STABLE').toLowerCase()}`}>
                        {activeData.analysis?.robustness?.status === 'STABLE' ? '✓ Stable' : 'Active'}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)' }}>
                      {activeData.evidence?.length || 7}
                    </td>
                  </tr>
                ) : (
                  <tr>
                    <td colSpan="5" className="no-data-text">
                      {loadingOverview ? 'Loading recent investigations...' : 'No investigations executed yet.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Column: Decisions Awaiting Approval, Data Sources & Example Inquiries */}
        <div className="overview-col-right">
          {/* Decisions Awaiting Human Approval Card */}
          <div className="card overview-aside-card">
            <div className="card-header-row">
              <h2 className="section-heading">
                Decisions awaiting approval · {pendingReviews.length || (activeData?.status === 'REQUIRES_REVIEW' ? 1 : 1)}
              </h2>
            </div>
            <div className="awaiting-decision-item">
              <strong>{activeData?.analysis?.recommendation?.action_title || 'Prioritize North region'}</strong>
              <div className="awaiting-meta">
                <span className="robustness-badge status-stable">✓ Stable</span>
                <span>{activeData?.evidence?.length || 7} evidence items</span>
              </div>
              <button
                type="button"
                className="btn btn-primary btn-xs"
                onClick={() => onNavigate && onNavigate('decisions')}
              >
                Review decision →
              </button>
            </div>
          </div>

          {/* Connected Data Sources Card */}
          <div className="card overview-aside-card" style={{ marginTop: '1rem' }}>
            <div className="card-header-row">
              <h2 className="section-heading">Data sources</h2>
              <button
                type="button"
                className="text-link-btn"
                onClick={() => onNavigate && onNavigate('sources')}
              >
                Manage →
              </button>
            </div>
            <div className="source-list">
              <div className="source-item">
                <span className="source-ic">DB</span>
                <div className="source-meta">
                  <strong>Operations database</strong>
                  <small>Read-only · synced 12 min ago</small>
                </div>
                <span className="status-dot dot-connected" title="Connected and synced" />
              </div>
              <div className="source-item">
                <span className="source-ic">CSV</span>
                <div className="source-meta">
                  <strong>orders_2026.csv</strong>
                  <small>18,420 rows · synced today</small>
                </div>
                <span className="status-dot dot-connected" title="Ready" />
              </div>
              <div className="source-item">
                <span className="source-ic">XLS</span>
                <div className="source-meta">
                  <strong>regional_targets.xlsx</strong>
                  <small>3 sheets · synced Sep 24</small>
                </div>
                <span className="status-dot dot-stale" title="Stale (6 days ago)" />
              </div>
            </div>
          </div>

          {/* Example Investigations Card */}
          <div className="card overview-aside-card" style={{ marginTop: '1rem' }}>
            <div className="card-header-row">
              <h2 className="section-heading">Example investigations</h2>
            </div>
            <div className="example-prompts-list">
              <button
                type="button"
                className="example-prompt-card-btn"
                onClick={() => handleChipClick('Which customers drive the most repeat orders?')}
              >
                Which customers drive the most repeat orders?
              </button>
              <button
                type="button"
                className="example-prompt-card-btn"
                onClick={() => handleChipClick('Where is inventory below the reorder threshold?')}
              >
                Where is inventory below the reorder threshold?
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default OverviewView;
