import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, getToken, setToken } from "../lib/api";
import type { User } from "../types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  hasRole: (...roles: string[]) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    api<User>("/api/v1/auth/me")
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const form = new FormData();
    form.append("username", email);
    form.append("password", password);
    const res = await api<{ access_token: string; user: User }>("/api/v1/auth/login", {
      method: "POST",
      formData: form,
      auth: false,
    });
    setToken(res.access_token);
    setUser(res.user);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  const hasRole = useCallback(
    (...roles: string[]) => (user?.roles ?? []).some((r) => roles.includes(r) || r === "admin"),
    [user],
  );

  const value = useMemo(() => ({ user, loading, login, logout, hasRole }), [user, loading, login, logout, hasRole]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth fuera de AuthProvider");
  return ctx;
}
