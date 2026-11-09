/**
 * VERIDEX Authentication & Session State Module
 *
 * TOKEN STORAGE SECURITY TRADE-OFF ASSESSMENT:
 * ----------------------------------------------------
 * VERIDEX is deployed as a decoupled static site (Render Static Site) communicating with a
 * distinct FastAPI backend service. Storing the JWT access token in localStorage enables:
 *  1. Zero server affinity / cross-origin REST communication with standard Authorization: Bearer headers.
 *  2. Resilience across page reloads in single-page application environments.
 *
 * Trade-off & Mitigations:
 *  - Risk: localStorage is accessible to JavaScript and vulnerable to XSS attacks if arbitrary script execution occurs.
 *  - Mitigation 1: Tokens are short-lived JWTs (typically 15-60 min) signed with HS256 by the backend.
 *  - Mitigation 2: Strict content rendering avoids dangerouslySetInnerHTML throughout the application.
 *  - Mitigation 3: Sensitive credentials (passwords) are NEVER persisted; only the opaque token and public profile are cached.
 *  - Fallback: In sandbox or restricted environments where localStorage throws DOMException, an in-memory variable is maintained.
 */

const TOKEN_KEY = 'veridex_auth_token';
const USER_KEY = 'veridex_auth_user';

let memoryToken = null;
let memoryUser = null;

// Auth state listeners (e.g., to notify React contexts on 401 expiration or logout)
const authListeners = new Set();

export function subscribeAuthChange(callback) {
  authListeners.add(callback);
  return () => authListeners.delete(callback);
}

function notifyAuthChange(user, token) {
  authListeners.forEach((cb) => {
    try {
      cb(user, token);
    } catch (e) {
      console.error('Error in auth listener:', e);
    }
  });
}

/**
 * Stores JWT authentication token.
 * @param {string|null} token
 */
export function setAuthToken(token) {
  memoryToken = token || null;
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    // Restricted environment fallback
  }
}

/**
 * Retrieves the currently active JWT access token.
 * @returns {string|null}
 */
export function getAuthToken() {
  if (memoryToken) {
    return memoryToken;
  }
  try {
    const saved = localStorage.getItem(TOKEN_KEY);
    if (saved) {
      memoryToken = saved;
      return saved;
    }
  } catch {
    // Restricted environment fallback
  }
  return null;
}

/**
 * Stores cached user profile.
 * @param {Object|null} user
 */
export function setAuthUser(user) {
  memoryUser = user || null;
  try {
    if (user) {
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(USER_KEY);
    }
  } catch {
    // Restricted environment fallback
  }
  notifyAuthChange(memoryUser, getAuthToken());
}

/**
 * Retrieves cached user profile.
 * @returns {Object|null}
 */
export function getAuthUser() {
  if (memoryUser) {
    return memoryUser;
  }
  try {
    const raw = localStorage.getItem(USER_KEY);
    if (raw) {
      memoryUser = JSON.parse(raw);
      return memoryUser;
    }
  } catch {
    // Fallback
  }
  return null;
}

/**
 * Clears current session token and cached user profile.
 */
export function clearAuthToken() {
  setAuthToken(null);
  setAuthUser(null);
}

/**
 * Checks whether user currently holds an access token.
 * @returns {boolean}
 */
export function isAuthenticated() {
  return Boolean(getAuthToken());
}

/**
 * Emits an unauthorized (401 / expired token) notification.
 */
export function handleUnauthorized() {
  clearAuthToken();
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('veridex:unauthorized', { detail: { timestamp: Date.now() } }));
  }
}

