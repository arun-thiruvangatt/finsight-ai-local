import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api, tokens } from "./api";

type AuthCtx = {
  user: any;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, full_name: string) => Promise<void>;
  logout: () => Promise<void>;
  setUser: (u: any) => void;
};
const Ctx = createContext<AuthCtx>(null as any);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!tokens.access) { setLoading(false); return; }
    api("/auth/me").then(setUser).catch(() => tokens.clear()).finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const t = await api("/auth/login", { method: "POST", body: { email, password } });
    tokens.set(t);
    setUser(await api("/auth/me"));
  };
  const register = async (email: string, password: string, full_name: string) => {
    await api("/auth/register", { method: "POST", body: { email, password, full_name } });
    await login(email, password);
  };
  const logout = async () => {
    try { await api("/auth/logout", { method: "POST", body: { refresh_token: tokens.refresh } }); } catch { /* ignore */ }
    tokens.clear();
    setUser(null);
  };
  return <Ctx.Provider value={{ user, loading, login, register, logout, setUser }}>{children}</Ctx.Provider>;
}
