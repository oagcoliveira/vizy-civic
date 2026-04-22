"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";

const TOKEN_KEY = "vizy_token";
const API = process.env.NEXT_PUBLIC_API_URL;

type AuthUser = { id: number; email: string; name: string };

type AuthContextType = {
  user: AuthUser | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  loading: boolean;
};

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  // On mount, restore token from localStorage and fetch current user
  useEffect(() => {
    const stored = typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
    if (stored) {
      setToken(stored);
      fetch(`${API}/auth/me`, { headers: { Authorization: `Bearer ${stored}` } })
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => { if (data) setUser(data); else localStorage.removeItem(TOKEN_KEY); })
        .catch(() => localStorage.removeItem(TOKEN_KEY))
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  async function register(name: string, email: string, password: string) {
    const r = await fetch(`${API}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password }),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail ?? "Erro ao criar conta");
    }
    await login(email, password);
  }

  async function login(email: string, password: string) {
    const body = new URLSearchParams({ username: email, password });
    const r = await fetch(`${API}/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString(),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail ?? "Login failed");
    }
    const data = await r.json();
    localStorage.setItem(TOKEN_KEY, data.access_token);
    setToken(data.access_token);

    const me = await fetch(`${API}/auth/me`, {
      headers: { Authorization: `Bearer ${data.access_token}` },
    }).then((r) => r.json());
    setUser(me);
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, token, login, register, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
