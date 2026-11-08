import { test, describe, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

import { getApiBaseUrl, buildApiUrl } from '../src/api/config.js';
import {
  setAuthToken,
  getAuthToken,
  setAuthUser,
  getAuthUser,
  clearAuthToken,
  isAuthenticated
} from '../src/api/session.js';
import {
  apiRequest,
  getAuthHeaders,
  VeridexApiError,
  VeridexNetworkError
} from '../src/api/core.js';

describe('Phase 1 — Centralized API Client & Config', () => {
  beforeEach(() => {
    clearAuthToken();
  });

  test('buildApiUrl handles relative endpoints without base URL in dev', () => {
    const url = buildApiUrl('/api/ask');
    assert.equal(url, '/api/ask');
  });

  test('buildApiUrl normalizes endpoints without leading slash', () => {
    const url = buildApiUrl('health');
    assert.equal(url, '/health');
  });

  test('Session module manages token lifecycle and storage', () => {
    assert.equal(isAuthenticated(), false);
    assert.equal(getAuthToken(), null);

    setAuthToken('test_jwt_access_token_123');
    assert.equal(getAuthToken(), 'test_jwt_access_token_123');
    assert.equal(isAuthenticated(), true);

    setAuthUser({ user_id: 'usr_analyst_01', role: 'ANALYST', full_name: 'Alice Analyst' });
    const cachedUser = getAuthUser();
    assert.equal(cachedUser.user_id, 'usr_analyst_01');
    assert.equal(cachedUser.role, 'ANALYST');

    clearAuthToken();
    assert.equal(getAuthToken(), null);
    assert.equal(getAuthUser(), null);
    assert.equal(isAuthenticated(), false);
  });

  test('getAuthHeaders automatically attaches Bearer token when authenticated', () => {
    const unauthHeaders = getAuthHeaders({ 'Custom-Header': 'veridex' });
    assert.equal(unauthHeaders['Authorization'], undefined);
    assert.equal(unauthHeaders['Custom-Header'], 'veridex');

    setAuthToken('mock_secret_token_abc');
    const authHeaders = getAuthHeaders({ 'Custom-Header': 'veridex' });
    assert.equal(authHeaders['Authorization'], 'Bearer mock_secret_token_abc');
    assert.equal(authHeaders['Custom-Header'], 'veridex');
  });

  test('apiRequest dispatches JSON requests and parses JSON responses', async () => {
    // Mock global fetch
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async (url, options) => {
      assert.equal(url, '/api/ask');
      assert.equal(options.method, 'POST');
      assert.equal(options.headers['Content-Type'], 'application/json');
      const body = JSON.parse(options.body);
      assert.equal(body.question, 'What is our gross revenue?');

      return {
        ok: true,
        status: 200,
        headers: {
          get: (name) => (name.toLowerCase() === 'content-type' ? 'application/json' : null)
        },
        json: async () => ({
          success: true,
          answer: 'Gross revenue is ₹1,200,000'
        })
      };
    };

    try {
      const res = await apiRequest('/api/ask', {
        method: 'POST',
        body: { question: 'What is our gross revenue?' }
      });
      assert.equal(res.success, true);
      assert.equal(res.answer, 'Gross revenue is ₹1,200,000');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('apiRequest does not set manual Content-Type header on FormData uploads', async () => {
    const originalFetch = globalThis.fetch;
    let sentHeaders = null;

    globalThis.fetch = async (url, options) => {
      sentHeaders = options.headers;
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({ success: true })
      };
    };

    try {
      const formData = new FormData();
      formData.append('key', 'value');

      await apiRequest('/api/upload', {
        method: 'POST',
        body: formData
      });

      assert.equal(sentHeaders['Content-Type'], undefined, 'Content-Type must not be manually set for FormData');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('apiRequest handles non-2xx responses and extracts backend detail', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async () => ({
      ok: false,
      status: 400,
      headers: { get: () => 'application/json' },
      json: async () => ({ detail: 'Invalid investigation parameters.' })
    });

    try {
      await assert.rejects(
        async () => {
          await apiRequest('/api/ask', { method: 'POST', body: {} });
        },
        (err) => {
          assert(err instanceof VeridexApiError);
          assert.equal(err.status, 400);
          assert.equal(err.detail, 'Invalid investigation parameters.');
          return true;
        }
      );
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('apiRequest handles network failure gracefully with VeridexNetworkError', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async () => {
      throw new TypeError('Failed to fetch');
    };

    try {
      await assert.rejects(
        async () => {
          await apiRequest('/health');
        },
        (err) => {
          assert(err instanceof VeridexNetworkError);
          assert(err.message.includes('Unable to connect to VERIDEX backend'));
          return true;
        }
      );
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('apiRequest supports AbortSignal cancellation', async () => {
    const originalFetch = globalThis.fetch;
    const controller = new AbortController();

    globalThis.fetch = async (url, options) => {
      if (options.signal?.aborted) {
        const err = new Error('The user aborted a request.');
        err.name = 'AbortError';
        throw err;
      }
      return { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => ({}) };
    };

    try {
      controller.abort();
      await assert.rejects(
        async () => {
          await apiRequest('/api/ask', { signal: controller.signal });
        },
        (err) => {
          assert.equal(err.name, 'AbortError');
          return true;
        }
      );
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});

