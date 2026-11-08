/**
 * VERIDEX Authentication API
 * Connects to:
 * - POST /api/auth/login
 * - GET /api/auth/me
 */

import { apiRequest } from './core.js';
import { setAuthToken, setAuthUser, clearAuthToken, getAuthToken } from './session.js';
import { getMockLoginResponse, getMockMeResponse } from '../mocks/mockData.js';

/**
 * Authenticates user credentials with real backend.
 *
 * @param {string} email
 * @param {string} password
 * @param {boolean} useMock - Fallback flag
 * @returns {Promise<{ access_token: string, token_type: string, user: Object }>}
 */
export async function login(email, password, useMock = false) {
  const cleanEmail = (email || '').trim();

  if (useMock) {
    return new Promise((resolve) => {
      setTimeout(() => {
        const mockRes = getMockLoginResponse(cleanEmail);
        setAuthToken(mockRes.access_token);
        setAuthUser(mockRes.user);
        resolve(mockRes);
      }, 250);
    });
  }

  const result = await apiRequest('/api/auth/login', {
    method: 'POST',
    body: {
      email: cleanEmail,
      password: password
    },
    skipAuth: true
  });

  if (result?.access_token) {
    setAuthToken(result.access_token);
  }
  if (result?.user) {
    setAuthUser(result.user);
  }

  return result;
}

/**
 * Retrieves the currently authenticated user's profile from the backend.
 *
 * @param {boolean} useMock - Fallback flag
 * @param {string} devRole - Optional dev role override for mock testing
 * @param {AbortSignal} signal - Optional abort signal
 * @returns {Promise<Object|null>}
 */
export async function getMe(useMock = false, devRole = "ANALYST", signal = null) {
  if (useMock) {
    return new Promise((resolve) => {
      setTimeout(() => {
        const mockUser = getMockMeResponse(devRole);
        setAuthUser(mockUser);
        resolve(mockUser);
      }, 150);
    });
  }

  const token = getAuthToken();
  if (!token) {
    return null;
  }

  try {
    const user = await apiRequest('/api/auth/me', {
      method: 'GET',
      signal
    });
    if (user) {
      setAuthUser(user);
    }
    return user;
  } catch (err) {
    if (err.status === 401) {
      clearAuthToken();
      return null;
    }
    throw err;
  }
}

/**
 * Logs out the active user and purges all credentials.
 */
export function logout() {
  clearAuthToken();
}

