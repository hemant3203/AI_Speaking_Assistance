/**
 * Same-origin JSON client. All API errors become ApiError with the contract's `code`, so callers
 * can branch on codes instead of parsing messages.
 */
const BASE = '/api/v1';

export class ApiError extends Error {
  constructor(message, { status = 0, code = 'unknown_error' } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

let unauthorizedHandler = null;

/** AuthContext registers here, which keeps this module free of React. */
export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}

function buildUrl(path, query) {
  if (!query) return `${BASE}${path}`;
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') params.set(key, value);
  });
  const text = params.toString();
  return text ? `${BASE}${path}?${text}` : `${BASE}${path}`;
}

/**
 * @param {string} path Path below /api/v1.
 * @param {object} [options]
 * @param {boolean} [options.ignoreUnauthorized] A 401 here does not mean the session ended, for
 *   example a wrong password at login or when deleting the account.
 */
export async function api(path, { method = 'GET', body, query, signal, ignoreUnauthorized = false } = {}) {
  let response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      credentials: 'same-origin',
      headers: body === undefined ? { Accept: 'application/json' } : { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if (error?.name === 'AbortError') throw error;
    throw new ApiError("We can't reach Spotlight right now. Check your connection and try again.", { code: 'network_error' });
  }

  if (response.status === 204) return null;

  // nginx returns an HTML error page when the backend is down, so JSON cannot be assumed.
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    if (response.status === 401 && !ignoreUnauthorized) unauthorizedHandler?.();
    const fallback =
      response.status >= 500 ? 'Something went wrong on our side. Please try again in a moment.' : 'That request did not work. Please try again.';
    throw new ApiError(typeof payload?.detail === 'string' ? payload.detail : fallback, {
      status: response.status,
      code: payload?.code ?? (response.status >= 500 ? 'server_error' : 'request_failed'),
    });
  }
  return payload;
}

/** ws(s)://host for the page's own origin, so the same bundle works behind any proxy or port. */
export function liveSocketUrl(sessionId) {
  const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${scheme}//${window.location.host}${BASE}/live/${encodeURIComponent(sessionId)}`;
}
