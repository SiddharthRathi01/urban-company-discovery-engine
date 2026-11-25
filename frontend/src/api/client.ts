// Thin client for the FastAPI backend. Same-origin /api/v1 (Vite proxies it in development, FastAPI serves it in production). No keys are involved.
export interface Envelope<T> {
  data: T;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  meta: Record<string, any>;
}

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: unknown) {
    super(message);
  }
}

export type Params = Record<string, string | number | boolean | undefined | null>;
const BASE = "/api/v1";
const cache = new Map<string, Promise<Envelope<unknown>>>();

function url(path: string, params?: Params) {
  const q = new URLSearchParams();
  Object.entries(params ?? {}).forEach(([k, v]) => v !== undefined && v !== null && v !== "" && q.set(k, String(v)));
  const s = q.toString();
  return `${BASE}${path}${s ? `?${s}` : ""}`;
}

async function request<T>(u: string, init?: RequestInit): Promise<Envelope<T>> {
  let res: Response;
  try {
    res = await fetch(u, init);
  } catch {
    throw new ApiError(0, "network_error", "Cannot reach the backend. Start it with start-app.cmd (or the API on port 8000).");
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const e = body?.error;
    throw new ApiError(res.status, e?.code ?? "http_error", e?.message ?? `Request failed (${res.status})`, e?.details);
  }
  return body as Envelope<T>;
}

/** GET with an in-memory cache (the analysis is precomputed, so responses do not change while the page is open). */
export function get<T>(path: string, params?: Params): Promise<Envelope<T>> {
  const u = url(path, params);
  let p = cache.get(u) as Promise<Envelope<T>> | undefined;
  if (!p) {
    p = request<T>(u);
    p.catch(() => cache.delete(u));
    cache.set(u, p as Promise<Envelope<unknown>>);
  }
  return p;
}

export function upload<T>(path: string, file: File): Promise<Envelope<T>> {
  const form = new FormData();
  form.append("file", file);
  return request<T>(`${BASE}${path}`, { method: "POST", body: form });
}

export function post<T>(path: string): Promise<Envelope<T>> {
  return request<T>(`${BASE}${path}`, { method: "POST" });
}

/** GET without the cache (job polling, freshly uploaded data). */
export function getFresh<T>(path: string, params?: Params): Promise<Envelope<T>> {
  return request<T>(url(path, params));
}

export function postForm<T>(path: string, form: FormData): Promise<Envelope<T>> {
  return request<T>(`${BASE}${path}`, { method: "POST", body: form });
}

export function postJson<T>(path: string, body: unknown): Promise<Envelope<T>> {
  return request<T>(`${BASE}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}
