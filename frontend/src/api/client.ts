import { API_BASE_URL } from "../config";

export class ApiError extends Error {
  readonly kind: "not_configured" | "not_connected" | "http" | "schema";
  readonly status: number | null;

  constructor(kind: ApiError["kind"], message: string, status: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
  }
}

export function apiConfigured(): boolean {
  return API_BASE_URL.length > 0;
}

function errorMessage(body: unknown, status: number): string {
  if (typeof body === "object" && body !== null && "error" in body) {
    const error = (body as { error?: unknown }).error;
    if (typeof error === "object" && error !== null && "message" in error) {
      const message = (error as { message?: unknown }).message;
      if (typeof message === "string" && message.trim()) return message.trim();
    }
    if (typeof error === "string" && error.trim()) return error.trim();
  }
  if (typeof body === "string" && body.trim()) return body.trim().slice(0, 400);
  return `The API returned HTTP ${status}.`;
}

export async function apiPost<T>(
  path: string,
  body: unknown,
  parse: (data: unknown) => T,
): Promise<T> {
  if (!apiConfigured()) {
    throw new ApiError("not_configured", "VITE_API_BASE_URL is not set. The backend is not configured.");
  }
  const url = new URL(path.replace(/^\//, ""), `${API_BASE_URL}/`);
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      cache: "no-store",
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError("not_connected", "The backend did not respond. AirCast is not connected to the API.");
  }
  const text = await response.text();
  let parsed: unknown = null;
  if (text) {
    try {
      parsed = JSON.parse(text) as unknown;
    } catch {
      parsed = text;
    }
  }
  if (!response.ok) {
    throw new ApiError("http", errorMessage(parsed, response.status), response.status);
  }
  try {
    return parse(parsed);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Response did not match the expected schema.";
    throw new ApiError("schema", message);
  }
}

export async function apiGet<T>(
  path: string,
  params: Record<string, string | number | undefined>,
  parse: (data: unknown) => T,
): Promise<T> {
  if (!apiConfigured()) {
    throw new ApiError(
      "not_configured",
      "VITE_API_BASE_URL is not set. The backend is not configured.",
    );
  }

  const url = new URL(path.replace(/^\//, ""), `${API_BASE_URL}/`);
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") url.searchParams.set(key, String(value));
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      "not_connected",
      "The backend did not respond. AirCast is not connected to the API.",
    );
  }

  const text = await response.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text) as unknown;
    } catch {
      body = text;
    }
  }

  if (!response.ok) {
    throw new ApiError("http", errorMessage(body, response.status), response.status);
  }

  try {
    return parse(body);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Response did not match the expected schema.";
    throw new ApiError("schema", message);
  }
}
