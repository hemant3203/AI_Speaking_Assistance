/** Display formatting for durations, dates and signed numbers, so every page words them alike. */

/** 118.4 -> "1:58". Used for timers and short speech lengths. */
export function clock(seconds) {
  const total = Math.max(0, Math.floor(seconds ?? 0));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

/** 4120 -> "1h 8m", 90 -> "1m 30s", 45 -> "45s". */
export function humanDuration(seconds) {
  const total = Math.round(seconds ?? 0);
  if (total < 60) return `${total}s`;
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  if (h > 0) return m ? `${h}h ${m}m` : `${h}h`;
  const s = total % 60;
  return s && m < 10 ? `${m}m ${s}s` : `${m}m`;
}

/** "2026-11-05" parsed as a calendar date. new Date(string) would read it as UTC and can shift the day. */
export function parseLocalDate(ymd) {
  const [y, m, d] = String(ymd).split('-').map(Number);
  return new Date(y, (m || 1) - 1, d || 1);
}

export function toYmd(date) {
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${m}-${d}`;
}

const SHORT_DATE = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' });
const LONG_DATE = new Intl.DateTimeFormat(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
const WEEKDAY = new Intl.DateTimeFormat(undefined, { weekday: 'narrow' });
const WEEKDAY_LONG = new Intl.DateTimeFormat(undefined, { weekday: 'long', month: 'short', day: 'numeric' });
const MONTH = new Intl.DateTimeFormat(undefined, { month: 'short' });

export const shortDate = (ymd) => (ymd ? SHORT_DATE.format(parseLocalDate(ymd)) : '');
export const longDate = (ymd) => (ymd ? LONG_DATE.format(parseLocalDate(ymd)) : '');
export const weekdayLetter = (ymd) => WEEKDAY.format(parseLocalDate(ymd));
export const weekdayLong = (ymd) => WEEKDAY_LONG.format(parseLocalDate(ymd));
export const monthName = (date) => MONTH.format(date);

export function dateTime(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

/** Today in the user's own timezone, because streak and quest days follow it, not the browser's. */
export function todayYmd(timeZone) {
  try {
    return new Intl.DateTimeFormat('en-CA', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
  } catch {
    return toYmd(new Date());
  }
}

export function signed(value, digits = 0) {
  if (value === null || value === undefined) return '';
  const fixed = Number(value).toFixed(digits);
  return Number(value) > 0 ? `+${fixed}` : fixed;
}

export const number = (value) => (value === null || value === undefined ? '–' : Number(value).toLocaleString());

/** One decimal, for rates such as fillers per 100 words. */
export const oneDecimal = (value) => (value === null || value === undefined ? '–' : Number(value).toFixed(1));

export const rounded = (value) => (value === null || value === undefined ? '–' : Math.round(value).toLocaleString());

export const plural = (count, one, many = `${one}s`) => `${count} ${count === 1 ? one : many}`;
