/** A badge, unlocked or locked with progress. Tier is written out as well as shown in color. */
import { Lock } from 'lucide-react';
import { DynamicIcon } from '../ui/DynamicIcon';
import { ProgressBar } from '../ui/ProgressBar';
import { dateTime } from '../../lib/format';

const TIER = {
  bronze: { ring: 'border-bronze text-bronze', label: 'Bronze' },
  silver: { ring: 'border-silver text-silver', label: 'Silver' },
  gold: { ring: 'border-gold text-gold', label: 'Gold' },
};

export function BadgeMedal({ badge, size = 'size-14', iconSize = 'size-6' }) {
  const tier = TIER[badge.tier] ?? TIER.bronze;
  return (
    <span className={`relative flex shrink-0 items-center justify-center rounded-full border-2 ${size} ${badge.unlocked ? `${tier.ring} bg-raised` : 'border-line-strong bg-stage text-ink-muted'}`}>
      <DynamicIcon name={badge.icon} className={iconSize} />
      {!badge.unlocked && (
        <span className="absolute -bottom-1 -right-1 flex size-5 items-center justify-center rounded-full bg-overlay text-ink-soft">
          <Lock aria-hidden="true" className="size-3" />
        </span>
      )}
    </span>
  );
}

export function BadgeCard({ badge }) {
  const tier = TIER[badge.tier] ?? TIER.bronze;
  return (
    <li className="card flex gap-4 p-4">
      <BadgeMedal badge={badge} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-x-2">
          <h4 className="font-sans text-[0.9375rem] font-semibold tracking-normal">{badge.name}</h4>
          <span className="text-xs font-medium text-ink-muted">{tier.label}</span>
        </div>
        <p className="mt-0.5 text-sm text-ink-soft">{badge.description}</p>
        {badge.unlocked ? (
          <p className="mt-2 text-xs font-medium text-ink-muted">
            Earned{badge.unlocked_at ? ` ${dateTime(badge.unlocked_at)}` : ''}
            <span className="sr-only"> (unlocked)</span>
          </p>
        ) : (
          <div className="mt-2 flex items-center gap-2">
            <ProgressBar value={badge.progress} max={badge.target} label={`${badge.name} progress`} height="h-1.5" />
            <span className="shrink-0 text-xs tabular-nums text-ink-muted">
              {badge.progress}/{badge.target}
            </span>
          </div>
        )}
      </div>
    </li>
  );
}
