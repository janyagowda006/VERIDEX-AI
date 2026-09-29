import React from 'react';
import { ClaimBadge } from './ClaimBadge.jsx';

export function AnswerCard({ answer, claims = [] }) {
  if (!answer) return null;

  return (
    <div className="card answer-card">
      <h2>Synthesized Finding</h2>
      <p className="answer-text">{answer}</p>

      {claims.length > 0 && (
        <div className="claims-section">
          <h3>Categorized Business Claims ({claims.length})</h3>
          <ul className="claims-list">
            {claims.map((claim, idx) => (
              <li key={claim.claim_id || idx} className="claim-item">
                <div className="claim-header">
                  <ClaimBadge type={claim.evidence_type} />
                  <span className="claim-id">{claim.claim_id}</span>
                </div>
                <p className="claim-text">{claim.claim_text}</p>
                {claim.evidence_ids && claim.evidence_ids.length > 0 && (
                  <div className="claim-evidence-ids">
                    Evidence IDs: {claim.evidence_ids.map(id => (
                      <span key={id} className="ev-tag">{id}</span>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
