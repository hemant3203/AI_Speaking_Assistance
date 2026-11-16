/** The streak flame and the last-7-days row. Coral appears here and nowhere else in the UI. */
import { Check, Minus, Snowflake } from 'lucide-react';
import { useId } from 'react';
import { weekdayLetter, weekdayLong } from '../../lib/format';

export function StreakFlame({ status = 'active_today', className = 'size-20', animated = true }) {
  const id = useId().replace(/[^a-zA-Z0-9]/g, '');
  const unlit = status === 'none';
  return (
    <svg viewBox="0 0 64 72" aria-hidden="true" className={`${className} origin-bottom ${animated && !unlit ? 'motion-safe:animate-flicker' : ''}`}>
      <defs>
        <linearGradient id={`outer${id}`} x1="0" y1="1" x2="0" y2="0">
          <stop offset="0" stopColor={unlit ? '#4B4439' : '#FF7A45'} />
          <stop offset="1" stopColor={unlit ? '#38322B' : '#FF5A2B'} />
        </linearGradient>
        <linearGradient id={`inner${id}`} x1="0" y1="1" x2="0" y2="0">
          <stop offset="0" stopColor={unlit ? '#5A5245' : '#FFD9A0'} />
          <stop offset="1" stopColor={unlit ? '#4B4439' : '#FF9E5E'} />
        </linearGradient>
      </defs>
      <path
        d="M34 2c3 11-3 16-9 22C19 30 12 37 12 47c0 13 9 23 21 23s21-10 21-23c0-9-4-16-8-21-1 5-3 8-7 9 2-12-1-25-5-33Z"
        fill={`url(#outer${id})`}
      />
      <path d="M33 34c1 6-2 9-5 12-3 3-5 6-5 11 0 7 4 12 10 12s10-5 10-12c0-4-2-8-4-10-1 2-2 4-4 4 1-6 0-12-2-17Z" fill={`url(#inner${id})`} />
    </svg>
  );
}

const DAY_STATES = {
  practiced: { label: 'practised', circle: 'bg-flame text-[#2A0E03]', icon: Check },
  frozen: { label: 'covered by a streak freeze', circle: 'border border-frost/70 bg-raised text-frost', icon: Snowflake },
  missed: { label: 'missed', circle: 'border border-line-strong text-ink-muted', icon: Minus },
  today_pending: { label: 'today, not practised yet', circle: 'border-2 border-amber text-amber motion-safe:animate-pulse-ring', icon: null },
};

export function WeekRow({ week = [] }) {
  return (
    <ol aria-label="Last 7 days" className="flex justify-between gap-1 sm:gap-2">
      {week.map((day) => {
        const config = DAY_STATES[day.state] ?? DAY_STATES.missed;
        const Icon = config.icon;
        return (
          <li key={day.date} className="flex flex-col items-center gap-1.5">
            <span className={`flex size-9 items-center justify-center rounded-full ${config.circle}`} title={`${weekdayLong(day.date)}: ${config.label}`}>
              {Icon ? <Icon aria-hidden="true" strokeWidth={2.75} className="size-4" /> : <span aria-hidden="true" className="size-1.5 rounded-full bg-amber" />}
            </span>
            <span aria-hidden="true" className="text-xs font-medium text-ink-muted">
              {weekdayLetter(day.date)}
            </span>
            <span className="sr-only">
              {weekdayLong(day.date)}: {config.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/** Words for each streak state. at_risk creates gentle urgency without scolding. */
export function streakCopy(streak, totalSessions) {
  const n = streak.current;
  if (totalSessions === 0) {
    return { headline: 'Your first minute on stage is waiting', detail: 'Pick a topic, talk for a minute, and hear what your coach noticed. No audience, no judgement.' };
  }
  if (streak.status === 'at_risk') {
    const freeze = streak.freezes > 0 ? ` You have ${streak.freezes === 1 ? 'a streak freeze' : `${streak.freezes} streak freezes`} saved, but a short session is better.` : '';
    return {
      headline: n > 0 ? `Practise today to keep your ${n}-day streak` : 'Practise today to keep your streak going',
      detail: `One short session is all it takes.${freeze}`,
    };
  }
  if (streak.status === 'active_today') {
    const toGo = streak.next_milestone ? streak.next_milestone - n : 0;
    return {
      headline: n === 1 ? "You showed up today. That's day one." : `You showed up today. That's ${n} days running.`,
      detail: toGo > 0 ? `${toGo} more ${toGo === 1 ? 'day' : 'days'} until your ${streak.next_milestone}-day milestone. Fancy another take while you're warm?` : "Fancy another take while you're warm?",
    };
  }
  return {
    headline: 'A new streak starts with one session',
    detail: streak.longest > 0 ? `Your best run so far is ${streak.longest} days. Today can be day one of the next.` : 'Today can be day one.',
  };
}
