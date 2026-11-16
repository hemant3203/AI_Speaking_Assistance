/** Level and XP, sparks, and daily quests. Mint carries XP and progress throughout. */
import { Check, Sparkle } from 'lucide-react';
import { ProgressBar } from '../ui/ProgressBar';
import { DynamicIcon } from '../ui/DynamicIcon';

export function SparksAmount({ amount, className = '' }) {
  return (
    <span className={`inline-flex items-center gap-1 ${className}`}>
      <Sparkle aria-hidden="true" className="size-[1em] text-spark" />
      {amount}
      <span className="sr-only"> sparks</span>
    </span>
  );
}

export function LevelBlock({ profile }) {
  const remaining = Math.max(0, profile.xp_for_next_level - profile.xp_into_level);
  return (
    <div>
      <div className="flex items-end justify-between gap-4">
        <div className="min-w-0">
          <p className="kicker">Level {profile.level}</p>
          <p className="mt-1 font-display text-2xl font-bold sm:text-3xl">{profile.level_title}</p>
        </div>
        <span className="flex size-14 shrink-0 items-center justify-center rounded-full border-2 border-mint font-display text-2xl font-bold text-mint">
          {profile.level}
        </span>
      </div>
      <ProgressBar
        value={profile.xp_into_level}
        max={profile.xp_for_next_level}
        label={`${profile.xp_into_level} of ${profile.xp_for_next_level} XP towards level ${profile.level + 1}`}
        height="h-2.5"
        className="mt-4"
      />
      <p className="mt-2 text-sm text-ink-soft">
        <span className="font-semibold text-ink">{remaining.toLocaleString()} XP</span> to level {profile.level + 1}
      </p>
    </div>
  );
}

export function QuestRow({ quest }) {
  return (
    <li className="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
      <span className={`mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-xl ${quest.completed ? 'bg-mint-deep text-mint' : 'bg-raised text-ink-soft'}`}>
        {quest.completed ? <Check aria-hidden="true" strokeWidth={2.75} className="size-5" /> : <DynamicIcon name={quest.icon} className="size-5" />}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3">
          <p className="font-semibold">{quest.title}</p>
          <p className="text-xs font-medium text-ink-muted">
            +{quest.xp} XP · <SparksAmount amount={`+${quest.sparks}`} />
          </p>
        </div>
        <p className="text-sm text-ink-soft">{quest.description}</p>
        {quest.completed ? (
          <p className="mt-1 text-xs font-semibold text-mint">Done</p>
        ) : (
          <div className="mt-2 flex items-center gap-2">
            <ProgressBar value={quest.progress} max={quest.target} label={`${quest.title} progress`} height="h-1.5" />
            <span className="shrink-0 text-xs tabular-nums text-ink-muted">
              {quest.progress}/{quest.target}
            </span>
          </div>
        )}
      </div>
    </li>
  );
}
