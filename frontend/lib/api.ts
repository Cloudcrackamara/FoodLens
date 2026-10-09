import type { z } from "zod";

/** Error from the FoodLens API, with the HTTP status and the server's message. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    /** From the Retry-After header on 429 responses. */
    public readonly retryAfterSeconds: number | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function parseRetryAfter(value: string | null): number | null {
  const seconds = value === null ? NaN : Number.parseInt(value, 10);
  return Number.isFinite(seconds) && seconds > 0 ? seconds : null;
}

function waitPhrase(seconds: number | null): string {
  if (seconds === null) return "in a minute or two";
  if (seconds < 60) return `in about ${seconds} second${seconds === 1 ? "" : "s"}`;
  const minutes = Math.ceil(seconds / 60);
  return `in about ${minutes} minute${minutes === 1 ? "" : "s"}`;
}

/** Message to show a person for any request error. Rate limits get a friendly explanation. */
export function describeError(error: Error): string {
  if (error instanceof ApiError && error.status === 429) {
    return (
      "Too many requests have come from your network recently. This limit is shared by " +
      "everyone on the same network (for example the same Wi-Fi), so it may not be caused " +
      `by you. Please try again ${waitPhrase(error.retryAfterSeconds)}.`
    );
  }
  return error.message;
}

type FastApiError = { detail?: string | { msg?: string }[] };

function errorMessage(status: number, payload: unknown): string {
  const detail = (payload as FastApiError | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  return `Request failed (${status})`;
}

/**
 * Call the API through the Next.js /api proxy so the session cookie stays same-origin.
 * Responses are validated with `schema`; pass null for empty responses (204).
 */
export async function apiFetch<T>(
  path: string,
  schema: z.ZodType<T> | null,
  init: { method?: string; body?: unknown } = {},
): Promise<T> {
  const response = await fetch(path, {
    method: init.method ?? "GET",
    credentials: "same-origin",
    headers: init.body === undefined ? undefined : { "Content-Type": "application/json" },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  });

  const payload: unknown =
    response.status === 204 ? null : await response.json().catch(() => null);

  if (!response.ok) {
    throw new ApiError(
      response.status,
      errorMessage(response.status, payload),
      parseRetryAfter(response.headers.get("Retry-After")),
    );
  }
  return schema ? schema.parse(payload) : (undefined as T);
}

/** Upload one file as multipart/form-data (field name "file") through the same-origin proxy. */
export async function apiUpload<T>(path: string, schema: z.ZodType<T>, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(path, { method: "POST", credentials: "same-origin", body: form });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(
      response.status,
      errorMessage(response.status, payload),
      parseRetryAfter(response.headers.get("Retry-After")),
    );
  }
  return schema.parse(payload);
}
