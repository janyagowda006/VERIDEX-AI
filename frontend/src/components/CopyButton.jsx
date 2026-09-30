import React, { useState } from 'react';

/**
 * Reusable accessible Copy-to-Clipboard button.
 * Uses browser Clipboard API with fallback, provides temporary visual feedback.
 */
export function CopyButton({ text, label = 'Copy', copiedLabel = 'Copied!', className = '' }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e) => {
    e.stopPropagation();
    if (!text) return;

    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    } catch (err) {
      console.warn('Clipboard copy failed:', err);
    }
  };

  return (
    <button
      type="button"
      className={`copy-btn ${copied ? 'copied' : ''} ${className}`}
      onClick={handleCopy}
      title={copied ? copiedLabel : label}
      aria-label={copied ? copiedLabel : label}
    >
      <span className="copy-btn-content">
        <span className="copy-icon" aria-hidden="true">{copied ? '✓' : '📋'}</span>
        <span className="copy-label-text">{copied ? copiedLabel : label}</span>
      </span>
    </button>
  );
}
