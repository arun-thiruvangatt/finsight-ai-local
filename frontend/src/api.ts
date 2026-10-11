const BASE: string = (import.meta as any).env?.VITE_API_URL || "/api/v1";

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

const store = {
  get access() { return localStorage.getItem("access"); },
  get refresh() { return localStorage.getItem("refresh"); },
  set(tokens: { access_token: string; refresh_token: string }) {
    localStorage.setItem("access", tokens.access_token);
    localStorage.setItem("refresh", tokens.refresh_token);
  },
  clear() { localStorage.removeItem("access"); localStorage.removeItem("refresh"); },
};
export const tokens = store;

type Opts = { method?: string; body?: any; form?: FormData; retry?: boolean };

let refreshing: Promise<boolean> | null = null;
async function tryRefresh(): Promise<boolean> {
  if (!store.refresh) return false;
  refreshing ??= fetch(`${BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: store.refresh }),
  })
    .then(async (r) => {
      if (!r.ok) return false;
      store.set(await r.json());
      return true;
    })
    .catch(() => false)
    .finally(() => { refreshing = null; });
  return refreshing;
}

export async function api<T = any>(path: string, opts: Opts = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (store.access) headers.Authorization = `Bearer ${store.access}`;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.body); }

  const res = await fetch(`${BASE}${path}`, { method: opts.method || "GET", headers, body });
  if (res.status === 401 && opts.retry !== false && !path.startsWith("/auth/") && (await tryRefresh())) {
    return api<T>(path, { ...opts, retry: false });
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = data?.error;
    if (res.status === 401 && !path.startsWith("/auth/login")) { store.clear(); window.location.href = "/login"; }
    throw new ApiError(res.status, err?.code || "ERROR", err?.message || res.statusText);
  }
  return data as T;
}

export const inr = (n: number | string | null | undefined) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(Number(n ?? 0));

export const thisMonth = () => new Date().toISOString().slice(0, 7);
