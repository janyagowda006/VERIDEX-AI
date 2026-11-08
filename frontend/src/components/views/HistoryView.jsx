import React, { useState, useEffect, useCallback } from 'react';
import { listInvestigations } from '../../api/client.js';

export function HistoryView({
  onSelectInvestigation,
  onNavigate,
  currentUser = null,
  useMock = false
}) {
  const [investigations, setInvestigations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filter & Search states
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [robustnessFilter, setRobustnessFilter] = useState('');
  const [mineOnly, setMineOnly] = useState(false);

  // Pagination states
  const [limit, setLimit] = useState(20);
  const [offset, setOffset] = useState(0);

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    setError(null);

    const ownerId = mineOnly && currentUser?.user_id ? currentUser.user_id : null;

    try {
      const records = await listInvestigations(
        limit,
        offset,
        useMock,
        searchTerm.trim() || null,
        statusFilter || null,
        robustnessFilter || null,
        ownerId
      );
      setInvestigations(Array.isArray(records) ? records : []);
    } catch (err) {
      setError(err.detail || err.message || 'Failed to load investigation history from backend.');
    } finally {
      setLoading(false);
    }
  }, [limit, offset, useMock, searchTerm, statusFilter, robustnessFilter, mineOnly, currentUser]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const handleResetFilters = () => {
    setSearchTerm('');
    setStatusFilter('');
    setRobustnessFilter('');
    setMineOnly(false);
    setOffset(0);
  };

  const handleNextPage = () => {
    setOffset((prev) => prev + limit);
  };

  const handlePrevPage = () => {
    setOffset((prev) => Math.max(0, prev - limit));
  };

  const formatTimestamp = (isoString) => {
    if (!isoString) return '—';
    try {
      const d = new Date(isoString);
      if (isNaN(d.getTime())) return isoString;
      return d.toLocaleString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return isoString;
    }
  };

  const hasActiveFilters = Boolean(searchTerm || statusFilter || robustnessFilter || mineOnly);

  return (
    <div className="view-shell history-view-shell" role="region" aria-label="Investigation History">
      {/* Header */}
      <div className="history-view-header">
        <div>
          <h1 className="history-view-title">Investigation Audit History</h1>
          <p className="history-view-subtitle">
            Immutable, audit-ready record of all natural language business investigations and human reviews.
          </p>
        </div>
        <div className="history-header-actions">
          <button
            type="button"
            className="btn btn-outline btn-sm"
            onClick={fetchHistory}
            disabled={loading}
            aria-label="Refresh investigation records"
          >
            <span className="btn-icon" aria-hidden="true">↻</span>
            Refresh
          </button>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() => onNavigate && onNavigate('investigations')}
          >
            + New Investigation
          </button>
        </div>
      </div>

      {/* Filter & Search Bar Card */}
      <div className="card history-filter-card">
        <div className="history-filter-row">
          <div className="filter-search-box">
            <span className="search-icon" aria-hidden="true">🔍</span>
            <input
              type="text"
              className="history-search-input"
              placeholder="Search by question or investigation ID..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setOffset(0);
              }}
              aria-label="Search investigations"
            />
            {searchTerm && (
              <button
                type="button"
                className="filter-clear-btn"
                onClick={() => setSearchTerm('')}
                aria-label="Clear search"
              >
                ✕
              </button>
            )}
          </div>

          <div className="filter-select-group">
            <select
              className="filter-select"
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setOffset(0);
              }}
              aria-label="Filter by lifecycle status"
            >
              <option value="">Status: All</option>
              <option value="COMPLETED">Completed</option>
              <option value="REQUIRES_REVIEW">Requires Review</option>
              <option value="FAILED">Failed</option>
              <option value="IN_PROGRESS">In Progress</option>
            </select>

            <select
              className="filter-select"
              value={robustnessFilter}
              onChange={(e) => {
                setRobustnessFilter(e.target.value);
                setOffset(0);
              }}
              aria-label="Filter by robustness status"
            >
              <option value="">Robustness: All</option>
              <option value="STABLE">✓ Stable</option>
              <option value="SENSITIVE">◐ Sensitive</option>
              <option value="INSUFFICIENT_EVIDENCE">○ Insufficient</option>
            </select>

            {currentUser && (
              <label className="filter-checkbox-label">
                <input
                  type="checkbox"
                  checked={mineOnly}
                  onChange={(e) => {
                    setMineOnly(e.target.checked);
                    setOffset(0);
                  }}
                />
                <span>My Investigations</span>
              </label>
            )}

            {hasActiveFilters && (
              <button
                type="button"
                className="btn btn-outline btn-xs"
                onClick={handleResetFilters}
              >
                Reset Filters
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Main Table Card */}
      <div className="card history-table-card">
        {loading ? (
          <div className="history-state-container" role="status">
            <span className="btn-spinner" aria-hidden="true"></span>
            <span>Loading investigation audit records...</span>
          </div>
        ) : error ? (
          <div className="history-state-container history-error-state" role="alert">
            <span className="error-icon" aria-hidden="true">⚠️</span>
            <p>{error}</p>
            <button
              type="button"
              className="btn btn-outline btn-sm"
              onClick={fetchHistory}
            >
              Retry Connection
            </button>
          </div>
        ) : investigations.length === 0 ? (
          <div className="history-state-container history-empty-state">
            <span className="empty-icon" aria-hidden="true">📜</span>
            <h3>{hasActiveFilters ? 'No Matching Investigations' : 'No Investigations Recorded Yet'}</h3>
            <p>
              {hasActiveFilters
                ? 'Try adjusting or clearing your filters to see historical audit records.'
                : 'Run an investigation from the workspace to record evidence, decision evaluations, and robustness analysis.'}
            </p>
            {hasActiveFilters ? (
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={handleResetFilters}
              >
                Clear Filters
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => onNavigate && onNavigate('investigations')}
              >
                Start an Investigation →
              </button>
            )}
          </div>
        ) : (
          <div className="table-responsive-wrapper">
            <table className="data-table history-data-table">
              <thead>
                <tr>
                  <th>Investigation ID</th>
                  <th>Business Question</th>
                  <th>Created</th>
                  <th>Status</th>
                  <th>Robustness</th>
                  <th>Evidence</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {investigations.map((inv) => {
                  const status = inv.status || 'COMPLETED';
                  const robStatus = inv.robustness_status || 'STABLE';

                  const statusBadgeClass =
                    status === 'COMPLETED'
                      ? 'b-ok'
                      : status === 'REQUIRES_REVIEW'
                        ? 'b-warn'
                        : status === 'FAILED'
                          ? 'b-fail'
                          : 'b-neu';

                  const robBadgeClass =
                    robStatus === 'STABLE'
                      ? 'b-ok'
                      : robStatus === 'SENSITIVE'
                        ? 'b-warn'
                        : 'b-neu';

                  return (
                    <tr
                      key={inv.investigation_id}
                      className="history-row pointer"
                      onClick={() => onSelectInvestigation && onSelectInvestigation(inv.investigation_id)}
                    >
                      <td>
                        <span className="history-id-code">{inv.investigation_id}</span>
                      </td>
                      <td className="history-question-cell">
                        <strong>{inv.question}</strong>
                        {inv.answer && (
                          <p className="history-snippet">
                            {inv.answer.length > 110 ? `${inv.answer.slice(0, 110)}...` : inv.answer}
                          </p>
                        )}
                      </td>
                      <td className="history-time-cell">
                        {formatTimestamp(inv.created_at)}
                      </td>
                      <td>
                        <span className={`status-badge ${statusBadgeClass}`}>
                          {status.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td>
                        <span className={`status-badge ${robBadgeClass}`}>
                          {robStatus === 'STABLE' ? '✓ Stable' : robStatus === 'SENSITIVE' ? '◐ Sensitive' : '○ Insufficient'}
                        </span>
                      </td>
                      <td className="history-evidence-cell">
                        {inv.evidence_count ?? 0} items
                      </td>
                      <td>
                        <button
                          type="button"
                          className="btn btn-outline btn-xs"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (onSelectInvestigation) onSelectInvestigation(inv.investigation_id);
                          }}
                        >
                          Audit Detail →
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        {!loading && !error && investigations.length > 0 && (
          <div className="history-pagination-row">
            <div className="pagination-info">
              Showing records {offset + 1} – {offset + investigations.length}
            </div>
            <div className="pagination-controls">
              <label className="limit-selector-label">
                <span>Page size:</span>
                <select
                  className="limit-select"
                  value={limit}
                  onChange={(e) => {
                    setLimit(Number(e.target.value));
                    setOffset(0);
                  }}
                >
                  <option value={10}>10</option>
                  <option value={20}>20</option>
                  <option value={50}>50</option>
                </select>
              </label>

              <button
                type="button"
                className="btn btn-outline btn-xs"
                onClick={handlePrevPage}
                disabled={offset === 0}
              >
                ← Previous
              </button>
              <button
                type="button"
                className="btn btn-outline btn-xs"
                onClick={handleNextPage}
                disabled={investigations.length < limit}
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default HistoryView;

