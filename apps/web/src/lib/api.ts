const TOKEN_KEY = "sismo_token";

/**
 * Base de la API. En desarrollo se deja vacia para usar el proxy de Vite
 * (`/api` -> localhost:8000); en despliegue (Vercel) se define
 * VITE_API_URL con la URL publica del backend (Render).
 */
export const API_BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/+$/, "");

export function apiUrl(path: string): string {
  return path.startsWith("http") ? path : `${API_BASE}${path}`;
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

interface RequestOptions {
  method?: string;
  json?: unknown;
  formData?: FormData;
  auth?: boolean;
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.auth !== false) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  let body: BodyInit | undefined;
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  } else if (options.formData) {
    body = options.formData;
  }

  const res = await fetch(apiUrl(path), { method: options.method ?? "GET", headers, body });
  if (res.status === 401 && !path.includes("/auth/login")) {
    setToken(null);
    window.location.href = "/login";
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const payload = await res.json();
      detail = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail);
    } catch {
      /* sin cuerpo JSON */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function qs(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => search.append(key, String(v)));
    else search.append(key, String(value));
  }
  const str = search.toString();
  return str ? `?${str}` : "";
}
