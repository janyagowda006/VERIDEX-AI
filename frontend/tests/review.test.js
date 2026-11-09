import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { submitReview } from '../src/api/review.js';
import { VeridexApiError } from '../src/api/core.js';

describe('Phase 5 — Human-in-the-Loop Review API', () => {
  test('submitReview rejects invalid status values', async () => {
    await assert.rejects(
      async () => {
        await submitReview('inv_123', 'INVALID_STATUS', 'usr_rev');
      },
      /Invalid review status/
    );
  });

  test('submitReview rejects missing investigation ID', async () => {
    await assert.rejects(
      async () => {
        await submitReview('', 'APPROVED', 'usr_rev');
      },
      /Investigation ID is required/
    );
  });

  test('submitReview submits valid review decision and receives confirmation', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async (url, options) => {
      assert.equal(url, '/api/investigations/inv_target_01/review');
      assert.equal(options.method, 'POST');
      const body = JSON.parse(options.body);
      assert.equal(body.review_status, 'APPROVED');
      assert.equal(body.reviewer_id, 'usr_reviewer_01');
      assert.equal(body.review_notes, 'Verified regional SQL calculations.');

      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          review_id: 'rev_999',
          investigation_id: 'inv_target_01',
          reviewer_id: 'usr_reviewer_01',
          review_status: 'APPROVED',
          review_notes: 'Verified regional SQL calculations.',
          reviewed_at: '2026-11-08T14:30:00Z'
        })
      };
    };

    try {
      const res = await submitReview(
        'inv_target_01',
        'APPROVED',
        'usr_reviewer_01',
        'Verified regional SQL calculations.'
      );
      assert.equal(res.review_id, 'rev_999');
      assert.equal(res.review_status, 'APPROVED');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('submitReview handles backend self-review rejection error', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async () => ({
      ok: false,
      status: 403,
      headers: { get: () => 'application/json' },
      json: async () => ({
        detail: 'Self-Review Blocked: You cannot review an investigation you initiated.'
      })
    });

    try {
      await assert.rejects(
        async () => {
          await submitReview('inv_target_01', 'APPROVED', 'usr_analyst_01');
        },
        (err) => {
          assert(err instanceof VeridexApiError);
          assert.equal(err.status, 403);
          assert(err.detail.includes('Self-Review Blocked'));
          return true;
        }
      );
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});

