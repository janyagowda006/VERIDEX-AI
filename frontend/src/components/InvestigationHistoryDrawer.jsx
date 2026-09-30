import React, { useState, useEffect } from 'react';
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

  useEffect(() => {
    if (!isOpen) return;

    let isMounted = true;
    setHistoryLoading(true);
    setHistoryError(null);

    listInvestigations(20, 0, useMock)
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
  }, [isOpen, useMock]);

  if (!isOpen) return null;

  return (
    <div className="history-drawer-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-label="Investigation History Drawer">
      <div className="history-drawer-panel" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <div className="header-title-group">
            <span className="header-icon" aria-hidden="true">📜</span>
            <div>
              <h3>Investigation Audit History</h3>
              <p className="header-subtitle">Browse & load persistent business investigations</p>
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
          {historyLoading && (
            <div className="drawer-loading" role="status">
              <span className="btn-spinner" aria-hidden="true"></span>
              <span>Loading investigation records...</span>
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
              <p>No historical investigations found.</p>
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
