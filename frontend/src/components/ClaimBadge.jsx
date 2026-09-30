import React from 'react';

/**
 * Renders categorized evidence badge: FACT, DERIVED_FACT, or INFERENCE.
 */
export function ClaimBadge({ type }) {
  const normalized = (type || 'FACT').toUpperCase();

  let badgeClass = 'badge-fact';
  let label = 'FACT';

  if (normalized === 'DERIVED_FACT') {
    badgeClass = 'badge-derived';
    label = 'DERIVED FACT';
  } else if (normalized === 'INFERENCE') {
    badgeClass = 'badge-inference';
    label = 'INFERENCE';
  }

  return (
    <span className={`evidence-badge ${badgeClass}`}>
      {label}
    </span>
  );
}
