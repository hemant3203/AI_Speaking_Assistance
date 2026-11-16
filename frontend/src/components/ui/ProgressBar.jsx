/** Horizontal progress in the mint progress color. The track is a step of the same ink, per the meter rule. */
export function ProgressBar({ value, max = 100, label, className = '', tone = 'mint', height = 'h-2' }) {
  const percent = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  const fill = tone === 'mint' ? 'bg-mint' : tone === 'muted' ? 'bg-ink-muted' : 'bg-amber';
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={Math.round(value)}
      className={`w-full overflow-hidden rounded-full bg-overlay ${height} ${className}`}
    >
      <div className={`h-full rounded-full transition-[width] duration-700 ease-out ${fill}`} style={{ width: `${percent}%` }} />
    </div>
  );
}
