import React from 'react';

/**
 * Prototype-aligned Navigation Sidebar for VERIDEX Decision Intelligence Engine.
 * Allows seamless navigation across product views while preserving active investigation state.
 */
export function Sidebar({ activeView, onSelectView, setActiveView, userRole = 'ANALYST', collapsed = false, onToggleCollapse, setCollapsed }) {
  const handleSelectView = (viewId) => {
    if (onSelectView) onSelectView(viewId);
    else if (setActiveView) setActiveView(viewId);
  };

  const handleToggle = () => {
    if (onToggleCollapse) onToggleCollapse();
    else if (setCollapsed) setCollapsed(!collapsed);
  };

  const isAuditorOrAdmin = userRole === 'AUDITOR' || userRole === 'ADMIN';

  const navItems = [
    { id: 'landing', label: 'Landing Page', icon: '🏠' },
    { id: 'overview', label: 'Overview', icon: '📊' },
    { id: 'workspace', label: 'Workspace', icon: '🔍' },
    { id: 'decisions', label: 'Decisions', icon: '🎯' },
    { id: 'evidence', label: 'Evidence', icon: '🔗' },
    { id: 'datasources', label: 'Data Sources', icon: '💾' },
    { id: 'history', label: 'History', icon: '📜' },
    { id: 'settings', label: 'Settings', icon: '⚙️' }
  ];

  if (isAuditorOrAdmin) {
    navItems.push({ id: 'audit', label: 'Audit Trail', icon: '🛡️' });
  }

  return (
    <aside className={`app-sidebar ${collapsed ? 'collapsed' : ''}`} aria-label="Sidebar Navigation">
      <div className="sidebar-header" style={{ padding: '1rem', borderBottom: '1px solid var(--border-light)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        {!collapsed && (
          <div
            className="brand-group"
            onClick={() => handleSelectView('landing')}
            style={{ gap: '0.5rem', cursor: 'pointer' }}
            title="Return to Landing Page"
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && handleSelectView('landing')}
          >
            <div className="brand-logo" aria-hidden="true" style={{ width: '28px', height: '28px', fontSize: '0.875rem' }}>
              <span className="logo-symbol">V</span>
            </div>
            <span style={{ fontWeight: '700', fontSize: '1rem', letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>VERIDEX</span>
          </div>
        )}
        <button
          type="button"
          className="btn-sidebar-toggle"
          onClick={handleToggle}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
            fontSize: '1rem',
            padding: '0.25rem'
          }}
        >
          {collapsed ? '▶' : '◀'}
        </button>
      </div>

      <nav className="sidebar-nav" style={{ padding: '0.75rem 0.5rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
        {navItems.map((item) => {
          const isActive = activeView === item.id || (item.id === 'workspace' && activeView === 'ask');
          return (
            <button
              key={item.id}
              type="button"
              className={`sidebar-nav-btn ${isActive ? 'active' : ''}`}
              onClick={() => handleSelectView(item.id)}
              title={collapsed ? item.label : undefined}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '0.6rem 0.75rem',
                borderRadius: '0.375rem',
                fontSize: '0.875rem',
                fontWeight: isActive ? '600' : '500',
                border: '1px solid',
                borderColor: isActive ? 'var(--border-medium)' : 'transparent',
                backgroundColor: isActive ? 'var(--bg-card-subtle)' : 'transparent',
                color: isActive ? 'var(--color-primary)' : 'var(--text-secondary)',
                cursor: 'pointer',
                textAlign: 'left',
                width: '100%'
              }}
            >
              <span className="nav-icon" aria-hidden="true" style={{ fontSize: '1rem' }}>{item.icon}</span>
              {!collapsed && <span>{item.label}</span>}
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
