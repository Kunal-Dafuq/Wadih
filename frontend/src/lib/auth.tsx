import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api, setToken, setUnauthenticatedHandler } from './api';
import type { CurrentUser } from './types';

// Session-scoped storage: the token is dropped when the tab closes.
const STORAGE_KEY = 'wadih.session';

interface Session {
  token: string;
  user: CurrentUser;
}

interface AuthState {
  user: CurrentUser | null;
  status: 'restoring' | 'signed-in' | 'signed-out';
  login: (email: string, password: string) => Promise<CurrentUser>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

function readSession(): Session | null {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

function writeSession(s: Session | null) {
  try {
    if (s) window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(s));
    else window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* storage unavailable: session lives in memory only */
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [status, setStatus] = useState<AuthState['status']>('restoring');

  const clear = useCallback(() => {
    setToken(null);
    writeSession(null);
    setUser(null);
    setStatus('signed-out');
  }, []);

  useEffect(() => {
    setUnauthenticatedHandler(clear);
    const saved = readSession();
    if (!saved) {
      setStatus('signed-out');
      return;
    }
    setToken(saved.token);
    // Re-validate the stored token with the server instead of trusting it.
    api
      .me()
      .then((me) => {
        writeSession({ token: saved.token, user: me });
        setUser(me);
        setStatus('signed-in');
      })
      .catch(clear);
    return () => setUnauthenticatedHandler(null);
  }, [clear]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.login(email, password);
    setToken(res.access_token);
    writeSession({ token: res.access_token, user: res.user });
    setUser(res.user);
    setStatus('signed-in');
    return res.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      /* token may already be invalid; clear locally regardless */
    }
    clear();
  }, [clear]);

  const value = useMemo(() => ({ user, status, login, logout }), [user, status, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
