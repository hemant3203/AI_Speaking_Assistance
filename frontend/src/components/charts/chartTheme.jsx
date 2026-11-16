/**
 * Shared chart constants.
 *
 * Skill colors are bound to the skill, not to its rank or position, so "Pace" is the same blue in
 * every chart and whatever else is filtered. Series tokens come from the dark categorical slots
 * in the dataviz palette, validated against --color-surface.
 */
export const SKILLS = [
  { id: 'pace', name: 'Pace', short: 'Pace', color: 'var(--color-series-1)' },
  { id: 'fluency', name: 'Fluency', short: 'Fluency', color: 'var(--color-series-2)' },
  { id: 'vocal_variety', name: 'Vocal variety', short: 'Variety', color: 'var(--color-series-3)' },
  { id: 'vocabulary', name: 'Vocabulary', short: 'Vocab', color: 'var(--color-series-4)' },
  { id: 'confidence', name: 'Confidence', short: 'Confidence', color: 'var(--color-series-5)' },
  { id: 'structure', name: 'Structure', short: 'Structure', color: 'var(--color-series-6)' },
  { id: 'clarity', name: 'Clarity', short: 'Clarity', color: 'var(--color-series-7)' },
  { id: 'engagement', name: 'Engagement', short: 'Engaging', color: 'var(--color-series-8)' },
];

export const SKILL_BY_ID = Object.fromEntries(SKILLS.map((skill) => [skill.id, skill]));

// Overall sits outside the eight slots as a primary-ink line, so it never needs a ninth hue.
export const OVERALL = { id: 'overall', name: 'Overall', color: 'var(--color-ink)' };

// A single series always takes slot 1.
export const SINGLE_SERIES = 'var(--color-series-1)';

export const AXIS_TICK = { fill: 'var(--color-ink-muted)', fontSize: 12 };
export const GRID_STROKE = 'var(--color-chart-grid)';
export const AXIS_STROKE = 'var(--color-chart-axis)';
export const SURFACE = 'var(--color-surface)';

export const LINE_PROPS = { type: 'linear', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round', isAnimationActive: false };

/** Show every dot on sparse series only. Dense series keep just the end dot, or they turn to noise. */
export function pointDot(color, total) {
  return function PointDot({ cx, cy, index, value, key }) {
    const isLast = index === total - 1;
    if (value === null || value === undefined || cx === undefined || cy === undefined) return <g key={key} />;
    if (total > 14 && !isLast) return <g key={key} />;
    return <circle key={key} cx={cx} cy={cy} r={4} fill={color} stroke={SURFACE} strokeWidth={2} />;
  };
}
