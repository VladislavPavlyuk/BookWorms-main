import React, { createContext, useContext, useEffect, useState } from "react";
import { AuthApi, clearTokens, getAccess, setTokens } from "./api";
import type { User } from "./types";

type Ctx = {
  user: User | null;
  ready: boolean;
  login: (u: string, p: string) => Promise<void>;
  logout: () => Promise<void>;
  reload: () => Promise<void>;
};

const C = createContext<Ctx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  const reload = async () => {
    const t = await getAccess();
    if (!t) {
      setUser(null);
      return;
    }
    try {
      setUser(await AuthApi.me());
    } catch {
      await clearTokens();
      setUser(null);
    }
  };

  useEffect(() => {
    reload().finally(() => setReady(true));
  }, []);

  const login = async (username: string, password: string) => {
    const data = await AuthApi.login(username, password);
    await setTokens(data.access, data.refresh);
    setUser(data.user);
  };

  const logout = async () => {
    await clearTokens();
    setUser(null);
  };

  return (
    <C.Provider value={{ user, ready, login, logout, reload }}>{children}</C.Provider>
  );
}

export function useAuth() {
  const v = useContext(C);
  if (!v) throw new Error("useAuth");
  return v;
}
