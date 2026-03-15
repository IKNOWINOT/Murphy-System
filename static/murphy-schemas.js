/* murphy-schemas.js — JSDoc-typed factory functions and validators for Murphy API responses.
 * Include this after murphy-components.js in HTML pages that need type-safe API helpers.
 *
 * © 2020 Inoni Limited Liability Company · BSL 1.1
 */

/* ── Type Definitions (JSDoc) ───────────────────────────────────────────── */

/**
 * @typedef {Object} ApiError
 * @property {string} code   Machine-readable error code (e.g. "NOT_FOUND").
 * @property {string} message Human-readable description.
 */

/**
 * Standard Murphy API response envelope.
 * @template T
 * @typedef {Object} ApiResponse
 * @property {boolean} success  Whether the call succeeded.
 * @property {T}       [data]   Payload on success.
 * @property {ApiError} [error] Error details on failure.
 */

/**
 * @typedef {Object} HealthStatus
 * @property {string}  status   "healthy" | "degraded" | "unhealthy"
 * @property {string}  [version]
 * @property {boolean} [mfgc_enabled]
 * @property {number}  [uptime_seconds]
 */

/**
 * @typedef {Object} FormSubmissionResult
 * @property {string} form_id
 * @property {string} form_type
 * @property {string} status   "pending" | "processing" | "completed" | "failed"
 * @property {string} [submitted_at]
 * @property {string} [completed_at]
 * @property {*}      [result]
 * @property {string[]} [errors]
 */

/**
 * @typedef {Object} FlowExecutionResult
 * @property {boolean} success
 * @property {*}       [output]
 * @property {string}  [trace_id]
 * @property {string}  [error]
 */

/**
 * @typedef {Object} ModuleSpec
 * @property {string}   module_id
 * @property {string}   source_path
 * @property {string}   [version_hash]
 * @property {Object[]} capabilities
 * @property {string}   verification_status  "passed" | "failed" | "pending"
 * @property {boolean}  is_partial
 * @property {boolean}  requires_manual_review
 * @property {string[]} uncertainty_flags
 * @property {string}   [compiled_at]
 */

/* ── Validators ─────────────────────────────────────────────────────────── */

/**
 * Ensure a raw API response conforms to the standard envelope shape.
 * Normalises legacy Flask and FastAPI error formats.
 *
 * @template T
 * @param {*} resp  Raw JSON-parsed value from fetch().
 * @param {number} [status=200] HTTP status code.
 * @returns {ApiResponse<T>}
 */
function validateApiResponse(resp, status) {
  status = status || 200;
  if (resp === null || resp === undefined) {
    return { success: status < 400, data: resp };
  }
  if (typeof resp !== 'object') {
    return { success: status < 400, data: resp };
  }
  // Already standard envelope
  if ('success' in resp) return resp;
  // Flask legacy: { status: 'error', message: '...' }
  if (resp.status === 'error') {
    return { success: false, error: { code: 'LEGACY_ERROR', message: resp.message || 'Unknown error' } };
  }
  // FastAPI: { detail: '...' }
  if ('detail' in resp) {
    return { success: false, error: { code: 'HTTP_' + status, message: String(resp.detail) } };
  }
  // Custom: { error: '...', code: '...' }
  if (typeof resp.error === 'string') {
    return { success: false, error: { code: resp.code || 'ERROR', message: resp.error } };
  }
  return { success: status < 400, data: resp };
}

/**
 * Assert that an ApiResponse is successful; throws if not.
 * Useful for one-liner calls: `const data = assertOk(await api.get('/health'))`.
 *
 * @template T
 * @param {ApiResponse<T>} resp
 * @returns {T}
 */
function assertOk(resp) {
  if (!resp || !resp.success) {
    var msg = (resp && resp.error && resp.error.message) || 'API call failed';
    throw new Error(msg);
  }
  return resp.data;
}

/* ── Exports ────────────────────────────────────────────────────────────── */

window.validateApiResponse = validateApiResponse;
window.assertOk = assertOk;
