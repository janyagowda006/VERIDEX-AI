import React from 'react';
import { DecisionCard } from '../DecisionCard.jsx';
import { HumanReviewPanel } from '../HumanReviewPanel.jsx';
import { CriteriaThresholdView } from '../visualization/CriteriaThresholdView.jsx';

export function DecisionsView({
  data,
  selectedEvidenceId,
  onSelectEvidence,
  useMock,
  currentUser
}) {
  const analysis = data?.analysis;
  const criteria = analysis?.criteria_evaluated || [];
  const invId = data?.metadata?.investigation_id || "inv_mock_123456";

  return (
    <div className="view-container decisions-view">
      <div className="view-header">
        <div>
          <h2>Decision Intelligence & Human Governance</h2>
          <p className="view-subtitle">
            Actionable candidate rankings, deterministic criteria threshold checks, and analyst review governance.
          </p>
        </div>
      </div>

      {data ? (
        <div className="decisions-views-flow" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Actionable Decision Card */}
          {analysis && (
            <DecisionCard
              analysis={analysis}
              selectedEvidenceId={selectedEvidenceId}
              onSelectEvidence={onSelectEvidence}
            />
          )}

          {/* Criteria Threshold Compliance */}
          {criteria.length > 0 && (
            <CriteriaThresholdView criteria={criteria} />
          )}

          {/* Human Review Approval Panel */}
          <HumanReviewPanel
            key={invId}
            investigationId={invId}
            investigationStatus={data?.status || 'COMPLETED'}
            latestReview={data?.latest_review || null}
            reviewCount={data?.review_count || 0}
            useMock={useMock}
            currentUser={currentUser}
            ownerId={data?.owner_id || "usr_analyst_01"}
          />
        </div>
      ) : (
        <div className="card empty-card" role="status">
          <p className="no-data-text">No active investigation loaded. Run an investigation to view decision intelligence.</p>
        </div>
      )}
    </div>
  );
}
