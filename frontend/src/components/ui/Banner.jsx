/** Inline message. Tone always comes with an icon, so meaning never rests on color alone. */
import { CircleAlert, FlaskConical, Info, TriangleAlert } from 'lucide-react';

const TONES = {
  info: { icon: Info, border: 'border-line-strong', iconColor: 'text-ink-soft' },
  warning: { icon: TriangleAlert, border: 'border-warning/50', iconColor: 'text-warning' },
  danger: { icon: CircleAlert, border: 'border-danger/60', iconColor: 'text-danger' },
  demo: { icon: FlaskConical, border: 'border-frost/50', iconColor: 'text-frost' },
};

export function Banner({ tone = 'info', title, children, action, className = '' }) {
  const { icon: Icon, border, iconColor } = TONES[tone];
  return (
    <div role={tone === 'danger' ? 'alert' : 'status'} className={`flex gap-3 rounded-xl border bg-raised px-4 py-3 text-sm ${border} ${className}`}>
      <Icon aria-hidden="true" className={`mt-0.5 size-5 shrink-0 ${iconColor}`} />
      <div className="min-w-0 flex-1">
        {title && <p className="font-semibold text-ink">{title}</p>}
        {children && <div className="text-ink-soft">{children}</div>}
        {action && <div className="mt-2">{action}</div>}
      </div>
    </div>
  );
}
