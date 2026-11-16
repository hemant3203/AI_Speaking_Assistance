/** Two views of current skill levels: the shape (radar) and the ranking (bars, weakest first). */
import { Bar, BarChart, CartesianGrid, Cell, LabelList, PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ChartCard, ChartTooltip, LegendRow } from './ChartCard';
import { AXIS_STROKE, GRID_STROKE, SINGLE_SERIES, SKILL_BY_ID } from './chartTheme';
import { signed } from '../../lib/format';

const DEEMPHASIS = 'var(--color-chart-deemph)';
const PREVIOUS_LINE = 'var(--color-ink-muted)';

const scored = (skills) => skills.filter((skill) => skill.current !== null && skill.current !== undefined);

export function SkillRadar({ skills }) {
  const data = scored(skills).map((skill) => ({
    skill: SKILL_BY_ID[skill.id]?.short ?? skill.name,
    name: skill.name,
    current: skill.current,
    previous: skill.previous,
    // Plot a skill with no earlier data on the current value, so the outline stays honest.
    previous_plot: skill.previous ?? skill.current,
  }));
  const hasPrevious = data.some((row) => row.previous !== null && row.previous !== undefined);

  const table = {
    columns: [
      { key: 'name', label: 'Skill' },
      { key: 'current', label: 'This period', align: 'right' },
      { key: 'previous', label: 'Previous', align: 'right' },
    ],
    rows: data,
  };

  return (
    <ChartCard
      title="What shape are your skills in?"
      subtitle="Score out of 100 for each skill. Bigger means stronger."
      table={table}
      legend={
        hasPrevious ? (
          <LegendRow
            items={[
              { label: 'This period', color: SINGLE_SERIES },
              { label: 'Previous period', color: PREVIOUS_LINE },
            ]}
          />
        ) : null
      }
    >
      <div className="h-72" role="img" aria-label="Radar chart of current skill scores. Use the table button for exact values.">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data} outerRadius="78%" margin={{ top: 8, right: 28, bottom: 8, left: 28 }}>
            <PolarGrid stroke={AXIS_STROKE} />
            <PolarAngleAxis dataKey="skill" tick={{ fill: 'var(--color-ink-soft)', fontSize: 12 }} />
            <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} tickCount={5} />
            {hasPrevious && <Radar name="Previous period" dataKey="previous_plot" stroke={PREVIOUS_LINE} strokeWidth={2} fill="none" isAnimationActive={false} />}
            <Radar name="This period" dataKey="current" stroke={SINGLE_SERIES} strokeWidth={2} fill={SINGLE_SERIES} fillOpacity={0.12} isAnimationActive={false} />
            <Tooltip cursor={{ stroke: AXIS_STROKE }} content={<ChartTooltip
                  labelFormatter={(_, payload) => payload?.[0]?.payload?.name}
                  valueFormatter={(value, entry) => (entry.dataKey === 'previous_plot' ? entry.payload.previous ?? 'No data' : value)}
                />} />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  );
}

export function SkillBars({ skills, focusSkillIds = [] }) {
  // Emphasis form: focus areas carry the hue and the rest step back, because the story is "start here".
  const data = [...scored(skills)]
    .sort((a, b) => a.current - b.current)
    .map((skill) => ({ ...skill, fill: focusSkillIds.includes(skill.id) ? SINGLE_SERIES : DEEMPHASIS }));

  const table = {
    columns: [
      { key: 'name', label: 'Skill' },
      { key: 'current', label: 'Score', align: 'right' },
      { key: 'change', label: 'Change', align: 'right' },
      { key: 'samples', label: 'Sessions', align: 'right' },
    ],
    rows: data.map((skill) => ({ ...skill, change: skill.delta === null || skill.delta === undefined ? '–' : signed(skill.delta) })),
  };

  return (
    <ChartCard
      title="Which skills need you most?"
      subtitle="Ranked weakest first, out of 100."
      table={table}
      legend={
        <LegendRow
          items={[
            { label: 'Your focus areas', color: SINGLE_SERIES, kind: 'block' },
            { label: 'Other skills', color: DEEMPHASIS, kind: 'block' },
          ]}
        />
      }
    >
      <div style={{ height: Math.max(180, data.length * 36 + 8) }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 32, bottom: 0, left: 0 }} barCategoryGap="22%">
            <CartesianGrid horizontal={false} stroke={GRID_STROKE} />
            <XAxis type="number" domain={[0, 100]} hide />
            <YAxis type="category" dataKey="name" width={112} tick={{ fill: 'var(--color-ink-soft)', fontSize: 13 }} tickLine={false} axisLine={{ stroke: AXIS_STROKE }} interval={0} />
            <Tooltip
              cursor={{ fill: 'var(--color-chart-band)' }}
              content={
                <ChartTooltip
                  extra={(payload) => {
                    const row = payload[0]?.payload;
                    return row?.delta === null || row?.delta === undefined ? 'No earlier period to compare' : `${signed(row.delta)} vs previous period`;
                  }}
                />
              }
            />
            <Bar dataKey="current" name="Score" maxBarSize={20} radius={[0, 4, 4, 0]} isAnimationActive={false}>
              {data.map((row) => (
                <Cell key={row.id} fill={row.fill} />
              ))}
              <LabelList dataKey="current" position="right" fill="var(--color-ink)" fontSize={13} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  );
}
