/**
 * Headline number with a delta. Delta color means direction times whether that direction is good,
 * and always comes with an icon and words. Pace has no good direction, so it stays neutral.
 */
import { ArrowDown, ArrowUp, Minus } from 'lucide-react';
import { signed } from '../../lib/format';

export function Delta({ value, goodWhen = 'up', digits = 0, suffix = '', periodLabel }) {
  if (value === null || value === undefined) {
    return <p className="mt-1 text-xs text-ink-muted">No earlier period yet</p>;
  }
  const flat = Number(value) === 0;
  const Icon = flat ? Minus : value > 0 ? ArrowUp : ArrowDown;
  let tone = 'text-ink-soft';
  if (!flat && goodWhen !== 'neutral') {
    const good = goodWhen === 'up' ? value > 0 : value < 0;
    tone = good ? 'text-good' : 'text-serious';
  }
  return (
    <p className={`mt-1 flex items-center gap-1 text-xs font-medium ${tone}`}>
      <Icon aria-hidden="true" className="size-3.5 shrink-0" />
      <span>
        {flat ? 'No change' : `${signed(value, digits)}${suffix}`}
        {periodLabel && <span className="font-normal text-ink-muted"> vs {periodLabel}</span>}
      </span>
    </p>
  );
}

export function StatTile({ label, value, children }) {
  return (
    <div className="card min-w-0 p-4">
      <p className="text-sm text-ink-soft">{label}</p>
      <p className="mt-1 font-display text-3xl font-bold leading-none tracking-tight">{value}</p>
      {children}
    </div>
  );
}
