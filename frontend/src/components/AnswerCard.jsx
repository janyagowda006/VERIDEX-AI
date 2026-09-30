import React from 'react';
import { ClaimBadge } from './ClaimBadge.jsx';

export function AnswerCard({ answer, claims = [], selectedEvidenceId, onSelectEvidence }) {
  if (!answer) return null;

  return (
    <div className="card answer-card">
      <h2>Synthesized Finding</h2>
      <p className="answer-text">{answer}</p>

      {claims.length > 0 && (
        <div className="claims-section">
          <h3>Categorized Business Claims ({claims.length})</h3>
          <ul className="claims-list">
            {claims.map((claim, idx) => {
              const isClaimActive = claim.evidence_ids && selectedEvidenceId && claim.evidence_ids.includes(selectedEvidenceId);
              return (
                <li key={claim.claim_id || idx} className={`claim-item ${isClaimActive ? 'claim-item-active' : ''}`}>
                  <div className="claim-header">
                    <ClaimBadge type={claim.evidence_type} />
                    <span className="claim-id">{claim.claim_id}</span>
                  </div>
                  <p className="claim-text">{claim.claim_text}</p>
                  {claim.evidence_ids && claim.evidence_ids.length > 0 && (
                    <div className="claim-evidence-ids">
                      <span className="ev-label">Supporting Evidence:</span>
                      <div className="ev-tags-group">
                        {claim.evidence_ids.map((id) => (
                          <button
                            key={id}
                            type="button"
                            className={`ev-tag-btn ${selectedEvidenceId === id ? 'active' : ''}`}
                            onClick={() => onSelectEvidence && onSelectEvidence(id)}
                            title={`Inspect evidence item ${id}`}
                            aria-label={`Jump to evidence item ${id}`}
                          >
                            {id}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
