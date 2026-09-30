import React, { useState, useEffect } from 'react';
import { getAnalyticsSummary } from '../api/client.js';

export function GlobalAnalyticsPanel({
  isOpen,
  onClose,
  useMock = false
}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isOpen) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    getAnalyticsSummary(useMock)
      .then((res) => {
        if (isMounted) {
          setData(res);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || "Failed to load global analytics summary.");
        }
      })
      .finally(() => {
        if (isMounted) {
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, useMock]);

  if (!isOpen) return null;

  const totalInv = data?.total_investigations || 0;
  const totalRev = data?.total_reviews || 0;

  const statusCounts = data?.status_counts || {};
  const reviewCounts = data?.review_counts || {};
  const robustnessCounts = data?.robustness_counts || {};

  const robustnessTotal = (robustnessCounts.STABLE || 0) +
                          (robustnessCounts.SENSITIVE || 0) +
                          (robustnessCounts.INSUFFICIENT_EVIDENCE || 0);

  const formatPct = (val, total) => {
    if (!total || total <= 0) return '0.0%';
    const pct = ((val || 0) / total) * 100;
    return `${pct.toFixed(1)}%`;
  };

  const getWidthPct = (val, total) => {
    if (!total || total <= 0) return 0;
    return Math.min(100, Math.max(0, ((val || 0) / total) * 100));
  };

  return (
    <div
      className="analytics-drawer-overlay"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Global Analytics Panel"
    >
      <div className="analytics-drawer-panel" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="drawer-header">
          <div className="header-title-group">
            <span className="header-icon" aria-hidden="true">📊</span>
            <div>
              <h3>Global Analytics</h3>
              <p className="header-subtitle">Platform-wide investigation and audit metrics</p>
            </div>
          </div>
          <button
            type="button"
            className="drawer-close-btn"
            onClick={onClose}
            aria-label="Close global analytics panel"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="drawer-body">
          {loading && (
            <div className="drawer-loading" role="status">
              <span className="btn-spinner" aria-hidden="true"></span>
              <span>Loading platform analytics metrics...</span>
            </div>
          )}

          {error && (
            <div className="drawer-error" role="alert">
              <span className="error-icon" aria-hidden="true">⚠️</span>
              <span>{error}</span>
            </div>
          )}

          {!loading && !error && data && (
            <div className="analytics-content">
              {/* KPI Summary Cards */}
              <section className="analytics-section" aria-label="Key Performance Indicators">
                <h4 className="analytics-section-title">Key Performance Indicators</h4>
                <div className="analytics-kpi-grid">
                  <div className="analytics-kpi-card">
                    <span className="kpi-label">Total Investigations</span>
                    <span className="kpi-value">{totalInv}</span>
                  </div>

                  <div className="analytics-kpi-card">
                    <span className="kpi-label">Total Human Reviews</span>
                    <span className="kpi-value">{totalRev}</span>
                  </div>

                  <div className="analytics-kpi-card">
                    <span className="kpi-label">Average Execution Time</span>
                    <span className="kpi-value">
                      {data.average_execution_time_ms !== null && data.average_execution_time_ms !== undefined
                        ? `${data.average_execution_time_ms} ms`
                        : 'N/A'}
                    </span>
                  </div>
                </div>
              </section>

              {/* Investigation Status Distribution */}
              <section className="analytics-section" aria-label="Investigation Status Distribution">
                <h4 className="analytics-section-title">Investigation Status Distribution</h4>
                <div className="distribution-list">
                  {[
                    { key: 'COMPLETED', label: 'Completed', colorClass: 'bar-completed' },
                    { key: 'REQUIRES_REVIEW', label: 'Requires Review', colorClass: 'bar-requires-review' },
                    { key: 'FAILED', label: 'Failed', colorClass: 'bar-failed' },
                    { key: 'IN_PROGRESS', label: 'In Progress', colorClass: 'bar-in-progress' }
                  ].map(({ key, label, colorClass }) => {
                    const cnt = statusCounts[key] || 0;
                    const pctStr = formatPct(cnt, totalInv);
                    const widthPct = getWidthPct(cnt, totalInv);

                    return (
                      <div key={key} className="distribution-item">
                        <div className="dist-meta-row">
                          <span className="dist-label">{label}</span>
                          <span className="dist-value">
                            <strong>{cnt}</strong> ({pctStr})
                          </span>
                        </div>
                        <div className="dist-bar-track">
                          <div
                            className={`dist-bar-fill ${colorClass}`}
                            style={{ width: `${widthPct}%` }}
                            aria-valuenow={cnt}
                            aria-valuemin={0}
                            aria-valuemax={totalInv}
                          ></div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>

              {/* Human Review Distribution */}
              <section className="analytics-section" aria-label="Human Review Decision Distribution">
                <h4 className="analytics-section-title">Human Review Decision Distribution</h4>
                <div className="distribution-list">
                  {[
                    { key: 'APPROVED', label: 'Approved', colorClass: 'bar-approved' },
                    { key: 'REJECTED', label: 'Rejected', colorClass: 'bar-rejected' },
                    { key: 'FLAGGED', label: 'Flagged', colorClass: 'bar-flagged' }
                  ].map(({ key, label, colorClass }) => {
                    const cnt = reviewCounts[key] || 0;
                    const pctStr = formatPct(cnt, totalRev);
                    const widthPct = getWidthPct(cnt, totalRev);

                    return (
                      <div key={key} className="distribution-item">
                        <div className="dist-meta-row">
                          <span className="dist-label">{label}</span>
                          <span className="dist-value">
                            <strong>{cnt}</strong> ({pctStr})
                          </span>
                        </div>
                        <div className="dist-bar-track">
                          <div
                            className={`dist-bar-fill ${colorClass}`}
                            style={{ width: `${widthPct}%` }}
                            aria-valuenow={cnt}
                            aria-valuemin={0}
                            aria-valuemax={totalRev}
                          ></div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>

              {/* Robustness Distribution */}
              <section className="analytics-section" aria-label="Robustness Status Distribution">
                <h4 className="analytics-section-title">Robustness Status Distribution</h4>
                <div className="distribution-list">
                  {[
                    { key: 'STABLE', label: 'Stable', colorClass: 'bar-stable' },
                    { key: 'SENSITIVE', label: 'Sensitive', colorClass: 'bar-sensitive' },
                    { key: 'INSUFFICIENT_EVIDENCE', label: 'Insufficient Evidence', colorClass: 'bar-insufficient' }
                  ].map(({ key, label, colorClass }) => {
                    const cnt = robustnessCounts[key] || 0;
                    const pctStr = formatPct(cnt, robustnessTotal);
                    const widthPct = getWidthPct(cnt, robustnessTotal);

                    return (
                      <div key={key} className="distribution-item">
                        <div className="dist-meta-row">
                          <span className="dist-label">{label}</span>
                          <span className="dist-value">
                            <strong>{cnt}</strong> ({pctStr})
                          </span>
                        </div>
                        <div className="dist-bar-track">
                          <div
                            className={`dist-bar-fill ${colorClass}`}
                            style={{ width: `${widthPct}%` }}
                            aria-valuenow={cnt}
                            aria-valuemin={0}
                            aria-valuemax={robustnessTotal}
                          ></div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
