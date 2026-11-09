/**
 * VERIDEX Human-in-the-Loop Review API
 * Connects to:
 * - POST /api/investigations/{id}/review
 */

import { apiRequest } from './core.js';
import { getMockReviewResponse } from '../mocks/mockData.js';

/**
 * Submits a persistent Human-in-the-Loop review decision.
 * Requires REVIEWER or ADMIN role. Self-review is rejected by backend.
 *
 * @param {string} investigationId - Persistent investigation identifier
 * @param {'APPROVED'|'REJECTED'|'FLAGGED'} reviewStatus - Review decision
 * @param {string} reviewerId - Reviewer user identifier
 * @param {string|null} reviewNotes - Optional reviewer comments or rationale
 * @param {boolean} useMock - Fallback mock flag
 * @param {AbortSignal|null} signal - Optional abort signal
 * @returns {Promise<Object>} InvestigationReviewResponse
 */
export async function submitReview(
  investigationId,
  reviewStatus,
  reviewerId,
  reviewNotes = null,
  useMock = false,
  signal = null
) {
  if (!investigationId) {
    throw new Error('Investigation ID is required for review submission.');
  }

  const cleanStatus = (reviewStatus || '').toUpperCase().trim();
  if (!['APPROVED', 'REJECTED', 'FLAGGED'].includes(cleanStatus)) {
    throw new Error(`Invalid review status '${reviewStatus}'. Must be APPROVED, REJECTED, or FLAGGED.`);
  }

  if (useMock) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(getMockReviewResponse(investigationId, cleanStatus, reviewerId, reviewNotes));
      }, 350);
    });
  }

  return await apiRequest(`/api/investigations/${encodeURIComponent(investigationId)}/review`, {
    method: 'POST',
    body: {
      review_status: cleanStatus,
      reviewer_id: reviewerId ? reviewerId.trim() : null,
      review_notes: reviewNotes ? reviewNotes.trim() : null
    },
    signal
  });
}

