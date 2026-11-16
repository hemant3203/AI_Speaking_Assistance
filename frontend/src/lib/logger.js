/**
 * App logger: console in dev; warn and error also go to the backend, so browser failures are visible.
 *
 * Shipping is best effort. It is throttled, can never throw, and strips anything transcript-like,
 * because speech content must never reach the logs.
 */
const IS_DEV = import.meta.env.DEV;
const MAX_PER_MINUTE = 10;
const DEDUPE_MS = 30000;
const BLOCKED_KEYS = /transcript|text|password|token|cookie|feedback|topic/i;

let windowStart = 0;
let sentInWindow = 0;
const lastSent = new Map();

function sanitize(context) {
  if (!context || typeof context !== 'object') return undefined;
  const clean = {};
  for (const [key, value] of Object.entries(context)) {
    if (BLOCKED_KEYS.test(key)) continue;
    if (typeof value === 'string') clean[key] = value.slice(0, 500);
    else if (typeof value === 'number' || typeof value === 'boolean' || value === null) clean[key] = value;
  }
  return clean;
}

function allowed(message) {
  const now = Date.now();
  if (now - windowStart > 60000) {
    windowStart = now;
    sentInWindow = 0;
  }
  if (sentInWindow >= MAX_PER_MINUTE) return false;
  if (now - (lastSent.get(message) ?? 0) < DEDUPE_MS) return false;
  if (lastSent.size > 100) lastSent.clear();
  lastSent.set(message, now);
  sentInWindow += 1;
  return true;
}

function ship(level, message, context) {
  try {
    const text = String(message).slice(0, 500);
    if (!allowed(text)) return;
    // Plain fetch rather than the API client: a failing log call must not route back into logging.
    fetch('/api/v1/client-logs', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ level, message: text, context: sanitize(context) }),
      keepalive: true,
    }).catch(() => {});
  } catch {
    // Logging must never become the thing that breaks the app.
  }
}

export const logger = {
  debug(message, context) {
    if (IS_DEV) console.debug(message, context ?? '');
  },
  info(message, context) {
    if (IS_DEV) console.info(message, context ?? '');
  },
  warn(message, context) {
    if (IS_DEV) console.warn(message, context ?? '');
    ship('warn', message, context);
  },
  error(message, context) {
    if (IS_DEV) console.error(message, context ?? '');
    ship('error', message, context);
  },
};

/** Report uncaught errors too, which React's ErrorBoundary never sees. */
export function installGlobalErrorLogging() {
  window.addEventListener('error', (event) => {
    logger.error(event.message || 'Uncaught error', { source: event.filename, line: event.lineno });
  });
  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason;
    // Expected API errors are shown in the UI, so they are not bugs worth logging.
    if (reason?.name === 'ApiError') return;
    logger.error(reason?.message || 'Unhandled promise rejection', { name: reason?.name });
  });
}
