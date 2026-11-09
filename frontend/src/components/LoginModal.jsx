import React, { useState } from 'react';

const SEEDED_ACCOUNTS = [
  {
    role: 'ANALYST',
    email: 'analyst@veridex.ai',
    name: 'Alice Analyst',
    desc: 'Runs investigations & views own query history'
  },
  {
    role: 'REVIEWER',
    email: 'reviewer@veridex.ai',
    name: 'Bob Reviewer',
    desc: 'Approves, rejects & flags decision recommendations'
  },
  {
    role: 'AUDITOR',
    email: 'auditor@veridex.ai',
    name: 'Carol Auditor',
    desc: 'Inspects compliance traces & exports reports'
  },
  {
    role: 'ADMIN',
    email: 'admin@veridex.ai',
    name: 'Dave Admin',
    desc: 'Full system privileges & database inspection'
  }
];

export function LoginModal({ isOpen, onClose, onLogin, initialError = null }) {
  const [email, setEmail] = useState('analyst@veridex.ai');
  const [password, setPassword] = useState('password123');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(initialError);
  const [useMock, setUseMock] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    const cleanEmail = email.trim();
    if (!cleanEmail) {
      setError('Email address is required.');
      return;
    }
    if (!password) {
      setError('Password is required.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await onLogin(cleanEmail, password, useMock);
      if (onClose) onClose();
    } catch (err) {
      const msg = err.detail || err.message || 'Authentication failed. Please check credentials or backend status.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectQuickAccount = (acc) => {
    setEmail(acc.email);
    setPassword('password123');
    setError(null);
  };

  return (
    <div className="login-modal-overlay" role="dialog" aria-modal="true" aria-labelledby="login-title">
      <div className="login-modal-card">
        {/* Header */}
        <div className="login-header">
          <div className="login-brand">
            <div className="brand-mark" aria-hidden="true" />
            <span className="brand-title">VERIDEX</span>
          </div>
          <h2 id="login-title" className="login-heading">Sign In to Decision Intelligence</h2>
          <p className="login-subheading">
            Enterprise role-based access for verifiable AI decision analysis.
          </p>
        </div>

        {/* Error Notice */}
        {error && (
          <div className="login-error-banner" role="alert">
            <span className="error-icon" aria-hidden="true">⚠️</span>
            <span>{error}</span>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="login-email" className="form-label">
              Enterprise Email
            </label>
            <input
              id="login-email"
              type="email"
              className="form-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="e.g. analyst@veridex.ai"
              disabled={loading}
              autoComplete="username"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="login-password" className="form-label">
              Password
            </label>
            <input
              id="login-password"
              type="password"
              className="form-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              disabled={loading}
              autoComplete="current-password"
              required
            />
          </div>

          {/* Quick Seed Accounts Selector */}
          <div className="quick-accounts-section">
            <span className="quick-accounts-label">Select Standard Enterprise Role:</span>
            <div className="quick-accounts-grid">
              {SEEDED_ACCOUNTS.map((acc) => {
                const isSelected = email === acc.email;
                return (
                  <button
                    key={acc.role}
                    type="button"
                    className={`quick-acc-btn ${isSelected ? 'active' : ''}`}
                    onClick={() => handleSelectQuickAccount(acc)}
                    disabled={loading}
                    title={acc.desc}
                  >
                    <span className="quick-acc-role">{acc.role}</span>
                    <span className="quick-acc-name">{acc.name}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Offline Mock Mode Option */}
          <div className="login-options-row">
            <label className="checkbox-label" title="Enable mock mode for offline testing without a running backend">
              <input
                type="checkbox"
                checked={useMock}
                onChange={(e) => setUseMock(e.target.checked)}
                disabled={loading}
              />
              <span className="checkbox-text">Offline Dev Mode (Mock Auth)</span>
            </label>
          </div>

          {/* Submit Button */}
          <div className="login-actions">
            <button
              type="submit"
              className="btn btn-primary btn-block"
              disabled={loading}
            >
              {loading ? (
                <span className="btn-loading-content">
                  <span className="btn-spinner" aria-hidden="true"></span>
                  <span>Signing In...</span>
                </span>
              ) : (
                <span>Sign In to VERIDEX →</span>
              )}
            </button>
          </div>
        </form>

        <div className="login-footer">
          <small>Traceable Evidence • Deterministic Calculations • Human Decisions</small>
        </div>
      </div>
    </div>
  );
}

export default LoginModal;

