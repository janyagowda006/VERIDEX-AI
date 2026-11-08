import { test, describe, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

import { login, getMe, logout } from '../src/api/auth.js';
import { getAuthToken, getAuthUser, clearAuthToken, setAuthToken } from '../src/api/session.js';
import { VeridexApiError } from '../src/api/core.js';

describe('Phase 2 — Authentication & Session Management', () => {
  beforeEach(() => {
    clearAuthToken();
  });

  test('login authenticates credentials against backend and persists JWT and profile', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async (url, options) => {
      assert.equal(url, '/api/auth/login');
      assert.equal(options.method, 'POST');
      const body = JSON.parse(options.body);
      assert.equal(body.email, 'analyst@veridex.ai');
      assert.equal(body.password, 'password123');

      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          access_token: 'jwt_sample_token_xyz',
          token_type: 'bearer',
          user: {
            user_id: 'usr_analyst_01',
            email: 'analyst@veridex.ai',
            full_name: 'Alice Analyst',
            role: 'ANALYST',
            is_active: true
          }
        })
      };
    };

    try {
      const res = await login('analyst@veridex.ai', 'password123');
      assert.equal(res.access_token, 'jwt_sample_token_xyz');
      assert.equal(res.user.role, 'ANALYST');

      assert.equal(getAuthToken(), 'jwt_sample_token_xyz');
      const cached = getAuthUser();
      assert.equal(cached.user_id, 'usr_analyst_01');
      assert.equal(cached.email, 'analyst@veridex.ai');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('login throws VeridexApiError on invalid credentials', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async () => ({
      ok: false,
      status: 401,
      headers: { get: () => 'application/json' },
      json: async () => ({ detail: 'Incorrect email or password' })
    });

    try {
      await assert.rejects(
        async () => {
          await login('wrong@veridex.ai', 'badpass');
        },
        (err) => {
          assert(err instanceof VeridexApiError);
          assert.equal(err.status, 401);
          assert.equal(err.detail, 'Incorrect email or password');
          return true;
        }
      );
      assert.equal(getAuthToken(), null);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('getMe returns current user profile when valid token exists', async () => {
    setAuthToken('valid_user_token');

    const originalFetch = globalThis.fetch;
    globalThis.fetch = async (url, options) => {
      assert.equal(url, '/api/auth/me');
      assert.equal(options.headers['Authorization'], 'Bearer valid_user_token');

      return {
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({
          user_id: 'usr_reviewer_01',
          email: 'reviewer@veridex.ai',
          full_name: 'Bob Reviewer',
          role: 'REVIEWER',
          is_active: true
        })
      };
    };

    try {
      const user = await getMe(false);
      assert.equal(user.user_id, 'usr_reviewer_01');
      assert.equal(user.role, 'REVIEWER');
      assert.equal(getAuthUser().full_name, 'Bob Reviewer');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('getMe returns null and clears token if token is expired or unauthorized', async () => {
    setAuthToken('expired_token_123');

    const originalFetch = globalThis.fetch;
    globalThis.fetch = async () => ({
      ok: false,
      status: 401,
      headers: { get: () => 'application/json' },
      json: async () => ({ detail: 'Not authenticated' })
    });

    try {
      const user = await getMe(false);
      assert.equal(user, null);
      assert.equal(getAuthToken(), null);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('logout clears session token and user profile', () => {
    setAuthToken('token_to_purge');
    logout();
    assert.equal(getAuthToken(), null);
    assert.equal(getAuthUser(), null);
  });
});

