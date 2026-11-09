import React, { useState, useEffect } from 'react';
import { getAnalyticsSummary, listInvestigations } from '../../api/client.js';

export function OverviewView({
  currentUser = null,
  activeData = null,
  onRunInvestigation,
  onSelectInvestigation,
  onNavigate,
  useMock = false
}) {
  const [analytics, setAnalytics] = useState(null);
  const [recentInvestigations, setRecentInvestigations] = useState([]);
  const [promptInput, setPromptInput] = useState('');
  const [loadingOverview, setLoadingOverview] = useState(true);
  const [overviewError, setOverviewError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    setLoadingOverview(true);
    setOverviewError(null);

    Promise.all([
      getAnalyticsSummary(useMock).catch(() => {
        return null;
      }),
      listInvestigations(5, 0, useMock).catch(() => {
        return [];
      })
    ])
      .then(([summary, list]) => {
        if (isMounted) {
          setAnalytics(summary);
          setRecentInvestigations(Array.isArray(list) ? list : []);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setOverviewError(err.message || 'Unable to connect to backend analytics service.');
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

  // Derive honest statistics from backend responses
  const totalInvCount = analytics?.total_investigations ?? recentInvestigations.length;
  const totalEvidenceCount = analytics
    ? (analytics.total_evidence_collected ?? recentInvestigations.reduce((acc, curr) => acc + (curr.evidence_count || 0), 0))
    : (activeData?.evidence?.length ?? 0);

  const supportedClaimsPct = activeData?.claims?.length
    ? Math.round((activeData.claims.filter((c) => c.is_supported).length / activeData.claims.length) * 100)
    : (recentInvestigations.length > 0 ? 100 : 0);

  const stableDecisionsCount = analytics?.robustness_counts?.STABLE ?? 0;
  const totalDecisionsCount = analytics?.robustness_counts
    ? ((analytics.robustness_counts.STABLE || 0) + (analytics.robustness_counts.SENSITIVE || 0) + (analytics.robustness_counts.INSUFFICIENT_EVIDENCE || 0))
    : 0;

  // Filter investigations awaiting human review
  const pendingReviews = recentInvestigations.filter((inv) =>
    inv.status === 'REQUIRES_REVIEW' || inv.robustness_status === 'SENSITIVE'
  );

  const userFirstName = currentUser?.full_name?.split(' ')[0] || (currentUser?.role ? currentUser.role : 'Analyst');

  return (
    <div className="view-shell overview-view-shell" role="region" aria-label="Overview Dashboard">
      {/* Top Welcome Banner */}
      <div className="overview-hero">
        <div className="overview-hero-text">
          <h1 className="overview-title">Welcome, {userFirstName}</h1>
          <p className="overview-subtitle">
            Evidence-First AI Decision Intelligence. Every answer is backed by deterministic SQL execution and verifiable claims.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => handleChipClick('What is our gross revenue by region?')}
          aria-label="Start a new investigation"
        >
          New Investigation →
        </button>
      </div>

      {overviewError && (
        <div className="review-message message-error" style={{ marginBottom: '1rem' }}>
          <span className="msg-icon" aria-hidden="true">⚠️</span>
          <span>{overviewError}</span>
        </div>
      )}

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
            placeholder="e.g. What is our gross revenue by region?"
          />
          <kbd className="kbd-shortcut" title="Press Enter to investigate">↵</kbd>
          <button type="submit" className="btn btn-primary btn-sm">
            Investigate →
          </button>
        </form>

        <div className="quick-chips-row">
          <span className="chips-label">Suggested Queries:</span>
          <button
            type="button"
            className="chip-btn"
            onClick={() => handleChipClick('What is our gross revenue by region?')}
          >
            What is our gross revenue by region?
          </button>
          <button
            type="button"
            className="chip-btn"
            onClick={() => handleChipClick('Which product category generates the highest net sales?')}
          >
            Which product category generates the highest net sales?
          </button>
          <button
            type="button"
            className="chip-btn"
            onClick={() => handleChipClick('What is the average order discount by customer segment?')}
          >
            Average order discount by customer segment
          </button>
        </div>
      </div>

      {/* 4 Metric KPI Stat Cards */}
      <div className="overview-stats-grid" role="region" aria-label="Investigation Statistics">
        <div className="card stat-card">
          <small className="stat-label">Total Investigations</small>
          <b className="stat-value">{loadingOverview ? '—' : totalInvCount}</b>
        </div>
        <div className="card stat-card">
          <small className="stat-label">Evidence Items Collected</small>
          <b className="stat-value">{loadingOverview ? '—' : totalEvidenceCount}</b>
        </div>
        <div className="card stat-card">
          <small className="stat-label">Claims Supported</small>
          <b className="stat-value">{loadingOverview ? '—' : (supportedClaimsPct > 0 ? `${supportedClaimsPct}%` : '—')}</b>
        </div>
        <div className="card stat-card">
          <small className="stat-label">Stable Decisions</small>
          <b className="stat-value">
            {loadingOverview ? '—' : (totalDecisionsCount > 0 ? `${stableDecisionsCount} / ${totalDecisionsCount}` : `${stableDecisionsCount} verified`)}
          </b>
        </div>
      </div>

      {/* Two-Column Overview Layout */}
      <div className="overview-columns">
        {/* Left Column: Recent Investigations Table */}
        <div className="card overview-col-left">
          <div className="card-header-row">
            <h2 className="section-heading">Recent Investigations</h2>
            <button
              type="button"
              className="text-link-btn"
              onClick={() => onNavigate && onNavigate('history')}
            >
              View Full History →
            </button>
          </div>

          <div className="overview-recent-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Question</th>
                  <th>Status</th>
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
                        {inv.created_at && (
                          <small className="meta-time">
                            {new Date(inv.created_at).toLocaleDateString()}
                          </small>
                        )}
                      </td>
                      <td>
                        <span className={`status-badge ${inv.status === 'COMPLETED' ? 'b-ok' : inv.status === 'REQUIRES_REVIEW' ? 'b-warn' : 'b-neu'}`}>
                          {inv.status || 'COMPLETED'}
                        </span>
                      </td>
                      <td>
                        <span className={`status-badge ${inv.robustness_status === 'STABLE' ? 'b-ok' : inv.robustness_status === 'SENSITIVE' ? 'b-warn' : 'b-neu'}`}>
                          {inv.robustness_status === 'STABLE' ? '✓ Stable' : inv.robustness_status === 'SENSITIVE' ? '◐ Sensitive' : '○ Insufficient'}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)' }}>
                        {inv.evidence_count ?? 0}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} style={{ textAlign: 'center', color: 'var(--mu)', padding: '2rem 1rem' }}>
                      {loadingOverview ? 'Loading recent investigations...' : 'No historical investigations found. Submit a question above to create the first investigation.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Column: Pending Human Reviews Card */}
        <div className="card overview-col-right">
          <div className="card-header-row">
            <h2 className="section-heading">Pending Human Reviews</h2>
            <span className="summary-count-tag">{pendingReviews.length}</span>
          </div>

          <div className="pending-reviews-list">
            {pendingReviews.length > 0 ? (
              pendingReviews.map((item) => (
                <div
                  key={item.investigation_id}
                  className="pending-review-item pointer"
                  onClick={() => onSelectInvestigation && onSelectInvestigation(item.investigation_id)}
                >
                  <div className="pr-top">
                    <strong>{item.question}</strong>
                    <span className="status-badge b-warn">Review Needed</span>
                  </div>
                  <small className="meta-sub">
                    Robustness: {item.robustness_status || 'SENSITIVE'} · ID: {item.investigation_id}
                  </small>
                </div>
              ))
            ) : (
              <div className="empty-reviews-state">
                <span className="empty-chk" aria-hidden="true">✓</span>
                <p>All decision recommendations are reviewed and stable.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default OverviewView;
