/**
 * 26 weeks of practice as a calendar grid in one sequential hue.
 * Built from plain elements, since Recharts has no calendar form. Weeks start on Monday.
 */
import { useMemo, useRef, useState } from 'react';
import { ChartCard } from './ChartCard';
import { humanDuration, longDate, monthName, parseLocalDate, plural, shortDate, todayYmd, toYmd } from '../../lib/format';

const DAYS_SHOWN = 182;
const LEVELS = ['var(--color-heat-0)', 'var(--color-heat-1)', 'var(--color-heat-2)', 'var(--color-heat-3)', 'var(--color-heat-4)'];

const levelFor = (sessions) => Math.min(sessions, 4);

function buildWeeks(heatmap, today) {
  const byDate = new Map(heatmap.map((day) => [day.date, day]));
  const end = parseLocalDate(today);
  const start = new Date(end);
  start.setDate(end.getDate() - (DAYS_SHOWN - 1));
  // Step back to the Monday on or before the start, so rows line up with weekdays.
  const cursor = new Date(start);
  cursor.setDate(cursor.getDate() - ((cursor.getDay() + 6) % 7));

  const weeks = [];
  while (cursor <= end) {
    const week = [];
    for (let i = 0; i < 7; i++) {
      const ymd = toYmd(cursor);
      const inRange = cursor >= start && cursor <= end;
      const entry = byDate.get(ymd);
      week.push(inRange ? { date: ymd, sessions: entry?.sessions ?? 0, speaking_seconds: entry?.speaking_seconds ?? 0 } : null);
      cursor.setDate(cursor.getDate() + 1);
    }
    weeks.push(week);
  }
  return weeks;
}

function monthLabels(weeks) {
  const labels = [];
  let lastMonth = null;
  weeks.forEach((week, column) => {
    const first = week.find(Boolean);
    if (!first) return;
    const date = parseLocalDate(first.date);
    if (date.getMonth() !== lastMonth) {
      lastMonth = date.getMonth();
      // Skip a label at the very edge if the next month would crowd it.
      labels.push({ column, label: monthName(date) });
    }
  });
  return labels.filter((item, index) => index === labels.length - 1 || labels[index + 1].column - item.column >= 3);
}

export function ActivityHeatmap({ heatmap, timeZone }) {
  const today = todayYmd(timeZone);
  const weeks = useMemo(() => buildWeeks(heatmap, today), [heatmap, today]);
  const months = useMemo(() => monthLabels(weeks), [weeks]);
  const [hover, setHover] = useState(null);
  const wrapRef = useRef(null);

  const onPointer = (event) => {
    const date = event.target?.dataset?.date;
    if (!date) {
      setHover(null);
      return;
    }
    const wrap = wrapRef.current.getBoundingClientRect();
    const cell = event.target.getBoundingClientRect();
    const day = weeks.flat().find((d) => d?.date === date);
    setHover({ day, x: Math.min(Math.max(cell.left - wrap.left + cell.width / 2, 72), wrap.width - 72), y: cell.top - wrap.top });
  };

  const activeDays = [...heatmap].sort((a, b) => (a.date < b.date ? 1 : -1));
  const table = {
    columns: [
      { key: 'date', label: 'Date' },
      { key: 'sessions', label: 'Sessions', align: 'right' },
      { key: 'time', label: 'Speaking time', align: 'right' },
    ],
    rows: activeDays.map((day) => ({ key: day.date, date: shortDate(day.date), sessions: day.sessions, time: humanDuration(day.speaking_seconds) })),
  };

  return (
    <ChartCard title="How often have you shown up?" subtitle={`Last 26 weeks. You practised on ${plural(heatmap.length, 'day')}.`} table={table}>
      <div ref={wrapRef} className="relative" onPointerMove={onPointer} onPointerDown={onPointer} onPointerLeave={() => setHover(null)}>
        <div className="grid gap-[3px] sm:gap-1" style={{ gridTemplateColumns: `repeat(${weeks.length}, minmax(0, 1fr))` }}>
          <div className="relative col-span-full h-5 text-xs text-ink-muted" aria-hidden="true">
            {months.map((month) => (
              <span key={`${month.label}${month.column}`} className="absolute" style={{ left: `${(month.column / weeks.length) * 100}%` }}>
                {month.label}
              </span>
            ))}
          </div>
          {/* Filling by column keeps the weekdays in rows without per-cell placement. */}
          <div
            role="img"
            aria-label={`Calendar of the last 26 weeks. You practised on ${plural(heatmap.length, 'day')}. Use the table button for the list of days.`}
            className="col-span-full grid grid-flow-col gap-[3px] sm:gap-1"
            style={{ gridTemplateRows: 'repeat(7, minmax(0, 1fr))', gridTemplateColumns: `repeat(${weeks.length}, minmax(0, 1fr))` }}
          >
            {weeks.flat().map((day, index) =>
              day ? (
                <div
                  key={day.date}
                  data-date={day.date}
                  className={`aspect-square rounded-[3px] ${hover?.day?.date === day.date ? 'outline-1 outline-ink' : ''}`}
                  style={{ background: LEVELS[levelFor(day.sessions)] }}
                />
              ) : (
                <div key={`pad${index}`} />
              ),
            )}
          </div>
        </div>
        {hover?.day && (
          <div
            className="pointer-events-none absolute z-10 w-max max-w-40 -translate-x-1/2 -translate-y-full rounded-lg border border-line-strong bg-overlay px-3 py-2 text-xs shadow-lg shadow-black/40"
            style={{ left: hover.x, top: hover.y - 6 }}
          >
            <p className="font-semibold text-ink">{hover.day.sessions === 0 ? 'No practice' : plural(hover.day.sessions, 'session')}</p>
            {hover.day.sessions > 0 && <p className="text-ink-soft">{humanDuration(hover.day.speaking_seconds)} speaking</p>}
            <p className="text-ink-muted">{longDate(hover.day.date)}</p>
          </div>
        )}
      </div>
      <div className="mt-3 flex items-center justify-end gap-1.5 text-xs text-ink-muted">
        <span>Fewer</span>
        {LEVELS.map((color, level) => (
          <span key={color} className="size-3 rounded-[3px]" style={{ background: color }} title={level === 4 ? '4 or more sessions' : plural(level, 'session')} />
        ))}
        <span>More sessions</span>
      </div>
    </ChartCard>
  );
}
