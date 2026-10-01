import React, { useState, useEffect } from 'react';
import { listAuditLogs } from '../../api/client.js';

export function AuditTrailView({ useMock = false, currentUser }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const userRole = currentUser?.role || 'ANALYST';
  const isAuthorized = userRole === 'AUDITOR' || userRole === 'ADMIN';

  useEffect(() => {
    if (!isAuthorized) {
      setLoading(false);
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError(null);

    listAuditLogs(useMock)
      .then((data) => {
        if (isMounted) {
          setLogs(data || []);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || 'Failed to load security audit logs.');
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [useMock, isAuthorized]);

  if (!isAuthorized) {
    return (
      <div className="view-container audit-trail-view">
        <div className="view-header">
          <h2>Enterprise Security Audit Trail</h2>
        </div>
        <div className="card error-card" role="alert" style={{ backgroundColor: 'var(--bg-card-subtle)', borderColor: 'var(--border-medium)', color: 'var(--text-secondary)' }}>
          <span className="error-icon" aria-hidden="true">🔒</span>
          <div>
            <h3>Access Restricted (HTTP 403 Forbidden)</h3>
            <p>
              Security audit trail logging is restricted exclusively to <code>AUDITOR</code> and <code>ADMIN</code> roles.
              Your current active role is <code>{userRole}</code>.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="view-container audit-trail-view">
      <div className="view-header">
        <div>
          <h2>Enterprise Security Audit Trail Event Sink</h2>
          <p className="view-subtitle">
            Immutable application audit log capturing authentication, review governance, and report exports.
          </p>
        </div>
        <span className="badge badge-platform">Append-Only Event Sink</span>
      </div>

      {loading && (
        <div className="card loading-card" role="status">
          <div className="spinner" aria-hidden="true"></div>
          <p>Loading security audit log entries...</p>
        </div>
      )}

      {error && (
        <div className="card error-card" role="alert">
          <span className="error-icon" aria-hidden="true">⚠️</span>
          <p>{error}</p>
        </div>
      )}

      {!loading && !error && (
        <div className="card audit-table-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: '600' }}>
              Recorded Events ({logs.length})
            </h3>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
              Ordered newest-first (timestamp DESC)
            </span>
          </div>

          {logs.length === 0 ? (
            <p className="no-data-text">No audit log events recorded yet.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table" style={{ width: '100%', fontSize: '0.85rem', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ backgroundColor: 'var(--bg-card-subtle)', textAlign: 'left' }}>
                    <th style={{ padding: '0.5rem 0.75rem' }}>Timestamp</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>Action Type</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>User ID</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>Role</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>Resource ID</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>Status</th>
                    <th style={{ padding: '0.5rem 0.75rem' }}>IP Address</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => (
                    <tr key={log.id} style={{ borderBottom: '1px solid var(--border-light)' }}>
                      <td style={{ padding: '0.5rem 0.75rem', whiteSpace: 'nowrap', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                        {new Date(log.timestamp).toLocaleString()}
                      </td>
                      <td style={{ padding: '0.5rem 0.75rem' }}>
                        <span className="badge badge-platform" style={{ fontWeight: '600' }}>{log.action_type}</span>
                      </td>
                      <td style={{ padding: '0.5rem 0.75rem' }}><code>{log.user_id || 'unauthenticated'}</code></td>
                      <td style={{ padding: '0.5rem 0.75rem' }}>
                        <span style={{ fontWeight: '500' }}>{log.user_role || 'N/A'}</span>
                      </td>
                      <td style={{ padding: '0.5rem 0.75rem' }}><code>{log.resource_id || '-'}</code></td>
                      <td style={{ padding: '0.5rem 0.75rem' }}>
                        <span className={`status-pill pill-${log.status.toLowerCase()}`}>
                          {log.status}
                        </span>
                      </td>
                      <td style={{ padding: '0.5rem 0.75rem', fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
                        {log.ip_address || '127.0.0.1'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
