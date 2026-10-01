import React, { useState, useEffect } from 'react';
import { listInvestigations } from '../../api/client.js';

export function HistoryView({ useMock = false, currentUser, onSelectInvestigation }) {
  const [investigations, setInvestigations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [robustnessFilter, setRobustnessFilter] = useState('');
  const [offset, setOffset] = useState(0);
  const limit = 10;

  const userRole = currentUser?.role || 'ANALYST';
  const ownerFilter = userRole === 'ANALYST' ? (currentUser?.user_id || 'usr_analyst_01') : null;

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);

    listInvestigations(limit, offset, useMock, searchTerm, statusFilter, robustnessFilter, ownerFilter)
      .then((data) => {
        if (isMounted) {
          setInvestigations(data || []);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || 'Failed to load investigation history.');
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [useMock, offset, searchTerm, statusFilter, robustnessFilter, ownerFilter]);

  const handleResetFilters = () => {
    setSearchTerm('');
    setStatusFilter('');
    setRobustnessFilter('');
    setOffset(0);
  };

  return (
    <div className="view-container history-view">
      <div className="view-header">
        <div>
          <h2>Investigation History & Search</h2>
          <p className="view-subtitle">
            Server-side keyword search, status filtering, and filter-aware pagination.
          </p>
        </div>
      </div>

      {/* Search & Filter Control Bar */}
      <div className="card filter-bar-card" style={{ marginBottom: '1.5rem', padding: '1rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem', alignItems: 'end' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: '600', marginBottom: '0.25rem' }}>Keyword Search</label>
            <input
              type="text"
              placeholder="Search questions or IDs..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ width: '100%', padding: '0.4rem 0.6rem', fontSize: '0.85rem', borderRadius: '0.375rem', border: '1px solid var(--border-medium)', backgroundColor: 'var(--bg-card)', color: 'var(--text-primary)' }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: '600', marginBottom: '0.25rem' }}>Status</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{ width: '100%', padding: '0.4rem 0.6rem', fontSize: '0.85rem', borderRadius: '0.375rem', border: '1px solid var(--border-medium)', backgroundColor: 'var(--bg-card)', color: 'var(--text-primary)' }}
            >
              <option value="">All Lifecycle Statuses</option>
              <option value="COMPLETED">COMPLETED</option>
              <option value="REQUIRES_REVIEW">REQUIRES_REVIEW</option>
              <option value="FAILED">FAILED</option>
              <option value="IN_PROGRESS">IN_PROGRESS</option>
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: '600', marginBottom: '0.25rem' }}>Robustness</label>
            <select
              value={robustnessFilter}
              onChange={(e) => setRobustnessFilter(e.target.value)}
              style={{ width: '100%', padding: '0.4rem 0.6rem', fontSize: '0.85rem', borderRadius: '0.375rem', border: '1px solid var(--border-medium)', backgroundColor: 'var(--bg-card)', color: 'var(--text-primary)' }}
            >
              <option value="">All Robustness Types</option>
              <option value="STABLE">STABLE</option>
              <option value="SENSITIVE">SENSITIVE</option>
              <option value="INSUFFICIENT_EVIDENCE">INSUFFICIENT_EVIDENCE</option>
            </select>
          </div>

          <button
            type="button"
            className="btn-history-toggle"
            onClick={handleResetFilters}
            style={{ height: '34px' }}
          >
            Reset Filters
          </button>
        </div>
      </div>

      {loading && (
        <div className="card loading-card" role="status">
          <div className="spinner" aria-hidden="true"></div>
          <p>Searching investigation records...</p>
        </div>
      )}

      {error && (
        <div className="card error-card" role="alert">
          <span className="error-icon" aria-hidden="true">⚠️</span>
          <p>{error}</p>
        </div>
      )}

      {!loading && !error && (
        <div className="card history-table-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: '600' }}>
              Historical Investigations ({investigations.length})
            </h3>
            {userRole === 'ANALYST' && (
              <span className="badge badge-platform">Showing your investigations only</span>
            )}
          </div>

          {investigations.length === 0 ? (
            <p className="no-data-text">No investigations found matching your filter criteria.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table" style={{ width: '100%', fontSize: '0.85rem', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ backgroundColor: 'var(--bg-card-subtle)', textAlign: 'left' }}>
                    <th style={{ padding: '0.5rem 0.75rem' }}>Question</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>Status</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>Robustness</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>Evidence</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>Created</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {investigations.map((inv) => (
                    <tr key={inv.investigation_id} style={{ borderBottom: '1px solid var(--border-light)' }}>
                      <td style={{ padding: '0.5rem 0.75rem', fontWeight: '500' }}>
                        <div>{inv.question}</div>
                        <code style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>{inv.investigation_id}</code>
                      </td>
                      <td style={{ padding: '0.5rem 0.75rem' }}>
                        <span className={`status-pill pill-${inv.status.toLowerCase()}`}>{inv.status}</span>
                      </td>
                      <td style={{ padding: '0.5rem 0.75rem' }}>
                        <span className={`robustness-pill rob-${(inv.robustness_status || 'STABLE').toLowerCase()}`}>
                          {inv.robustness_status || 'STABLE'}
                        </span>
                      </td>
                      <td style={{ padding: '0.5rem 0.75rem', color: 'var(--text-secondary)' }}>
                        {inv.evidence_count || 0} items
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
                          Load Thread →
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination Controls */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-light)' }}>
            <button
              type="button"
              className="btn-history-toggle"
              disabled={offset === 0}
              onClick={() => setOffset((prev) => Math.max(0, prev - limit))}
            >
              ← Previous
            </button>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Showing {offset + 1} - {offset + investigations.length}
            </span>
            <button
              type="button"
              className="btn-history-toggle"
              disabled={investigations.length < limit}
              onClick={() => setOffset((prev) => prev + limit)}
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
