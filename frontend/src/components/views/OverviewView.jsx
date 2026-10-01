import React, { useState, useEffect } from 'react';
import { getAnalyticsSummary, listInvestigations } from '../../api/client.js';

export function OverviewView({ useMock = false, onSelectInvestigation, onNavigate }) {
  const [metrics, setMetrics] = useState(null);
  const [recentInv, setRecentInv] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);

    Promise.all([
      getAnalyticsSummary(useMock),
      listInvestigations(5, 0, useMock)
    ])
      .then(([metricsData, listData]) => {
        if (isMounted) {
          setMetrics(metricsData);
          setRecentInv(listData || []);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || 'Failed to load executive overview data.');
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [useMock]);

  return (
    <div className="view-container overview-view">
      <div className="view-header">
        <div>
          <h2>Executive Decision Intelligence Overview</h2>
          <p className="view-subtitle">
            System-wide investigation counts, human review decisions, robustness distribution, and recent activity.
          </p>
        </div>
        <button
          type="button"
          className="submit-review-btn"
          onClick={() => onNavigate && onNavigate('workspace')}
        >
          + New Investigation
        </button>
      </div>

      {loading && (
        <div className="card loading-card" role="status">
          <div className="spinner" aria-hidden="true"></div>
          <p>Loading overview metrics...</p>
        </div>
      )}

      {error && (
        <div className="card error-card" role="alert">
          <span className="error-icon" aria-hidden="true">⚠️</span>
          <p>{error}</p>
        </div>
      )}

      {!loading && !error && metrics && (
        <>
          {/* Executive KPI Summary Cards */}
          <div className="kpi-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
            <div className="card kpi-card" style={{ padding: '1.25rem', textAlign: 'center' }}>
              <span className="kpi-label" style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Total Investigations</span>
              <div className="kpi-value" style={{ fontSize: '2rem', fontWeight: '700', color: 'var(--color-primary)' }}>
                {metrics.total_investigations || 0}
              </div>
            </div>

            <div className="card kpi-card" style={{ padding: '1.25rem', textAlign: 'center' }}>
              <span className="kpi-label" style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Human Audit Reviews</span>
              <div className="kpi-value" style={{ fontSize: '2rem', fontWeight: '700', color: 'var(--color-success)' }}>
                {metrics.total_reviews || 0}
              </div>
            </div>

            <div className="card kpi-card" style={{ padding: '1.25rem', textAlign: 'center' }}>
              <span className="kpi-label" style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Pending Review</span>
              <div className="kpi-value" style={{ fontSize: '2rem', fontWeight: '700', color: 'var(--color-warning)' }}>
                {metrics.status_counts?.REQUIRES_REVIEW || 0}
              </div>
            </div>

            <div className="card kpi-card" style={{ padding: '1.25rem', textAlign: 'center' }}>
              <span className="kpi-label" style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Avg Execution Time</span>
              <div className="kpi-value" style={{ fontSize: '2rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                {metrics.average_execution_time_ms ? `${metrics.average_execution_time_ms} ms` : 'N/A'}
              </div>
            </div>
          </div>

          {/* Recent Investigations Activity Table */}
          <div className="card recent-activity-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 style={{ fontSize: '1rem', fontWeight: '600' }}>Recent Investigations</h3>
              <button
                type="button"
                className="btn-history-toggle"
                style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem' }}
                onClick={() => onNavigate && onNavigate('history')}
              >
                View Full History →
              </button>
            </div>

            {recentInv.length === 0 ? (
              <p className="no-data-text">No investigations executed yet.</p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table className="data-table" style={{ width: '100%', fontSize: '0.85rem', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ backgroundColor: 'var(--bg-card-subtle)', textAlign: 'left' }}>
                      <th style={{ padding: '0.5rem 0.75rem' }}>Question</th>
                      <th style={{ padding: '0.5rem 0.75rem' }}>Status</th>
                      <th style={{ padding: '0.5rem 0.75rem' }}>Robustness</th>
                      <th style={{ padding: '0.5rem 0.75rem' }}>Created</th>
                      <th style={{ padding: '0.5rem 0.75rem' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentInv.map((inv) => (
                      <tr key={inv.investigation_id} style={{ borderBottom: '1px solid var(--border-light)' }}>
                        <td style={{ padding: '0.5rem 0.75rem', fontWeight: '500' }}>{inv.question}</td>
                        <td style={{ padding: '0.5rem 0.75rem' }}>
                          <span className={`status-pill pill-${inv.status.toLowerCase()}`}>{inv.status}</span>
                        </td>
                        <td style={{ padding: '0.5rem 0.75rem' }}>
                          <span className={`robustness-pill rob-${(inv.robustness_status || 'STABLE').toLowerCase()}`}>
                            {inv.robustness_status || 'STABLE'}
                          </span>
                        </td>
                        <td style={{ padding: '0.5rem 0.75rem', fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
                          {new Date(inv.created_at).toLocaleDateString()}
                        </td>
                        <td style={{ padding: '0.5rem 0.75rem' }}>
                          <button
                            type="button"
                            className="btn-select-inv"
                            style={{
                              padding: '0.25rem 0.5rem',
                              fontSize: '0.75rem',
                              borderRadius: '0.25rem',
                              border: '1px solid var(--border-medium)',
                              backgroundColor: 'var(--bg-card)',
                              color: 'var(--color-primary)',
                              cursor: 'pointer'
                            }}
                            onClick={() => onSelectInvestigation && onSelectInvestigation(inv.investigation_id)}
                          >
                            Open →
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
