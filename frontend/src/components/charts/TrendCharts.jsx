/** Change over time: overall score with optional skills, speaking pace, and filler rate. */
import { useMemo, useState } from 'react';
import { Area, AreaChart, CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ChartCard, ChartTooltip, LegendRow } from './ChartCard';
import { AXIS_STROKE, AXIS_TICK, GRID_STROKE, LINE_PROPS, OVERALL, SINGLE_SERIES, SKILLS, pointDot } from './chartTheme';
import { oneDecimal, rounded, shortDate } from '../../lib/format';

// Past three skills plus overall, lines converge and colors stop being readable.
const MAX_SELECTED_SKILLS = 3;

/** Trends are per session, and two sessions can share a date, so x is the session id, shown as a date. */
function dateTickFormatter(rows) {
  const dates = Object.fromEntries(rows.map((row) => [row.session_id, row.date]));
  return (id) => shortDate(dates[id]);
}

const xAxisProps = (rows) => ({
  dataKey: 'session_id',
  tickFormatter: dateTickFormatter(rows),
  tick: AXIS_TICK,
  tickLine: false,
  axisLine: { stroke: AXIS_STROKE },
  minTickGap: 28,
  interval: 'preserveStartEnd',
});

const yAxisProps = { tick: AXIS_TICK, tickLine: false, axisLine: false, width: 36 };

/** With one session there is no line to draw yet, so say so rather than leave a lonely dot unexplained. */
function SinglePointNote({ rows }) {
  if (rows.length !== 1) return null;
  return <p className="mt-2 text-center text-xs text-ink-muted">One session so far. Your trend line appears after the next one.</p>;
}

function steppedTicks(min, max, step) {
  const ticks = [];
  for (let value = min; value <= max; value += step) ticks.push(value);
  return ticks;
}

const tooltipLabel = (rows) => (id) => shortDate(rows.find((row) => row.session_id === id)?.date);

export function ScoreTrend({ rows }) {
  const [selected, setSelected] = useState([]);
  const available = useMemo(() => SKILLS.filter((skill) => rows.some((row) => row[skill.id] !== null && row[skill.id] !== undefined)), [rows]);
  const atLimit = selected.length >= MAX_SELECTED_SKILLS;

  const toggle = (id) => setSelected((list) => (list.includes(id) ? list.filter((item) => item !== id) : [...list, id]));

  const shownSkills = available.filter((skill) => selected.includes(skill.id));
  const table = {
    columns: [
      { key: 'date', label: 'Date' },
      { key: 'overall', label: 'Overall', align: 'right' },
      ...shownSkills.map((skill) => ({ key: skill.id, label: skill.name, align: 'right' })),
    ],
    rows: rows.map((row) => ({ ...row, key: row.session_id, date: shortDate(row.date) })),
  };

  return (
    <ChartCard title="Is your score going up?" subtitle="One point per session. Add up to three skills to compare them against your overall score." table={table}>
      {/* The legend doubles as the skill picker, so identity and selection live in one place. */}
      <div role="group" aria-label="Skills to show on the chart" className="mb-4 flex flex-wrap gap-2">
        <span className="flex min-h-9 items-center gap-2 rounded-lg px-1 text-xs font-medium text-ink-soft">
          <span aria-hidden="true" className="h-0.5 w-3.5 rounded-full" style={{ background: OVERALL.color }} />
          Overall
        </span>
        {available.map((skill) => {
          const on = selected.includes(skill.id);
          return (
            <button
              key={skill.id}
              type="button"
              aria-pressed={on}
              disabled={!on && atLimit}
              onClick={() => toggle(skill.id)}
              className={`flex min-h-9 items-center gap-2 rounded-lg border px-2.5 text-xs font-medium transition-colors disabled:opacity-40 ${
                on ? 'border-line-strong bg-overlay text-ink' : 'border-line text-ink-muted hover:text-ink'
              }`}
            >
              <span aria-hidden="true" className="h-0.5 w-3.5 rounded-full" style={{ background: skill.color }} />
              {skill.name}
            </button>
          );
        })}
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke={GRID_STROKE} />
            <XAxis {...xAxisProps(rows)} />
            <YAxis {...yAxisProps} domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} />
            <Tooltip cursor={{ stroke: AXIS_STROKE }} content={<ChartTooltip labelFormatter={tooltipLabel(rows)} />} />
            {shownSkills.map((skill) => (
              <Line key={skill.id} {...LINE_PROPS} name={skill.name} dataKey={skill.id} stroke={skill.color} dot={pointDot(skill.color, rows.length)} connectNulls />
            ))}
            <Line {...LINE_PROPS} name={OVERALL.name} dataKey="overall" stroke={OVERALL.color} dot={pointDot(OVERALL.color, rows.length)} activeDot={{ r: 5 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <SinglePointNote rows={rows} />
    </ChartCard>
  );
}

export function PaceTrend({ rows, band }) {
  const low = band?.low ?? 120;
  const high = band?.high ?? 160;
  const values = rows.map((row) => row.wpm).filter((value) => value !== null && value !== undefined);
  // Always keep the whole target band in view, so "inside or outside" can be read at a glance.
  const yMin = Math.max(0, Math.floor((Math.min(low, ...values) - 15) / 20) * 20);
  const yMax = Math.ceil((Math.max(high, ...values) + 15) / 20) * 20;
  const yStep = yMax - yMin > 120 ? 40 : 20;

  const table = {
    columns: [
      { key: 'date', label: 'Date' },
      { key: 'wpm', label: 'Words per minute', align: 'right' },
      { key: 'zone', label: 'Target band' },
    ],
    rows: rows.map((row) => ({
      key: row.session_id,
      date: shortDate(row.date),
      wpm: rounded(row.wpm),
      zone: row.wpm < low ? 'Below' : row.wpm > high ? 'Above' : 'Inside',
    })),
  };

  return (
    <ChartCard title="Are you speaking at a comfortable pace?" subtitle={`Words per minute. The shaded band, ${low} to ${high}, is easy for most listeners to follow.`} table={table}>
      <LegendRow
        items={[
          { label: 'Your pace', color: SINGLE_SERIES },
          { label: `Target ${low}–${high}`, color: 'var(--color-line-strong)', kind: 'block' },
        ]}
      />
      <div className="h-60">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke={GRID_STROKE} />
            <XAxis {...xAxisProps(rows)} />
            <YAxis {...yAxisProps} domain={[yMin, yMax]} ticks={steppedTicks(yMin, yMax, yStep)} />
            <ReferenceArea y1={low} y2={high} fill="var(--color-line-strong)" fillOpacity={0.45} stroke="none" ifOverflow="extendDomain" />
            <Tooltip
              cursor={{ stroke: AXIS_STROKE }}
              content={<ChartTooltip labelFormatter={tooltipLabel(rows)} valueFormatter={(value) => `${rounded(value)} WPM`} />}
            />
            <Line {...LINE_PROPS} name="Pace" dataKey="wpm" stroke={SINGLE_SERIES} dot={pointDot(SINGLE_SERIES, rows.length)} activeDot={{ r: 5 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <SinglePointNote rows={rows} />
    </ChartCard>
  );
}

export function FillerTrend({ rows }) {
  const highest = Math.max(4, ...rows.map((row) => row.per_100 ?? 0));
  const step = highest <= 8 ? 2 : highest <= 20 ? 5 : 10;
  const top = Math.ceil(highest / step) * step;
  const table = {
    columns: [
      { key: 'date', label: 'Date' },
      { key: 'per_100', label: 'Fillers per 100 words', align: 'right' },
    ],
    rows: rows.map((row) => ({ key: row.session_id, date: shortDate(row.date), per_100: oneDecimal(row.per_100) })),
  };

  return (
    <ChartCard title="Are the ums and likes fading?" subtitle="Filler words per 100 words spoken. Lower is better." table={table}>
      <div className="h-60">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke={GRID_STROKE} />
            <XAxis {...xAxisProps(rows)} />
            <YAxis {...yAxisProps} domain={[0, top]} ticks={steppedTicks(0, top, step)} />
            <Tooltip
              cursor={{ stroke: AXIS_STROKE }}
              content={<ChartTooltip labelFormatter={tooltipLabel(rows)} valueFormatter={(value) => `${oneDecimal(value)} per 100`} />}
            />
            <Area {...LINE_PROPS} name="Fillers" dataKey="per_100" stroke={SINGLE_SERIES} fill={SINGLE_SERIES} fillOpacity={0.1} dot={pointDot(SINGLE_SERIES, rows.length)} activeDot={{ r: 5 }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <SinglePointNote rows={rows} />
    </ChartCard>
  );
}

