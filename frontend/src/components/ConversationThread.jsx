import React from 'react';

/**
 * ConversationThread component renders the ordered timeline of investigation turns
 * for an active business investigation thread.
 *
 * @param {Array<Object>} turns - Array of InvestigationTurn summary/payload objects.
 * @param {number} activeTurnNumber - Currently selected/rendered turn number.
 * @param {Function} onSelectTurn - Callback when user clicks a turn to view details.
 * @param {string} activeInvestigationId - ID of active investigation.
 * @param {Function} onNewInvestigation - Callback to reset & start a fresh investigation.
 * @param {boolean} loading - Loading state for in-flight requests.
 */
export function ConversationThread({
  turns = [],
  activeTurnNumber = 1,
  onSelectTurn,
  activeInvestigationId = null,
  onNewInvestigation,
  loading = false
}) {
  if (!turns || turns.length === 0) {
    return null;
  }

  return (
    <div className="card conversation-thread-card" role="region" aria-label="Conversation Thread Timeline">
      <div className="card-header conversation-thread-header">
        <div className="thread-title-group">
          <span className="thread-icon" aria-hidden="true">💬</span>
          <div>
            <h2>Investigation Thread Timeline</h2>
            <p className="thread-subtitle">
              Persistent multi-turn business conversation & history trace
              {activeInvestigationId && (
                <span className="thread-id-pill">ID: {activeInvestigationId}</span>
              )}
            </p>
          </div>
        </div>
        {onNewInvestigation && (
          <button
            type="button"
            className="btn-new-investigation"
            onClick={onNewInvestigation}
            disabled={loading}
            aria-label="Start a completely new investigation"
          >
            <span className="btn-icon" aria-hidden="true">+</span>
            New Investigation
          </button>
        )}
      </div>

      <div className="thread-timeline">
        {turns.map((turn) => {
          const isTurnActive = turn.turn_number === activeTurnNumber;
          const turnTimeStr = turn.created_at
            ? new Date(turn.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
            : null;

          return (
            <div
              key={turn.turn_id || `turn_${turn.turn_number}`}
              className={`thread-turn-item ${isTurnActive ? 'active-turn' : ''}`}
            >
              <div className="turn-marker-column">
                <div className="turn-badge" aria-hidden="true">
                  T{turn.turn_number}
                </div>
                <div className="turn-connector-line" aria-hidden="true"></div>
              </div>

              <div className="turn-content-card">
                <div className="turn-card-header">
                  <div className="turn-meta-left">
                    <span className="turn-number-label">Turn {turn.turn_number}</span>
                    {turnTimeStr && <span className="turn-timestamp">{turnTimeStr}</span>}
                  </div>
                  <div className="turn-meta-right">
                    {turn.evidence_count !== undefined && (
                      <span className="turn-stat-badge">
                        🔍 {turn.evidence_count} {turn.evidence_count === 1 ? 'evidence' : 'evidence items'}
                      </span>
                    )}
                    {turn.execution_time_ms && (
                      <span className="turn-stat-badge">
                        ⚡ {Math.round(turn.execution_time_ms)}ms
                      </span>
                    )}
                  </div>
                </div>

                <div className="turn-user-query">
                  <span className="role-label user-role">User</span>
                  <p className="query-text">{turn.question}</p>
                </div>

                <div className="turn-assistant-response">
                  <span className="role-label assistant-role">Assistant Finding</span>
                  <p className="answer-summary">{turn.answer}</p>
                </div>

                {onSelectTurn && (
                  <div className="turn-card-actions">
                    <button
                      type="button"
                      className={`btn-inspect-turn ${isTurnActive ? 'btn-inspect-active' : ''}`}
                      onClick={() => onSelectTurn(turn.turn_number)}
                      aria-label={`Inspect detailed result for Turn ${turn.turn_number}`}
                      aria-current={isTurnActive ? 'true' : 'false'}
                    >
                      {isTurnActive ? '✓ Viewing Detailed Analysis' : `Inspect Turn ${turn.turn_number} Analysis →`}
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
