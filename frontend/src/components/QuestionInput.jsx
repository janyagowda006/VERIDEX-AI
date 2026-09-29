import React, { useState } from 'react';
import { PRESET_QUESTIONS } from '../mocks/mockData.js';

export function QuestionInput({ onSubmit, loading, useMock, onToggleMock }) {
  const [question, setQuestion] = useState('What is our gross revenue by region?');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (question.trim() && !loading) {
      onSubmit(question.trim());
    }
  };

  const handleSelectPreset = (presetText) => {
    setQuestion(presetText);
    onSubmit(presetText);
  };

  return (
    <div className="card question-card">
      <div className="card-header">
        <h2>Investigate Business Data</h2>
        <label className="toggle-label">
          <input
            type="checkbox"
            checked={useMock}
            onChange={(e) => onToggleMock(e.target.checked)}
          />
          <span className="toggle-text">
            {useMock ? 'Mock Mode' : 'Live API Mode'}
          </span>
        </label>
      </div>

      <form onSubmit={handleSubmit} className="question-form">
        <textarea
          className="question-textarea"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a business question (e.g., What is our gross revenue by region?)"
          rows={3}
          disabled={loading}
        />

        <div className="preset-container">
          <span className="preset-label">Suggested:</span>
          <div className="preset-pills">
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
          <button type="submit" className="submit-button" disabled={loading || !question.trim()}>
            {loading ? 'Investigating Data...' : 'Run Investigation'}
          </button>
        </div>
      </form>
    </div>
  );
}
