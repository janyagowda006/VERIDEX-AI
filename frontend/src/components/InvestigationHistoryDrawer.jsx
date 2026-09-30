import React, { useState, useEffect, useCallback } from 'react';
import { listInvestigations } from '../api/client.js';

export function InvestigationHistoryDrawer({
  isOpen,
  onClose,
  onSelectInvestigation,
  useMock = false
}) {
  const [historyItems, setHistoryItems] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [robustnessFilter, setRobustnessFilter] = useState('');

  const loadHistory = useCallback(() => {
    let isMounted = true;
    setHistoryLoading(true);
    setHistoryError(null);

    listInvestigations(20, 0, useMock, searchTerm, statusFilter, robustnessFilter)
      .then((items) => {
        if (isMounted) {
          setHistoryItems(items || []);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setHistoryError(err.message || "Unable to load investigation history.");
        }
      })
      .finally(() => {
        if (isMounted) {
          setHistoryLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [useMock, searchTerm, statusFilter, robustnessFilter]);

  useEffect(() => {
    if (!isOpen) return;
    return loadHistory();
  }, [isOpen, loadHistory]);

  const handleResetFilters = () => {
    setSearchTerm('');
    setStatusFilter('');
    setRobustnessFilter('');
  };

  if (!isOpen) return null;

  const hasActiveFilters = Boolean(searchTerm || statusFilter || robustnessFilter);

  return (
    <div className="history-drawer-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-label="Investigation History Drawer">
      <div className="history-drawer-panel" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <div className="header-title-group">
            <span className="header-icon" aria-hidden="true">📜</span>
            <div>
              <h3>Investigation Audit History</h3>
              <p className="header-subtitle">Browse, filter & load persistent business investigations</p>
            </div>
          </div>
          <button
            type="button"
            className="drawer-close-btn"
            onClick={onClose}
            aria-label="Close history drawer"
          >
            ✕
          </button>
        </div>

        <div className="drawer-body">
          {/* Search & Filter Bar */}
          <div className="drawer-filter-bar">
            <div className="filter-input-wrapper">
              <input
                type="text"
                className="filter-search-input"
                placeholder="Search question or ID..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                aria-label="Search investigations by question or ID"
              />
              {searchTerm && (
                <button
                  type="button"
                  className="filter-search-clear"
                  onClick={() => setSearchTerm('')}
                  aria-label="Clear search input"
                >
                  ✕
                </button>
              )}
            </div>

            <div className="filter-select-row">
              <select
                className="filter-select"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                aria-label="Filter by lifecycle status"
              >
                <option value="">All Statuses</option>
                <option value="COMPLETED">COMPLETED</option>
                <option value="REQUIRES_REVIEW">REQUIRES_REVIEW</option>
                <option value="FAILED">FAILED</option>
                <option value="IN_PROGRESS">IN_PROGRESS</option>
              </select>

              <select
                className="filter-select"
                value={robustnessFilter}
                onChange={(e) => setRobustnessFilter(e.target.value)}
                aria-label="Filter by robustness status"
              >
                <option value="">All Robustness</option>
                <option value="STABLE">STABLE</option>
                <option value="SENSITIVE">SENSITIVE</option>
                <option value="INSUFFICIENT_EVIDENCE">INSUFFICIENT_EVIDENCE</option>
              </select>

              {hasActiveFilters && (
                <button
                  type="button"
                  className="btn-clear-filters"
                  onClick={handleResetFilters}
                  aria-label="Reset all search filters"
                >
                  Reset
                </button>
              )}
            </div>
          </div>

          {historyLoading && (
            <div className="drawer-loading" role="status">
              <span className="btn-spinner" aria-hidden="true"></span>
              <span>Searching investigation records...</span>
            </div>
          )}

          {historyError && (
            <div className="drawer-error" role="alert">
              <span className="error-icon" aria-hidden="true">⚠️</span>
              <span>{historyError}</span>
            </div>
          )}

          {!historyLoading && !historyError && historyItems.length === 0 && (
            <div className="drawer-empty">
              <p>
                {hasActiveFilters
                  ? "No historical investigations match your search filters."
                  : "No historical investigations found."}
              </p>
              {hasActiveFilters && (
                <button
                  type="button"
                  className="btn-reset-empty-filters"
                  onClick={handleResetFilters}
                >
                  Clear Search Filters
                </button>
              )}
            </div>
          )}

          {!historyLoading && !historyError && historyItems.length > 0 && (
            <div className="history-items-list">
              {historyItems.map((item) => {
                const statusKey = (item.status || 'COMPLETED').toLowerCase().replace(/_/g, '-');
                const robKey = (item.robustness_status || 'STABLE').toLowerCase().replace(/_/g, '-');

                return (
                  <div key={item.investigation_id} className={`history-item-card card-status-${statusKey}`}>
                    <div className="item-top-bar">
                      <span className={`status-badge badge-${statusKey}`}>
                        {item.status}
                      </span>
                      {item.robustness_status && (
                        <span className={`robustness-pill pill-${robKey}`}>
                          {item.robustness_status}
                        </span>
                      )}
                    </div>

                    <h4 className="item-question">{item.question}</h4>

                    <div className="item-meta-row">
                      <span className="item-id">{item.investigation_id}</span>
                      <span className="item-date">
                        {item.created_at ? new Date(item.created_at).toLocaleDateString() : '—'}
                      </span>
                    </div>

                    <div className="item-stats-chips">
                      <span className="stat-chip">Evidence: {item.evidence_count ?? 0}</span>
                      <span className="stat-chip">Claims: {item.claims_count ?? 0}</span>
                      <span className="stat-chip">Turns: {item.turns_used ?? 1}</span>
                      {item.execution_time_ms && (
                        <span className="stat-chip">{Math.round(item.execution_time_ms)}ms</span>
                      )}
                    </div>

                    <div className="item-actions">
                      <button
                        type="button"
                        className="select-investigation-btn"
                        onClick={() => {
                          onSelectInvestigation(item.investigation_id);
                          onClose();
                        }}
                      >
                        Inspect Workspace →
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
