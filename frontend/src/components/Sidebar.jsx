import React from 'react';

/**
 * Navigation item descriptors matching the official VERIDEX interactive prototype.
 */
const NAV_ITEMS = [
  {
    key: 'overview',
    label: 'Overview',
    description: 'Application overview dashboard',
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
      </svg>
    )
  },
  {
    key: 'investigations',
    label: 'Investigations',
    description: 'AI-assisted investigation workspace',
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
    )
  },
  {
    key: 'sources',
    label: 'Data Sources',
    description: 'Connected databases and datasets',
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <ellipse cx="12" cy="5" rx="9" ry="3" />
        <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
        <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
      </svg>
    )
  },
  {
    key: 'evidence',
    label: 'Evidence',
    description: 'Evidence explorer and provenance catalog',
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
        <polyline points="10 9 9 9 8 9" />
      </svg>
    )
  },
  {
    key: 'decisions',
    label: 'Decisions',
    description: 'Decision intelligence and candidate rankings',
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
      </svg>
    )
  },
  {
    key: 'history',
    label: 'History',
    description: 'Historical investigation audit log',
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 12 16 14" />
      </svg>
    )
  },
  {
    key: 'settings',
    label: 'Settings',
    description: 'Workspace, security and preferences',
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
      </svg>
    )
  }
];

/**
 * Persistent sidebar component matching the VERIDEX official prototype layout.
 *
 * @param {string} activeView - The currently active view key.
 * @param {Function} onSelectView - Handler when a navigation item is selected.
 * @param {Object} currentUser - Current authenticated user (from Phase 9.5H RBAC).
 * @param {string} workspaceName - Current workspace name (e.g. "Acme Retail").
 */
export function Sidebar({
  activeView = 'investigations',
  onSelectView,
  currentUser = null,
  workspaceName = 'Acme Retail'
}) {
  const userInitials = currentUser?.full_name
    ? currentUser.full_name.charAt(0).toUpperCase()
    : 'G';

  const userRoleDisplay = currentUser?.role
    ? currentUser.role.charAt(0).toUpperCase() + currentUser.role.slice(1).toLowerCase()
    : 'Analyst';

  return (
    <aside className="app-sidebar" aria-label="Main application sidebar">
      {/* Brand & Logo */}
      <button
        type="button"
        className="sidebar-brand-btn"
        onClick={() => onSelectView && onSelectView('overview')}
        title="Go to Overview"
        aria-label="VERIDEX logo, go to Overview"
      >
        <div className="brand-mark" aria-hidden="true" />
        <span className="brand-title">VERIDEX</span>
      </button>

      {/* Primary Navigation Links */}
      <nav className="sidebar-nav" aria-label="Primary navigation">
        {NAV_ITEMS.map((item) => {
          const isActive = activeView === item.key ||
            (item.key === 'decisions' && activeView === 'robustness') ||
            (item.key === 'investigations' && activeView === 'detail');
          return (
            <button
              key={item.key}
              type="button"
              className={`sidebar-nav-item ${isActive ? 'active' : ''}`}
              onClick={() => onSelectView && onSelectView(item.key)}
              aria-current={isActive ? 'page' : undefined}
              title={item.description}
            >
              <span className="nav-item-icon" aria-hidden="true">
                {item.icon}
              </span>
              <span className="nav-item-label">{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Workspace & Authenticated User Meta */}
      <div className="sidebar-footer-meta" aria-label="Workspace and user info">
        <div className="sidebar-ws-item" title={`Active workspace: ${workspaceName}`}>
          <span className="sidebar-avatar avatar-ws">AC</span>
          <div className="sidebar-ws-text">
            <span className="ws-name">{workspaceName}</span>
            <small className="ws-sub">Workspace</small>
          </div>
        </div>
        <div className="sidebar-ws-item" title={`User: ${currentUser?.full_name || 'Gagandeep'} (${userRoleDisplay})`}>
          <span className="sidebar-avatar avatar-user">{userInitials}</span>
          <div className="sidebar-ws-text">
            <span className="ws-name">{currentUser?.full_name || 'Gagandeep'}</span>
            <small className="ws-sub">{userRoleDisplay}</small>
          </div>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
