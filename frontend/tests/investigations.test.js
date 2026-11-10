import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import {
  askQuestion,
  reassessInvestigation,
  getInvestigationDetail,
  listInvestigations,
  exportInvestigationReport,
  getAnalyticsSummary
} from '../src/api/investigations.js';

describe('Phase 4, 6, 7 & 8 — Investigations, Decisions, Robustness & History APIs', () => {
  test('askQuestion sends question and max_turns', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async (url, options) => {
      assert.equal(url, '/api/ask');
      const body = JSON.parse(options.body);
      assert.equal(body.question, 'What is gross revenue?');
      assert.equal(body.max_turns, 3);
      assert.equal(body.investigation_id, undefined);

      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          success: true,
          investigation_id: 'inv_abc123',
          question: 'What is gross revenue?',
          answer: 'Gross revenue is ₹1,200,000.',
          claims: [{ claim_id: 'c1', claim_text: 'Rev 1.2M', is_supported: true }],
          evidence: [{ evidence_id: 'ev1', evidence_type: 'FACT' }],
          analysis: { recommendation: { action_title: 'Prioritize North' } }
        })
      };
    };

    try {
      const res = await askQuestion('What is gross revenue?');
      assert.equal(res.investigation_id, 'inv_abc123');
      assert.equal(res.success, true);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('askQuestion attaches investigation_id for multi-turn continuations', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async (url, options) => {
      const body = JSON.parse(options.body);
      assert.equal(body.investigation_id, 'inv_thread_999');
      assert.equal(body.question, 'Why did South sales decline?');

      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({ success: true, investigation_id: 'inv_thread_999' })
      };
    };

    try {
      const res = await askQuestion('Why did South sales decline?', 3, false, 'inv_thread_999');
      assert.equal(res.investigation_id, 'inv_thread_999');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('reassessInvestigation calls POST /api/investigations/{id}/reassess with scenario_shift_pct', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async (url, options) => {
      assert.equal(url, '/api/investigations/inv_target_01/reassess');
      assert.equal(options.method, 'POST');
      const body = JSON.parse(options.body);
      assert.equal(body.scenario_shift_pct, 15);

      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          investigation_id: 'inv_target_01',
          robustness: {
            status: 'STABLE',
            explanation: 'Recommendation survived 15% perturbation.'
          }
        })
      };
    };

    try {
      const res = await reassessInvestigation('inv_target_01', 15.0);
      assert.equal(res.robustness.status, 'STABLE');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('listInvestigations passes pagination parameters, search, and filters in query string', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async (url) => {
      assert(url.startsWith('/api/investigations?'));
      const parsed = new URL(`http://localhost${url}`);
      assert.equal(parsed.searchParams.get('limit'), '10');
      assert.equal(parsed.searchParams.get('offset'), '20');
      assert.equal(parsed.searchParams.get('search'), 'revenue');
      assert.equal(parsed.searchParams.get('status'), 'COMPLETED');
      assert.equal(parsed.searchParams.get('robustness_status'), 'STABLE');
      assert.equal(parsed.searchParams.get('owner_id'), 'usr_analyst_01');

      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ([
          { investigation_id: 'inv_1', question: 'Revenue query', status: 'COMPLETED' }
        ])
      };
    };

    try {
      const items = await listInvestigations(10, 20, false, 'revenue', 'COMPLETED', 'STABLE', 'usr_analyst_01');
      assert.equal(items.length, 1);
      assert.equal(items[0].investigation_id, 'inv_1');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('getInvestigationDetail retrieves full audit record by ID', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async (url) => {
      assert.equal(url, '/api/investigations/inv_audit_test');
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          investigation_id: 'inv_audit_test',
          question: 'What is our regional breakdown?',
          status: 'COMPLETED',
          created_at: '2026-11-08T12:00:00Z',
          turns: [],
          evidence_count: 4
        })
      };
    };

    try {
      const detail = await getInvestigationDetail('inv_audit_test');
      assert.equal(detail.investigation_id, 'inv_audit_test');
      assert.equal(detail.status, 'COMPLETED');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('exportInvestigationReport retrieves markdown or json audit report', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async (url, options) => {
      assert.equal(url, '/api/investigations/inv_export_01/export?format=markdown');
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'text/markdown' },
        text: async () => '# VERIDEX AUDIT REPORT FOR inv_export_01'
      };
    };

    try {
      const md = await exportInvestigationReport('inv_export_01', 'markdown');
      assert(md.includes('# VERIDEX AUDIT REPORT'));
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('getAnalyticsSummary retrieves global metrics from backend', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async (url) => {
      assert.equal(url, '/api/investigations/metrics/summary');
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          total_investigations: 42,
          status_counts: { COMPLETED: 38, REQUIRES_REVIEW: 4 },
          robustness_counts: { STABLE: 30, SENSITIVE: 10, INSUFFICIENT_EVIDENCE: 2 }
        })
      };
    };

    try {
      const metrics = await getAnalyticsSummary();
      assert.equal(metrics.total_investigations, 42);
      assert.equal(metrics.robustness_counts.STABLE, 30);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});

