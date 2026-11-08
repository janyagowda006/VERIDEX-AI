import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  login as apiLogin,
  getMe as apiGetMe,
  logout as apiLogout,
  getAuthToken,
  getAuthUser,
  setAuthUser,
  clearAuthToken,
  subscribeAuthChange
} from '../api/client.js';

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [currentUser, setCurrentUserState] = useState(() => getAuthUser());
  const [token, setTokenState] = useState(() => getAuthToken());
  const [isLoading, setIsLoading] = useState(true);
  const [authError, setAuthError] = useState(null);

  // Synchronize state when token or user changes externally
  useEffect(() => {
    const unsubscribe = subscribeAuthChange((user, newToken) => {
      setCurrentUserState(user);
      setTokenState(newToken);
    });
    return unsubscribe;
  }, []);

  // Check and validate active token on mount
  useEffect(() => {
    let isMounted = true;

    async function initializeAuth() {
      const existingToken = getAuthToken();
      if (!existingToken) {
        if (isMounted) {
          setCurrentUserState(null);
          setIsLoading(false);
        }
        return;
      }

      try {
        const user = await apiGetMe(false);
        if (isMounted) {
          if (user) {
            setCurrentUserState(user);
            setAuthUser(user);
          } else {
            clearAuthToken();
            setCurrentUserState(null);
            setTokenState(null);
          }
        }
      } catch (err) {
        if (isMounted) {
          // If 401 or network error on mount
          if (err.status === 401) {
            clearAuthToken();
            setCurrentUserState(null);
            setTokenState(null);
          } else {
            // Keep cached user if offline temporarily
            const cached = getAuthUser();
            if (cached) setCurrentUserState(cached);
          }
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    initializeAuth();

    // Listen for unauthorized 401 events
    const handleUnauthorizedEvent = () => {
      if (isMounted) {
        clearAuthToken();
        setCurrentUserState(null);
        setTokenState(null);
        setAuthError('Your session has expired. Please sign in again.');
      }
    };

    window.addEventListener('veridex:unauthorized', handleUnauthorizedEvent);
    return () => {
      isMounted = false;
      window.removeEventListener('veridex:unauthorized', handleUnauthorizedEvent);
    };
  }, []);

  const login = useCallback(async (email, password, useMock = false) => {
    setAuthError(null);
    setIsLoading(true);
    try {
      const response = await apiLogin(email, password, useMock);
      const user = response?.user || null;
      const newToken = response?.access_token || null;
      setCurrentUserState(user);
      setTokenState(newToken);
      return response;
    } catch (err) {
      const msg = err.detail || err.message || 'Authentication failed. Please verify your credentials.';
      setAuthError(msg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    apiLogout();
    setCurrentUserState(null);
    setTokenState(null);
    setAuthError(null);
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const user = await apiGetMe(false);
      if (user) {
        setCurrentUserState(user);
        setAuthUser(user);
      }
      return user;
    } catch {
      return null;
    }
  }, []);

  const value = {
    currentUser,
    token,
    isAuthenticated: Boolean(token && currentUser),
    isLoading,
    authError,
    setAuthError,
    login,
    logout,
    refreshUser,
    role: currentUser?.role || null
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export { useAuth } from './useAuth.js';
