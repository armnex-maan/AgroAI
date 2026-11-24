const API = import.meta.env.VITE_API_URL || "";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
  });
  if (!r.ok) {
    const txt = await r.text();
    // FastAPI errors carry a readable Italian message in "detail": show that instead of the raw response
    let detail: unknown = null;
    try { detail = JSON.parse(txt)?.detail; } catch { /* not JSON */ }
    throw new Error(typeof detail === "string" ? detail : `${r.status} ${r.statusText}: ${txt}`);
  }
  if (r.status === 204) return undefined as T;
  return (await r.json()) as T;
}

export const api = {
  get: <T>(p: string) => request<T>(p),
  post: <T>(p: string, body?: unknown) =>
    request<T>(p, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(p: string, body?: unknown) =>
    request<T>(p, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(p: string, body?: unknown) =>
    request<T>(p, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  del: <T>(p: string) => request<T>(p, { method: "DELETE" }),
};

export function wsUrl(path: string): string {
  if (API.startsWith("http")) {
    const u = new URL(path, API);
    u.protocol = u.protocol.replace("http", "ws");
    return u.toString();
  }
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}${path}`;
}
