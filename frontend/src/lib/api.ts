export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api";

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

function waitForRetry(delay: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    signal.throwIfAborted();
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", abort);
      resolve();
    }, delay);
    function abort() {
      clearTimeout(timer);
      reject(signal.reason);
    }
    signal.addEventListener("abort", abort, { once: true });
  });
}

async function fetchApi(path: string, init: RequestInit): Promise<Response> {
  // Free API instances may return a gateway error while waking up. Only
  // replay reads: a failed write may already have reached the database.
  const retryable = (init.method ?? "GET").toUpperCase() === "GET";
  const deadline = AbortSignal.timeout(retryable ? 120_000 : 60_000);
  const signal = init.signal ? AbortSignal.any([init.signal, deadline]) : deadline;
  // Keep checking for the whole startup window. An attempt limit can expire
  // much earlier when the gateway returns immediately while the API sleeps.
  for (let attempt = 0; ; attempt++) {
    signal.throwIfAborted();
    let response: Response | undefined;
    try {
      response = await fetch(`${API_URL}${path}`, {
        ...init, credentials: "include", cache: "no-store",
        signal: AbortSignal.any([signal, AbortSignal.timeout(retryable ? 15_000 : 60_000)]),
      });
    } catch (reason) {
      if (signal.aborted || !retryable) throw reason;
    }
    // Hosting gateways can also serve an HTML wake-up page with HTTP 200.
    const wakingPage = response?.ok && response.headers.get("content-type")?.includes("text/html");
    if (response && (!retryable || (![502, 503, 504].includes(response.status) && !wakingPage))) {
      return response;
    }
    // Release discarded gateway response bodies before the next request.
    await response?.body?.cancel();
    await waitForRetry(Math.min(2_000 * 2 ** attempt, 5_000), signal);
  }
}

export async function api<T>(path: string, token?: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("X-CSRF-Token", token);
  let response: Response;
  try {
    response = await fetchApi(path, { ...init, headers });
  } catch (reason) {
    if (init.signal?.aborted) throw reason;
    throw new ApiError("The workspace could not be reached. It may be waking up; try again shortly.", 0);
  }
  const isJson = response.headers.get("content-type")?.includes("application/json");
  const body = isJson ? await response.json() : null;
  if (!response.ok) {
    const fallback = response.status === 401 ? "Your session has expired. Sign in again."
      : [502, 503, 504].includes(response.status) ? "The workspace is temporarily unavailable. Try again shortly."
      : response.status === 413 ? "This file exceeds the workspace upload limit. Choose a smaller file."
      : response.status === 429 ? "Too many requests. Wait a minute before trying again."
      : `Request failed (${response.status}). Please try again.`;
    const detail = body?.error?.message ?? body?.detail;
    throw new ApiError(typeof detail === "string" ? detail : fallback, response.status);
  }
  if (response.status === 204) return undefined as T;
  if (!isJson) throw new ApiError("The server returned an unexpected response. Please try again.", response.status);
  return body as T;
}

export function errorMessage(reason: unknown, fallback = "Could not complete this action.") {
  return reason instanceof Error ? reason.message : fallback;
}

export function validateUpload(file: File, maxBytes: number) {
  if (!/\.(pdf|txt|md)$/i.test(file.name)) return "Choose a PDF, TXT or Markdown file.";
  if (!file.size) return "The selected file is empty. Choose a file with source content.";
  if (file.size > maxBytes) return `Choose a file smaller than ${Math.round(maxBytes / 1024 / 1024)} MB.`;
  return null;
}
