import React, { useState } from 'react';
import { PRESET_QUESTIONS } from '../mocks/mockData.js';

export function QuestionInput({
  onSubmit,
  loading,
  useMock,
  onToggleMock,
  activeInvestigationId = null,
  turnCount = 0,
  onStartNew
}) {
  const [question, setQuestion] = useState('What is our gross revenue by region?');

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    if (question.trim() && !loading) {
      onSubmit(question.trim());
    }
  };

  const handleKeyDown = (e) => {
    // Ctrl+Enter or Cmd+Enter submits the investigation query
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSelectPreset = (presetText) => {
    setQuestion(presetText);
    onSubmit(presetText);
  };

  const isFollowUp = Boolean(activeInvestigationId && turnCount > 0);

  return (
    <div className="card question-card" role="region" aria-label="Business Data Investigation Query">
      <div className="card-header question-card-header">
        <div>
          <div className="question-header-top-row">
            <h2>{isFollowUp ? 'Ask Follow-Up Question' : 'Investigate Business Data'}</h2>
            {isFollowUp && (
              <span className="thread-status-badge" title={`Active investigation ID: ${activeInvestigationId}`}>
                <span className="status-dot" aria-hidden="true">●</span>
                Continuing Thread • Turn {turnCount + 1}
              </span>
            )}
          </div>
          <p className="question-desc">
            {isFollowUp
              ? 'Ask follow-up questions to expand context. Context informs reasoning while SQL & Evidence remain strictly current-turn.'
              : 'Formulate natural language questions to inspect verifiable evidence and evaluate decision scenarios.'}
          </p>
        </div>
        <div className="question-header-actions">
          {isFollowUp && onStartNew && (
            <button
              type="button"
              className="btn-new-investigation-small"
              onClick={() => {
                setQuestion('What is our gross revenue by region?');
                onStartNew();
              }}
              disabled={loading}
              title="Start a fresh investigation thread"
            >
              + New Investigation
            </button>
          )}
          <label className="mode-toggle-switch" title={`Switch to ${useMock ? 'Live API' : 'Mock'} mode`}>
            <span className="toggle-label-text">
              {useMock ? 'Mock API' : 'Live API'}
            </span>
            <input
              type="checkbox"
              checked={useMock}
              onChange={(e) => onToggleMock(e.target.checked)}
              aria-label="Toggle between Mock Mode and Live API Mode"
            />
            <span className="switch-slider" aria-hidden="true"></span>
          </label>
        </div>
      </div>


      <form onSubmit={handleSubmit} className="question-form">
        <div className="textarea-wrapper">
          <textarea
            className="question-textarea"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a business question (e.g., What is our gross revenue by region?)"
            rows={3}
            disabled={loading}
            aria-label="Investigation question"
          />
          <span className="textarea-hint" aria-hidden="true">
            Press <kbd>Ctrl</kbd> + <kbd>Enter</kbd> to run
          </span>
        </div>

        <div className="preset-container">
          <span className="preset-label">Suggested Investigations:</span>
          <div className="preset-pills" role="group" aria-label="Suggested investigations">
            {PRESET_QUESTIONS.map((q, idx) => (
              <button
                key={idx}
                type="button"
                className="preset-pill"
                onClick={() => handleSelectPreset(q)}
                disabled={loading}
              >
                {q}
              </button>
            ))}
          </div>
        </div>

        <div className="form-actions">
          <button
            type="submit"
            className="submit-button"
            disabled={loading || !question.trim()}
            aria-label={loading ? 'Investigating Data...' : 'Run Investigation'}
          >
            {loading ? (
              <span className="btn-loading-content">
                <span className="btn-spinner" aria-hidden="true"></span>
                <span>Investigating Data...</span>
              </span>
            ) : (
              <span className="btn-content">
                <span>Run Investigation</span>
                <span className="btn-arrow" aria-hidden="true">→</span>
              </span>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
