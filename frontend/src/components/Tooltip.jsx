import React, { useState } from 'react';

/**
 * Accessible Tooltip component providing hover/focus context details.
 * Supports keyboard navigation and screen readers.
 */
export function Tooltip({ text, children, position = 'top' }) {
  const [visible, setVisible] = useState(false);

  if (!text) return children;

  return (
    <span
      className="tooltip-wrapper"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
      style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}
    >
      {children}
      {visible && (
        <span
          className={`tooltip-bubble tooltip-${position}`}
          role="tooltip"
          aria-hidden={!visible}
          style={{
            position: 'absolute',
            zIndex: 100,
            padding: '0.35rem 0.6rem',
            fontSize: '0.75rem',
            fontWeight: '500',
            lineHeight: '1.3',
            color: 'var(--text-on-dark, #ffffff)',
            backgroundColor: 'var(--bg-tooltip, #1e293b)',
            borderRadius: '0.375rem',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.2)',
            pointerEvents: 'none',
            whiteSpace: 'nowrap',
            border: '1px solid var(--border-medium, #334155)',
            bottom: position === 'top' ? '125%' : 'auto',
            top: position === 'bottom' ? '125%' : 'auto',
            left: '50%',
            transform: 'translateX(-50%)'
          }}
        >
          {text}
        </span>
      )}
    </span>
  );
}
