import React, { useState } from 'react';
import { ThemeToggle } from '../ThemeToggle.jsx';

export function SettingsView({
  theme,
  onToggleTheme,
  useMock,
  onToggleMock,
  userRole,
  onSwitchRole,
  currentUser
}) {
  const [defaultTurns, setDefaultTurns] = useState(() => {
    try {
      return localStorage.getItem('veridex_default_turns') || '3';
    } catch {
      return '3';
    }
  });

  const [savedNotice, setSavedNotice] = useState(false);

  const handleSaveSettings = () => {
    try {
      localStorage.setItem('veridex_default_turns', defaultTurns);
      setSavedNotice(true);
      setTimeout(() => setSavedNotice(false), 3000);
    } catch {
      // fallback
    }
  };

  return (
    <div className="view-container settings-view">
      <div className="view-header">
        <div>
          <h2>Application Preferences & Settings</h2>
          <p className="view-subtitle">
            Frontend visual theme, environment mode, role switching, and session preferences.
          </p>
        </div>
      </div>

      <div className="settings-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem' }}>
        {/* Visual Appearance & Theme */}
        <div className="card settings-card">
          <div className="card-header" style={{ marginBottom: '1rem', borderBottom: '1px solid var(--border-light)', paddingBottom: '0.5rem' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>🎨</span> Appearance & Theme
            </h3>
          </div>
          <div className="setting-item" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <div>
              <strong>Color Theme Mode</strong>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: 0 }}>
                Switch between Light mode and Dark mode.
              </p>
            </div>
            <ThemeToggle theme={theme} onToggle={onToggleTheme} />
          </div>
        </div>

        {/* API & Data Mode */}
        <div className="card settings-card">
          <div className="card-header" style={{ marginBottom: '1rem', borderBottom: '1px solid var(--border-light)', paddingBottom: '0.5rem' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>⚡</span> API Execution Mode
            </h3>
          </div>
          <div className="setting-item" style={{ marginBottom: '1rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <div>
                <strong>Execution Source</strong>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: 0 }}>
                  Select backend live server or deterministic mock provider.
                </p>
              </div>
              <button
                type="button"
                className={`btn-mode-toggle ${useMock ? 'mock' : 'live'}`}
                onClick={() => onToggleMock(!useMock)}
                style={{
                  padding: '0.35rem 0.75rem',
                  fontSize: '0.8125rem',
                  fontWeight: '600',
                  borderRadius: '0.375rem',
                  border: '1px solid var(--border-medium)',
                  backgroundColor: useMock ? 'var(--color-primary-subtle)' : 'var(--color-success-bg)',
                  color: useMock ? 'var(--color-primary)' : 'var(--color-success-text)',
                  cursor: 'pointer'
                }}
              >
                {useMock ? 'Mock API Mode' : 'Live API Mode'}
              </button>
            </div>
          </div>
        </div>

        {/* User Identity & Role Switcher */}
        <div className="card settings-card">
          <div className="card-header" style={{ marginBottom: '1rem', borderBottom: '1px solid var(--border-light)', paddingBottom: '0.5rem' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>👤</span> User Identity & Role Selection
            </h3>
          </div>
          <div className="setting-item" style={{ marginBottom: '1rem' }}>
            <label htmlFor="roleSelect" style={{ display: 'block', fontWeight: '600', fontSize: '0.875rem', marginBottom: '0.35rem' }}>
              Active RBAC Testing Role
            </label>
            <select
              id="roleSelect"
              value={userRole}
              onChange={(e) => onSwitchRole(e.target.value)}
              style={{
                width: '100%',
                padding: '0.5rem',
                borderRadius: '0.375rem',
                border: '1px solid var(--border-medium)',
                backgroundColor: 'var(--bg-card)',
                color: 'var(--text-primary)',
                fontSize: '0.875rem'
              }}
            >
              <option value="ANALYST">ANALYST (Alice Analyst - Lead Analyst)</option>
              <option value="REVIEWER">REVIEWER (Bob Reviewer - Senior Reviewer)</option>
              <option value="AUDITOR">AUDITOR (Carol Auditor - Compliance Auditor)</option>
              <option value="ADMIN">ADMIN (Dave Admin - System Admin)</option>
            </select>
            <p style={{ fontSize: '0.78125rem', color: 'var(--text-tertiary)', marginTop: '0.35rem' }}>
              Current User: <code>{currentUser?.full_name || userRole}</code> ({currentUser?.email})
            </p>
          </div>
        </div>

        {/* Investigation Pipeline Defaults */}
        <div className="card settings-card">
          <div className="card-header" style={{ marginBottom: '1rem', borderBottom: '1px solid var(--border-light)', paddingBottom: '0.5rem' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>⚙️</span> Investigation Pipeline Defaults
            </h3>
          </div>
          <div className="setting-item" style={{ marginBottom: '1rem' }}>
            <label htmlFor="turnsInput" style={{ display: 'block', fontWeight: '600', fontSize: '0.875rem', marginBottom: '0.35rem' }}>
              Default Max Investigation Turns: {defaultTurns}
            </label>
            <input
              id="turnsInput"
              type="range"
              min="1"
              max="5"
              value={defaultTurns}
              onChange={(e) => setDefaultTurns(e.target.value)}
              style={{ width: '100%' }}
            />
            <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
              Bounded multi-turn memory limit ($K \le 5$).
            </span>
          </div>

          <button
            type="button"
            className="submit-review-btn"
            onClick={handleSaveSettings}
            style={{ width: '100%', marginTop: '0.5rem' }}
          >
            Save Preferences
          </button>

          {savedNotice && (
            <p style={{ fontSize: '0.8rem', color: 'var(--color-success)', marginTop: '0.5rem', textAlign: 'center' }}>
              ✓ Preferences saved to local storage.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
