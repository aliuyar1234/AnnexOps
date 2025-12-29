"use client";

import { apiRequest, ApiError } from "@/lib/http";
import type { TokenResponse, UserResponse } from "@/lib/types";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

type AuthState = {
  isLoading: boolean;
  accessToken: string | null;
  user: UserResponse | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isLoading, setIsLoading] = useState(true);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserResponse | null>(null);

  const loadMe = useCallback(
    async (token: string) => {
      const me = await apiRequest<UserResponse>("/api/me", {}, { accessToken: token });
      setUser(me);
    },
    [setUser],
  );

  const refresh = useCallback(async () => {
    const token = await apiRequest<TokenResponse>("/api/auth/refresh", { method: "POST" });
    setAccessToken(token.access_token);
    await loadMe(token.access_token);
  }, [loadMe]);

  const login = useCallback(
    async (email: string, password: string) => {
      const token = await apiRequest<TokenResponse>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setAccessToken(token.access_token);
      await loadMe(token.access_token);
    },
    [loadMe],
  );

  const logout = useCallback(async () => {
    try {
      if (accessToken) {
        await apiRequest("/api/auth/logout", { method: "POST" }, { accessToken });
      }
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  }, [accessToken]);

  useEffect(() => {
    let isMounted = true;
    (async () => {
      try {
        await refresh();
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          // Not logged in yet
          if (isMounted) {
            setAccessToken(null);
            setUser(null);
          }
          return;
        }
        if (isMounted) {
          setAccessToken(null);
          setUser(null);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    })();
    return () => {
      isMounted = false;
    };
  }, [refresh]);

  const value = useMemo<AuthState>(
    () => ({
      isLoading,
      accessToken,
      user,
      login,
      logout,
      refresh,
    }),
    [isLoading, accessToken, user, login, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within <AuthProvider>");
  }
  return ctx;
}

