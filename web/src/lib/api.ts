/**
 * Default: same-origin relative calls through Next.js.
 * - Next API routes (e.g. /api/charts) are handled by Next
 * - Other /api/* are rewritten to the Python backend (next.config.ts)
 *
 * Set NEXT_PUBLIC_API_URL only if you intentionally want to bypass Next
 * and hit FastAPI directly (then charts must also exist on FastAPI).
 */
const envUrl = (process.env.NEXT_PUBLIC_API_URL ?? "").trim().replace(/\/$/, "");

export const API_BASE_URL: string = envUrl;

/** Human label for UI status lines */
export const API_DISPLAY_URL: string =
  envUrl || "http://localhost:3000 (proxy → backend :9090)";

type ApiOptions = Omit<RequestInit, "body"> & { body?: unknown };

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch<T = unknown>(
  path: string,
  options: ApiOptions = {},
): Promise<T> {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  const url = `${API_BASE_URL}${normalized}`;
  const headers = new Headers(options.headers);
  if (options.body !== undefined && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(url, {
    ...options,
    headers,
    body:
      options.body !== undefined && !(options.body instanceof FormData)
        ? JSON.stringify(options.body)
        : (options.body as BodyInit | undefined),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new ApiError(text || res.statusText, res.status);
  }
  const contentType = res.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return (await res.json()) as T;
  }
  return (await res.text()) as unknown as T;
}
