/**
 * murphyClient.ts — TypeScript API client for the Murphy System backend.
 *
 * Mirrors the behavior of the vanilla-JS MurphyAPI class:
 *  - Reads API key from localStorage or VITE_MURPHY_API_KEY env
 *  - Sends X-API-Key and Content-Type: application/json headers
 *  - 3 retries with exponential backoff for 5xx responses
 *  - Circuit breaker (opens after 5 failures, half-open after 30 s)
 *
 * © 2020 Inoni Limited Liability Company · BSL 1.1
 */

import type { ApiResponse } from "./types";

// ── Config ────────────────────────────────────────────────────────────────

const BASE_URL = (import.meta?.env?.VITE_API_BASE ?? "").replace(/\/+$/, "");
const MAX_RETRIES = 3;
const TIMEOUT_MS = 10_000;
const CB_THRESHOLD = 5;
const CB_COOLDOWN_MS = 30_000;

// ── Circuit breaker state (module-level singleton) ────────────────────────

let _cbFailures = 0;
let _cbState: "closed" | "open" | "half-open" = "closed";
let _cbOpenedAt = 0;

function _checkCircuit(): boolean {
  if (_cbState === "closed") return true;
  if (_cbState === "open") {
    if (Date.now() - _cbOpenedAt >= CB_COOLDOWN_MS) {
      _cbState = "half-open";
      return true;
    }
    return false;
  }
  return true; // half-open allows one attempt
}

function _recordSuccess(): void {
  _cbFailures = 0;
  _cbState = "closed";
}

function _recordFailure(): void {
  _cbFailures += 1;
  if (_cbFailures >= CB_THRESHOLD) {
    _cbState = "open";
    _cbOpenedAt = Date.now();
  }
}

function _backoff(attempt: number): Promise<void> {
  const ms = Math.min(1000 * Math.pow(2, attempt), 8000);
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ── Header builder ────────────────────────────────────────────────────────

function _buildHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  try {
    const key =
      localStorage.getItem("murphy_api_key") ??
      (import.meta?.env?.VITE_MURPHY_API_KEY as string | undefined) ??
      "";
    if (key) headers["X-API-Key"] = key;
  } catch {
    /* localStorage unavailable */
  }
  return { ...headers, ...extra };
}

// ── Response normaliser ───────────────────────────────────────────────────

function _parseResponse<T>(data: unknown, status: number): ApiResponse<T> {
  if (data === null || data === undefined) {
    return { success: status < 400, data: data as T };
  }
  if (typeof data !== "object") {
    return { success: status < 400, data: data as T };
  }
  const obj = data as Record<string, unknown>;
  // Standard envelope
  if ("success" in obj) return obj as ApiResponse<T>;
  // Flask legacy: { status: 'error', message: '...' }
  if (obj.status === "error") {
    return { success: false, error: { code: "LEGACY_ERROR", message: String(obj.message ?? "Unknown error") } };
  }
  // FastAPI validation: { detail: '...' }
  if ("detail" in obj) {
    return { success: false, error: { code: `HTTP_${status}`, message: String(obj.detail) } };
  }
  // Custom: { error: '...', code: '...' }
  if (typeof obj.error === "string") {
    return { success: false, error: { code: String(obj.code ?? "ERROR"), message: obj.error } };
  }
  return { success: status < 400, data: data as T };
}

// ── Core request ──────────────────────────────────────────────────────────

async function _request<T>(
  method: string,
  path: string,
  body?: unknown,
  extraHeaders?: Record<string, string>
): Promise<ApiResponse<T>> {
  if (!_checkCircuit()) {
    return {
      success: false,
      error: { code: "CIRCUIT_OPEN", message: "Circuit breaker is open — too many consecutive failures" },
    };
  }

  const url = `${BASE_URL}${path}`;
  const init: RequestInit = {
    method,
    headers: _buildHeaders(extraHeaders),
  };
  if (body !== undefined) init.body = JSON.stringify(body);

  let lastError = "";
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);
    try {
      const response = await fetch(url, { ...init, signal: controller.signal });
      clearTimeout(timeoutId);

      // Retry on 5xx
      if (response.status >= 500) {
        lastError = `Server error ${response.status}`;
        _recordFailure();
        if (attempt < MAX_RETRIES) {
          await _backoff(attempt);
          continue;
        }
        return { success: false, error: { code: `HTTP_${response.status}`, message: lastError } };
      }

      _recordSuccess();

      let data: unknown = null;
      const ct = response.headers.get("content-type") ?? "";
      if (ct.includes("application/json")) {
        data = await response.json();
      } else {
        data = await response.text();
      }

      const parsed = _parseResponse<T>(data, response.status);
      if (!response.ok) {
        return {
          success: false,
          error: parsed.error ?? {
            code: `HTTP_${response.status}`,
            message: `HTTP ${response.status}`,
          },
        };
      }
      return parsed;
    } catch (err) {
      clearTimeout(timeoutId);
      const isAbort = err instanceof Error && err.name === "AbortError";
      lastError = isAbort ? "Request timed out" : (err instanceof Error ? err.message : String(err));
      _recordFailure();
      if (attempt < MAX_RETRIES) {
        await _backoff(attempt);
        continue;
      }
    }
  }
  return { success: false, error: { code: "NETWORK_ERROR", message: lastError } };
}

// ── Public API ────────────────────────────────────────────────────────────

/** Perform a GET request. */
export function get<T = unknown>(path: string): Promise<ApiResponse<T>> {
  return _request<T>("GET", path);
}

/** Perform a POST request. */
export function post<T = unknown>(path: string, body?: unknown): Promise<ApiResponse<T>> {
  return _request<T>("POST", path, body);
}

/** Perform a PUT request. */
export function put<T = unknown>(path: string, body?: unknown): Promise<ApiResponse<T>> {
  return _request<T>("PUT", path, body);
}

/** Perform a DELETE request. */
export function del<T = unknown>(path: string): Promise<ApiResponse<T>> {
  return _request<T>("DELETE", path);
}
