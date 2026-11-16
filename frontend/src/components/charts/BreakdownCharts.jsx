/** Top filler words and the modes breakdown. */
import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ChartCard, ChartTooltip } from './ChartCard';
import { AXIS_STROKE, GRID_STROKE, SINGLE_SERIES } from './chartTheme';

function HorizontalBars({ data, categoryKey, valueKey, name, domain, categoryWidth = 92, ariaLabel, showCategories = true }) {
  return (
    <div style={{ height: Math.max(120, data.length * 38 + 8) }} aria-label={ariaLabel}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 36, bottom: 0, left: 0 }} barCategoryGap="24%">
          <CartesianGrid horizontal={false} stroke={GRID_STROKE} />
          <XAxis type="number" domain={domain} hide />
          <YAxis
            type="category"
            dataKey={categoryKey}
            width={categoryWidth}
            tick={{ fill: 'var(--color-ink-soft)', fontSize: 13 }}
            tickLine={false}
            axisLine={{ stroke: AXIS_STROKE }}
            interval={0}
            hide={!showCategories}
          />
          <Tooltip cursor={{ fill: 'var(--color-chart-band)' }} content={<ChartTooltip />} />
          <Bar dataKey={valueKey} name={name} fill={SINGLE_SERIES} maxBarSize={20} radius={[0, 4, 4, 0]} isAnimationActive={false}>
            <LabelList dataKey={valueKey} position="right" fill="var(--color-ink)" fontSize={13} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function TopFillers({ fillers }) {
  const data = fillers.slice(0, 8);
  return (
    <ChartCard
      title="Which fillers do you lean on?"
      subtitle="Times each word came up in this period."
      table={{
        columns: [
          { key: 'word', label: 'Word' },
          { key: 'count', label: 'Times used', align: 'right' },
        ],
        rows: data,
      }}
    >
      {data.length === 0 ? (
        <p className="py-10 text-center text-sm text-ink-soft">No filler words counted yet. Lovely.</p>
      ) : (
        <HorizontalBars data={data} categoryKey="word" valueKey="count" name="Times used" domain={[0, 'dataMax']} ariaLabel="Bar chart of your most used filler words" />
      )}
    </ChartCard>
  );
}

export function ModesBreakdown({ modes }) {
  // Sessions and score have different scales, so they get two small charts rather than a dual axis.
  const scored = modes.filter((mode) => mode.avg_score !== null && mode.avg_score !== undefined);
  return (
    <ChartCard
      title="Which modes do you practise, and how do they go?"
      subtitle="Session count and average score for each mode."
      table={{
        columns: [
          { key: 'name', label: 'Mode' },
          { key: 'sessions', label: 'Sessions', align: 'right' },
          { key: 'avg_score', label: 'Average score', align: 'right' },
        ],
        rows: modes,
      }}
    >
      <div className="grid gap-6 sm:grid-cols-2">
        <div className="min-w-0">
          <p className="mb-2 text-xs font-semibold text-ink-soft">Sessions</p>
          <HorizontalBars data={modes} categoryKey="name" valueKey="sessions" name="Sessions" domain={[0, 'dataMax']} ariaLabel="Bar chart of sessions per mode" />
        </div>
        <div className="min-w-0">
          <p className="mb-2 text-xs font-semibold text-ink-soft">Average score</p>
          <HorizontalBars data={scored} categoryKey="name" valueKey="avg_score" name="Average score" domain={[0, 100]} ariaLabel="Bar chart of average score per mode" />
        </div>
      </div>
    </ChartCard>
  );
}
