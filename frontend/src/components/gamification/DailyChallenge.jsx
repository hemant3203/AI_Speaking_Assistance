/** Today's challenge: one topic for everyone, taken as a 3-minute sprint or a 5-minute marathon. */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, CircleCheck, Hourglass, Swords, Timer } from 'lucide-react';
import { SparksAmount } from './Progress';
import { clock, plural } from '../../lib/format';

const OPTION_STYLE = {
  180: { name: '3-minute sprint', icon: Timer },
  300: { name: '5-minute marathon', icon: Hourglass },
};

/** Minutes until midnight in the user's timezone, which is when quests and the challenge reset. */
function minutesToMidnight(timeZone) {
  const now = new Date();
  try {
    const parts = new Intl.DateTimeFormat('en-GB', { timeZone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(now);
    const hour = Number(parts.find((part) => part.type === 'hour')?.value);
    const minute = Number(parts.find((part) => part.type === 'minute')?.value);
    if (Number.isFinite(hour) && Number.isFinite(minute)) return 24 * 60 - (hour * 60 + minute);
  } catch {
    // An unknown timezone falls through to the browser's own clock.
  }
  return 24 * 60 - (now.getHours() * 60 + now.getMinutes());
}

function useCountdown(timeZone) {
  const [minutes, setMinutes] = useState(() => minutesToMidnight(timeZone));
  useEffect(() => {
    setMinutes(minutesToMidnight(timeZone));
    const timer = setInterval(() => setMinutes(minutesToMidnight(timeZone)), 30_000);
    return () => clearInterval(timer);
  }, [timeZone]);
  const hours = Math.floor(minutes / 60);
  return hours > 0 ? `${hours}h ${minutes % 60}m` : `${minutes}m`;
}

export function DailyChallengeCard({ challenge, timeZone }) {
  const countdown = useCountdown(timeZone);
  if (!challenge) return null;

  return (
    <section aria-labelledby="challenge-heading" className="card p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="kicker flex items-center gap-1.5">
          <Swords aria-hidden="true" className="size-4" />
          Daily challenge · {challenge.mode_name}
        </p>
        <p className="text-xs text-ink-muted">New topic in {countdown}</p>
      </div>
      <h2 id="challenge-heading" className="mt-2 text-2xl font-bold sm:text-3xl">
        {challenge.topic}
      </h2>
      <p lang="hi" className="mt-1 text-sm text-ink-muted">
        {challenge.topic_hi}
      </p>

      {challenge.completed ? (
        <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl bg-raised p-4">
          <p className="flex items-center gap-2 font-semibold">
            <CircleCheck aria-hidden="true" className="size-5 text-good" />
            Done for today{challenge.score !== null ? `, with a score of ${challenge.score}` : ''}.
          </p>
          {challenge.session_id && (
            <Link to={`/sessions/${encodeURIComponent(challenge.session_id)}`} className="inline-flex min-h-10 items-center gap-1 text-sm text-ink-soft underline underline-offset-2 hover:text-ink">
              See your take
              <ArrowUpRight aria-hidden="true" className="size-4" />
            </Link>
          )}
          <p className="w-full text-sm text-ink-soft">
            {plural(challenge.total_completed, 'challenge')} completed so far. Come back tomorrow for a new topic.
          </p>
        </div>
      ) : (
        <>
          <p className="mt-3 text-sm text-ink-soft">Everyone gets the same topic today. Pick your distance, speak for most of it, and the bonus is yours.</p>
          <ul className="mt-4 grid gap-3 sm:grid-cols-2">
            {challenge.options.map((option) => {
              const style = OPTION_STYLE[option.target_seconds] ?? { name: `${Math.round(option.target_seconds / 60)} minutes`, icon: Timer };
              const Icon = style.icon;
              return (
                <li key={option.target_seconds}>
                  <Link
                    to={`/practice?challenge=${option.target_seconds}`}
                    className="group flex h-full items-center gap-3 rounded-2xl border border-line bg-surface p-4 transition-colors hover:border-line-strong hover:bg-raised"
                  >
                    <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-raised text-ink-soft group-hover:text-ink">
                      <Icon aria-hidden="true" className="size-5" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block font-semibold">{style.name}</span>
                      <span className="block text-sm">
                        <span className="font-semibold text-mint">+{option.xp} XP</span>
                        <span className="text-ink-muted"> · </span>
                        <SparksAmount amount={`+${option.sparks}`} className="text-ink-soft" />
                      </span>
                      <span className="block text-xs text-ink-muted">Speak at least {clock(option.min_seconds)}</span>
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </section>
  );
}
