/**
 * Who is signed in. `status` separates "not signed in" from "could not reach the server", so a
 * backend outage shows a retry rather than kicking the user to the login page.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import * as authApi from '../api/auth';
import { setUnauthorizedHandler } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState('loading');
  const [bootError, setBootError] = useState(null);

  const applyUser = useCallback((next) => {
    setUser(next);
    setStatus(next ? 'authed' : 'anon');
  }, []);

  const loadMe = useCallback(async () => {
    setStatus('loading');
    setBootError(null);
    try {
      const { user: me } = await authApi.fetchMe();
      applyUser(me);
    } catch (error) {
      if (error.status === 401) {
        applyUser(null);
      } else {
        setBootError(error);
        setStatus('error');
      }
    }
  }, [applyUser]);

  useEffect(() => {
    loadMe();
    // RequireAuth sees status "anon" and routes to login, keeping the current page as the way back.
    setUnauthorizedHandler(() => applyUser(null));
    return () => setUnauthorizedHandler(null);
  }, [loadMe, applyUser]);

  const value = useMemo(
    () => ({
      user,
      status,
      bootError,
      retry: loadMe,
      setUser: applyUser,
      async login(credentials) {
        const { user: next } = await authApi.login(credentials);
        applyUser(next);
        return next;
      },
      async register(details) {
        const { user: next } = await authApi.register(details);
        applyUser(next);
        return next;
      },
      async logout() {
        try {
          await authApi.logout();
        } finally {
          // Clear locally even if the call failed. The user asked to leave.
          applyUser(null);
        }
      },
    }),
    [user, status, bootError, loadMe, applyUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
