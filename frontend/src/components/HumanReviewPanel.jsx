import React, { useState } from 'react';
import { submitReview } from '../api/client.js';

export function HumanReviewPanel({
  investigationId,
  investigationStatus = 'COMPLETED',
  latestReview = null,
  reviewCount = 0,
  useMock = false
}) {
  const [reviewStatus, setReviewStatus] = useState('');
  const [reviewerId, setReviewerId] = useState('');
  const [reviewNotes, setReviewNotes] = useState('');

  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewError, setReviewError] = useState(null);
  const [reviewSuccess, setReviewSuccess] = useState(null);

  const [currentLatestReview, setCurrentLatestReview] = useState(latestReview);
  const [currentReviewCount, setCurrentReviewCount] = useState(reviewCount);

  const isCompletedOrReviewable = investigationStatus !== 'IN_PROGRESS';
  const isRequiresReview = investigationStatus === 'REQUIRES_REVIEW';

  const handleReviewSubmit = async (e) => {
    e.preventDefault();
    setReviewError(null);
    setReviewSuccess(null);

    // Form validation
    if (!reviewStatus) {
      setReviewError("Please select a review decision (APPROVED, REJECTED, or FLAGGED).");
      return;
    }

    const trimmedReviewerId = reviewerId.trim();
    if (!trimmedReviewerId) {
      setReviewError("Reviewer ID is required and cannot be empty or whitespace only.");
      return;
    }

    if (trimmedReviewerId.length > 64) {
      setReviewError("Reviewer ID cannot exceed 64 characters.");
      return;
    }

    if (reviewNotes.length > 2000) {
      setReviewError("Review notes cannot exceed 2000 characters.");
      return;
    }

    const targetInvId = investigationId || "inv_mock_123456";
    setReviewLoading(true);

    try {
      const result = await submitReview(
        targetInvId,
        reviewStatus,
        trimmedReviewerId,
        reviewNotes.trim() || null,
        useMock
      );

      setCurrentLatestReview(result);
      setCurrentReviewCount((prev) => prev + 1);
      setReviewSuccess(`Review decision successfully recorded as '${result.review_status}'.`);
      setReviewStatus('');
      setReviewNotes('');
    } catch (err) {
      setReviewError(err.message || "Unable to submit review decision. Please try again.");
    } finally {
      setReviewLoading(false);
    }
  };

  return (
    <div className={`card human-review-card ${isRequiresReview ? 'card-requires-review' : ''}`}>
      <div className="card-header">
        <div className="review-title-group">
          <span className="review-header-icon" aria-hidden="true">🛡️</span>
          <div>
            <h2>Human-in-the-Loop Audit & Review</h2>
            <p className="review-subtitle">
              Application-level analyst verification layer. Original AI evidence remains 100% immutable.
            </p>
          </div>
        </div>
        {isRequiresReview && (
          <span className="requires-review-badge animate-pulse">
            REQUIRES HUMAN REVIEW
          </span>
        )}
      </div>

      {isRequiresReview && (
        <div className="review-alert-banner">
          <span className="alert-icon" aria-hidden="true">⚠️</span>
          <div>
            <strong>Analyst Verification Recommended:</strong> Metric sensitivity test indicated perturbed candidate margin &lt;5.0%. Review evidence and record your decision below.
          </div>
        </div>
      )}

      {/* Submission Form */}
      {isCompletedOrReviewable ? (
        <form onSubmit={handleReviewSubmit} className="review-form" noValidate>
          {/* Decision Selection Buttons */}
          <div className="form-group">
            <label className="field-label">
              Review Decision <span className="required-star">*</span>
            </label>
            <div className="review-decision-buttons" role="radiogroup" aria-label="Review decision choices">
              <button
                type="button"
                className={`decision-btn btn-approved ${reviewStatus === 'APPROVED' ? 'active' : ''}`}
                onClick={() => setReviewStatus('APPROVED')}
                disabled={reviewLoading}
              >
                <span className="btn-icon" aria-hidden="true">✓</span>
                APPROVED
              </button>
              <button
                type="button"
                className={`decision-btn btn-rejected ${reviewStatus === 'REJECTED' ? 'active' : ''}`}
                onClick={() => setReviewStatus('REJECTED')}
                disabled={reviewLoading}
              >
                <span className="btn-icon" aria-hidden="true">✕</span>
                REJECTED
              </button>
              <button
                type="button"
                className={`decision-btn btn-flagged ${reviewStatus === 'FLAGGED' ? 'active' : ''}`}
                onClick={() => setReviewStatus('FLAGGED')}
                disabled={reviewLoading}
              >
                <span className="btn-icon" aria-hidden="true">⚑</span>
                FLAGGED
              </button>
            </div>
          </div>

          {/* Reviewer ID Input */}
          <div className="form-group">
            <label htmlFor="reviewerIdInput" className="field-label">
              Reviewer ID <span className="required-star">*</span>
            </label>
            <input
              id="reviewerIdInput"
              type="text"
              className="review-text-input"
              value={reviewerId}
              onChange={(e) => setReviewerId(e.target.value)}
              placeholder="e.g. analyst_gagan"
              maxLength={64}
              disabled={reviewLoading}
              required
            />
            <span className="field-helper-text">
              Recorded as audit metadata; authentication is handled outside this workflow.
            </span>
          </div>

          {/* Review Notes Textarea */}
          <div className="form-group">
            <div className="label-with-counter">
              <label htmlFor="reviewNotesInput" className="field-label">
                Review Rationale / Notes <span className="optional-tag">(Optional)</span>
              </label>
              <span className={`char-counter ${reviewNotes.length > 1900 ? 'near-limit' : ''}`}>
                {reviewNotes.length} / 2000
              </span>
            </div>
            <textarea
              id="reviewNotesInput"
              className="review-textarea"
              rows={3}
              value={reviewNotes}
              onChange={(e) => setReviewNotes(e.target.value.slice(0, 2000))}
              placeholder="Add evidence verification details, domain context, or rationale..."
              disabled={reviewLoading}
            />
          </div>

          {/* User Feedback Messages */}
          {reviewError && (
            <div className="review-message message-error" role="alert">
              <span className="msg-icon" aria-hidden="true">⚠️</span>
              <span>{reviewError}</span>
            </div>
          )}

          {reviewSuccess && (
            <div className="review-message message-success" role="status">
              <span className="msg-icon" aria-hidden="true">✓</span>
              <span>{reviewSuccess}</span>
            </div>
          )}

          {/* Form Actions */}
          <div className="review-form-actions">
            <button
              type="submit"
              className="submit-review-btn"
              disabled={reviewLoading || !reviewStatus || !reviewerId.trim()}
            >
              {reviewLoading ? (
                <>
                  <span className="btn-spinner" aria-hidden="true"></span>
                  Submitting Review...
                </>
              ) : (
                'Submit Review Decision'
              )}
            </button>
          </div>
        </form>
      ) : (
        <div className="review-in-progress-notice" role="status">
          <span className="info-icon" aria-hidden="true">ℹ️</span>
          <span>Human review becomes available after the investigation completes.</span>
        </div>
      )}

      {/* Persistent Audit History Display */}
      <div className="review-audit-history">
        <div className="history-header">
          <h4>Human Audit History</h4>
          <span className="review-count-pill">
            Review Count: {currentReviewCount}
          </span>
        </div>

        {currentLatestReview ? (
          <div className="latest-review-card">
            <div className="audit-card-top">
              <div className="audit-status-group">
                <span className="audit-label">Latest Review:</span>
                <span className={`audit-badge badge-${currentLatestReview.review_status.toLowerCase()}`}>
                  {currentLatestReview.review_status}
                </span>
              </div>
              <span className="audit-timestamp">
                {new Date(currentLatestReview.reviewed_at).toLocaleString()}
              </span>
            </div>

            <div className="audit-meta-row">
              <span className="meta-label">Reviewer ID:</span>
              <span className="meta-val">{currentLatestReview.reviewer_id}</span>
            </div>

            {currentLatestReview.review_notes && (
              <div className="audit-notes-box">
                <span className="meta-label">Notes / Rationale:</span>
                <p className="notes-text">{currentLatestReview.review_notes}</p>
              </div>
            )}
          </div>
        ) : (
          <p className="no-reviews-text">No human review decision recorded yet.</p>
        )}
      </div>
    </div>
  );
}
