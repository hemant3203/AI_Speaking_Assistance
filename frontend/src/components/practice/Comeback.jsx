/**
 * The improvement loop: see your slips, say it again, and earn a comeback bonus for beating your
 * own take. Also how a take did as the daily challenge.
 */
import { ArrowRight, CircleCheck, RotateCcw, Swords, TrendingUp } from 'lucide-react';
import { Button } from '../ui/Button';
import { SparksAmount } from '../gamification/Progress';
import { clock, signed } from '../../lib/format';

// Mirrors backend/app/services/gamification/comebacks.py, for the copy only. The server decides the payout.
const XP_PER_SCORE_POINT = 3;
const XP_PER_GRAMMAR_POINT = 2;
const MAX_BONUS_XP = 75;

/** An invitation to beat this take. `onRetake` replaces the link on the practice page. */
export function RetakeCard({ session, onRetake, variant = 'primary' }) {
  const grammar = session.feedback?.grammar;
  const slips = grammar?.issues?.length ?? 0;
  return (
    <section aria-labelledby="retake-heading" className="card p-5 sm:p-6">
      <p className="kicker flex items-center gap-1.5">
        <RotateCcw aria-hidden="true" className="size-4" />
        Second take
      </p>
      <h2 id="retake-heading" className="mt-1 text-2xl font-bold">
        Say it again and beat {session.overall_score}
      </h2>
      <p className="mt-2 max-w-2xl text-ink-soft">
        {slips > 0
          ? `Read your ${slips === 1 ? 'fix' : `${slips} fixes`} out loud once, then give the same speech again. Your coach will listen for them.`
          : 'Give the same speech again with your coach’s notes in mind.'}{' '}
        Beat this take to earn a comeback bonus.
      </p>
      <ul className="mt-4 flex flex-wrap gap-2 text-sm">
        <li className="rounded-lg bg-raised px-3 py-1.5">
          <span className="font-semibold text-mint">+{XP_PER_SCORE_POINT} XP</span> for every point above {session.overall_score}
        </li>
        {grammar && (
          <li className="rounded-lg bg-raised px-3 py-1.5">
            <span className="font-semibold text-mint">+{XP_PER_GRAMMAR_POINT} XP</span> for every grammar point above {grammar.score}
          </li>
        )}
        <li className="rounded-lg bg-raised px-3 py-1.5 text-ink-soft">Up to +{MAX_BONUS_XP} XP and 10 sparks</li>
      </ul>
      <Button
        variant={variant}
        icon={RotateCcw}
        className="mt-5 w-full sm:w-auto"
        {...(onRetake ? { onClick: onRetake } : { to: `/practice?retry=${encodeURIComponent(session.id)}` })}
      >
        Retake this speech
      </Button>
    </section>
  );
}

function Change({ label, before, after }) {
  if (before === null || before === undefined || after === null || after === undefined) return null;
  const delta = after - before;
  return (
    <div className="rounded-xl bg-raised px-3.5 py-2.5">
      <dt className="text-xs text-ink-soft">{label}</dt>
      <dd className="mt-0.5 flex items-baseline gap-2 font-display text-xl font-bold">
        <span className="text-ink-muted">{before}</span>
        <ArrowRight aria-hidden="true" className="size-4 self-center text-ink-muted" />
        <span>{after}</span>
        <span className={`font-sans text-sm font-semibold ${delta > 0 ? 'text-good' : 'text-ink-muted'}`}>({signed(delta)})</span>
      </dd>
    </div>
  );
}

const COMEBACK_NOTES = {
  not_improved: (comeback) => `Not beaten this time. The bar is still ${comeback.score_before}${comeback.grammar_before !== null ? `, or ${comeback.grammar_before} for grammar` : ''}. One more go?`,
  already_claimed: () => 'You beat it, but that take’s comeback bonus was already claimed. Beat this take next for another one.',
  daily_limit: () => 'You beat it! You’ve had today’s comeback bonuses, so this win is for the glory. More tomorrow.',
};

/** How a second take compared with the take it set out to beat. */
export function ComebackResult({ comeback }) {
  if (!comeback) return null;
  const paid = comeback.xp > 0;
  return (
    <section aria-labelledby="comeback-heading" className="card p-5 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="comeback-heading" className="flex items-center gap-2 text-xl font-bold">
          <TrendingUp aria-hidden="true" className={`size-5 ${comeback.improved ? 'text-good' : 'text-ink-soft'}`} />
          {comeback.improved ? 'Comeback!' : 'Second take'}
        </h2>
        {paid && (
          <p className="text-sm font-semibold">
            <span className="text-mint">+{comeback.xp} XP</span> · <SparksAmount amount={`+${comeback.sparks}`} />
          </p>
        )}
      </div>
      <dl className="mt-3 grid gap-3 sm:grid-cols-2">
        <Change label="Overall score" before={comeback.score_before} after={comeback.score_after} />
        <Change label="Grammar" before={comeback.grammar_before} after={comeback.grammar_after} />
      </dl>
      {comeback.slips_before !== null && comeback.slips_after !== null && (
        <p className="mt-3 text-sm text-ink-soft">
          Grammar slips: {comeback.slips_before} last time, {comeback.slips_after} this time.
        </p>
      )}
      {!paid && COMEBACK_NOTES[comeback.reason] && <p className="mt-3 text-sm text-ink-soft">{COMEBACK_NOTES[comeback.reason](comeback)}</p>}
    </section>
  );
}

/** How a take did as the daily challenge. */
export function ChallengeResult({ challenge }) {
  if (!challenge) return null;
  const minutes = Math.round(challenge.target_seconds / 60);
  let body;
  if (challenge.completed) {
    body = (
      <p className="mt-1 text-sm text-ink-soft">
        You spoke for {clock(challenge.spoken_seconds)} and earned <span className="font-semibold text-mint">+{challenge.xp} XP</span> and{' '}
        <SparksAmount amount={challenge.sparks} className="font-semibold text-ink" />. A new topic arrives tomorrow.
      </p>
    );
  } else if (challenge.reason === 'too_short') {
    body = (
      <p className="mt-1 text-sm text-ink-soft">
        You spoke for {clock(challenge.spoken_seconds)}. The {minutes}-minute challenge needs at least {clock(challenge.min_seconds)}. Retake it to claim today’s bonus.
      </p>
    );
  } else {
    body = <p className="mt-1 text-sm text-ink-soft">You already completed today’s challenge, so this take was bonus practice.</p>;
  }
  return (
    <section className="card flex gap-3 p-5 sm:p-6">
      {challenge.completed ? (
        <CircleCheck aria-hidden="true" className="mt-0.5 size-6 shrink-0 text-good" />
      ) : (
        <Swords aria-hidden="true" className="mt-0.5 size-6 shrink-0 text-ink-soft" />
      )}
      <div className="min-w-0">
        <h2 className="font-sans text-lg font-semibold tracking-normal">
          {challenge.completed ? 'Daily challenge complete' : challenge.reason === 'too_short' ? 'Almost there' : 'Daily challenge'}
        </h2>
        {body}
      </div>
    </section>
  );
}
