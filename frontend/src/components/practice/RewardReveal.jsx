/**
 * The payoff. Rewards land one at a time so each gets its own beat: score, XP, level-up, streak,
 * badges and quests. With reduced motion everything is simply shown, with no confetti.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import confetti from 'canvas-confetti';
import { ArrowRight, Check, Snowflake, Swords, Trophy, TrendingUp } from 'lucide-react';
import { Button } from '../ui/Button';
import { Logo } from '../ui/Logo';
import { SpotBeam } from '../ui/StageScene';
import { StreakFlame } from '../gamification/Streak';
import { SparksAmount } from '../gamification/Progress';
import { BadgeMedal } from '../gamification/BadgeCard';
import { clock, plural } from '../../lib/format';
import { prefersReducedMotion, useCountUp } from '../../lib/motion';

const CONFETTI_COLORS = ['#FFB84D', '#FFC971', '#5FE0B7', '#F5EFE6', '#F6D27A'];

function burst(options = {}) {
  // disableForReducedMotion makes this a no-op for those users.
  confetti({ particleCount: 90, spread: 75, startVelocity: 38, origin: { y: 0.55 }, colors: CONFETTI_COLORS, disableForReducedMotion: true, zIndex: 60, ...options })?.catch?.(() => {});
}

const STEP = { SCORE: 0, XP: 1, LEVEL: 2, STREAK: 3, EXTRAS: 4, DONE: 5 };
const STEP_DELAY_MS = { [STEP.SCORE]: 1900, [STEP.XP]: 1900, [STEP.LEVEL]: 200, [STEP.STREAK]: 1300, [STEP.EXTRAS]: 1100 };

function LevelUpMoment({ before, after, title, onContinue }) {
  const buttonRef = useRef(null);

  useEffect(() => {
    buttonRef.current?.focus();
    burst({ particleCount: 150, spread: 100, startVelocity: 48 });
    const second = setTimeout(() => {
      burst({ particleCount: 60, angle: 60, spread: 60, origin: { x: 0, y: 0.7 } });
      burst({ particleCount: 60, angle: 120, spread: 60, origin: { x: 1, y: 0.7 } });
    }, 450);
    return () => clearTimeout(second);
  }, []);

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="levelup-title" className="fixed inset-0 z-50 flex flex-col items-center justify-center overflow-hidden bg-stage px-6 text-center">
      <SpotBeam className="animate-beam-open inset-x-0 top-0 mx-auto h-[86vh] w-full max-w-3xl origin-top" intensity={1.5} />
      <div className="relative flex flex-col items-center">
        <p className="kicker animate-rise text-amber-bright">Level up</p>
        <div className="mt-4 flex items-center gap-5 font-display font-bold">
          <span className="animate-rise text-5xl text-ink-muted [animation-delay:150ms]">{before}</span>
          <ArrowRight aria-hidden="true" className="animate-rise size-8 text-ink-muted [animation-delay:250ms]" />
          <span className="animate-pop text-[7.5rem] leading-none text-ink [animation-delay:350ms] sm:text-[10rem]">{after}</span>
        </div>
        <h2 id="levelup-title" className="animate-rise mt-4 text-4xl font-bold [animation-delay:600ms] sm:text-6xl">
          {title}
        </h2>
        <p className="animate-rise mt-3 max-w-sm text-ink-soft [animation-delay:750ms]">You've earned a new title. People who keep showing up get here. You did.</p>
        <Button ref={buttonRef} size="lg" onClick={onContinue} className="animate-rise mt-8 [animation-delay:900ms]">
          Take a bow
        </Button>
      </div>
    </div>
  );
}

function Panel({ children, className = '' }) {
  return <section className={`card animate-rise p-5 text-left ${className}`}>{children}</section>;
}

export function RewardReveal({ result, onContinue }) {
  const { session, rewards } = result;
  const score = session.overall_score ?? 0;
  const [step, setStep] = useState(() => (prefersReducedMotion() ? STEP.DONE : STEP.SCORE));
  const [levelOverlay, setLevelOverlay] = useState(false);
  const displayed = useCountUp(score, { duration: 1500 });
  const xpTotal = useCountUp(rewards.xp_gained, { duration: 1000, start: step >= STEP.XP });
  const continueRef = useRef(null);
  const panelsEndRef = useRef(null);
  const skippedRef = useRef(false);
  const reduced = prefersReducedMotion();

  const advance = useCallback(() => setStep((value) => Math.min(value + 1, STEP.DONE)), []);

  useEffect(() => {
    // Rewards land below the fold on most screens, so bring each new one into view. Not after a
    // skip or with reduced motion, where the score at the top should stay the first thing seen.
    if (!skippedRef.current && !reduced && step > STEP.SCORE) {
      panelsEndRef.current?.scrollIntoView({ block: 'end', behavior: 'smooth' });
    }
    if (step >= STEP.DONE) {
      continueRef.current?.focus({ preventScroll: true });
      return undefined;
    }
    if (step === STEP.LEVEL) {
      if (rewards.leveled_up && !reduced) {
        setLevelOverlay(true);
        return undefined; // Waits for the user: this moment should not rush past.
      }
      advance();
      return undefined;
    }
    const timer = setTimeout(advance, STEP_DELAY_MS[step]);
    return () => clearTimeout(timer);
  }, [advance, reduced, rewards.leveled_up, step]);

  useEffect(() => {
    if (step === STEP.SCORE && (score >= 80 || rewards.personal_best)) {
      const timer = setTimeout(() => burst(), 1400);
      return () => clearTimeout(timer);
    }
    const celebrate = rewards.new_badges?.length || rewards.comeback?.improved || rewards.challenge?.completed;
    if (step === STEP.EXTRAS && celebrate) burst({ particleCount: 70, origin: { y: 0.75 } });
    return undefined;
  }, [rewards.challenge?.completed, rewards.comeback?.improved, rewards.new_badges?.length, rewards.personal_best, score, step]);

  const streak = rewards.streak;
  const quests = rewards.completed_quests ?? [];
  const badges = rewards.new_badges ?? [];
  const comeback = rewards.comeback;
  const challenge = rewards.challenge;

  return (
    <div className="fixed inset-0 z-40 overflow-y-auto bg-stage">
      <SpotBeam className="inset-x-0 top-0 mx-auto h-[420px] w-full max-w-3xl" />
      <div className="relative mx-auto flex min-h-full w-full max-w-xl flex-col px-4 pb-10 pt-3">
        <header className="flex items-center justify-between">
          <Logo />
          {step < STEP.DONE && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                skippedRef.current = true;
                setLevelOverlay(false);
                setStep(STEP.DONE);
              }}
            >
              Skip
            </Button>
          )}
        </header>

        <div aria-live="polite" className="sr-only">
          {`You scored ${score} out of 100. You earned ${rewards.xp_gained} XP and ${rewards.sparks_gained} sparks.`}
          {rewards.leveled_up ? ` Level up! You are now level ${rewards.level_after}, ${rewards.new_title}.` : ''}
          {badges.length ? ` New badges: ${badges.map((badge) => badge.name).join(', ')}.` : ''}
          {comeback?.improved ? ` Comeback! You beat your last take, ${comeback.score_before} to ${comeback.score_after}.` : ''}
          {challenge?.completed ? ' Daily challenge complete.' : ''}
        </div>

        <div className="flex flex-col items-center pb-8 pt-10 text-center">
          <p className="kicker">Your score</p>
          <p className="mt-1 font-display text-[6.5rem] font-bold leading-none tracking-tight sm:text-[8.5rem]">{displayed}</p>
          <p className="text-sm text-ink-soft">out of 100</p>
          {rewards.personal_best && step > STEP.SCORE && (
            <p className="animate-pop mt-3 inline-flex items-center gap-1.5 rounded-full bg-raised px-3 py-1 text-sm font-semibold text-ink">
              <Trophy aria-hidden="true" className="size-4 text-gold" />
              New personal best
            </p>
          )}
        </div>

        <div className="flex flex-col gap-3">
          {step >= STEP.XP && (
            <Panel>
              <div className="flex items-baseline justify-between gap-3">
                <h2 className="text-lg font-bold">XP earned</h2>
                <p className="font-display text-3xl font-bold text-mint">+{xpTotal}</p>
              </div>
              <ul className="mt-3 flex flex-col gap-1.5 text-sm">
                {(rewards.xp_breakdown ?? []).map((line, index) => (
                  <li key={line.label} className="animate-rise flex justify-between gap-3 text-ink-soft" style={{ animationDelay: `${index * 140}ms` }}>
                    <span>{line.label}</span>
                    <span className="font-medium tabular-nums text-ink">+{line.xp}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-3 border-t border-line pt-3 text-sm text-ink-soft">
                You also picked up <SparksAmount amount={rewards.sparks_gained} className="font-semibold text-ink" />
              </p>
            </Panel>
          )}

          {rewards.leveled_up && step > STEP.LEVEL && (
            <Panel className="flex items-center gap-4">
              <span className="flex size-12 shrink-0 items-center justify-center rounded-full border-2 border-mint font-display text-xl font-bold text-mint">{rewards.level_after}</span>
              <div>
                <p className="font-semibold">You reached level {rewards.level_after}</p>
                <p className="text-sm text-ink-soft">{rewards.new_title}</p>
              </div>
            </Panel>
          )}

          {step >= STEP.STREAK && streak && (
            <Panel className="flex items-center gap-4">
              <StreakFlame status="active_today" className="size-12 shrink-0" />
              <div className="min-w-0">
                <p className="font-semibold">
                  {streak.extended ? (streak.current === 1 ? 'Day one of your streak' : `${streak.current}-day streak!`) : `Streak: ${plural(streak.current, 'day')}`}
                </p>
                <p className="text-sm text-ink-soft">
                  {!streak.extended ? 'Today already counted, so this one is pure practice.' : streak.current === 1 ? 'Every long run starts exactly like this.' : 'Another day on the board.'}
                  {streak.freeze_used > 0 && ` ${plural(streak.freeze_used, 'freeze')} kept it alive.`}
                </p>
                {streak.freeze_earned && (
                  <p className="mt-1 flex items-center gap-1.5 text-sm font-medium text-frost">
                    <Snowflake aria-hidden="true" className="size-4" />
                    Milestone! You earned a free streak freeze.
                  </p>
                )}
              </div>
            </Panel>
          )}

          {step >= STEP.EXTRAS && comeback && (
            <Panel className="flex items-center gap-4">
              <span className={`flex size-12 shrink-0 items-center justify-center rounded-full bg-raised ${comeback.improved ? 'text-good' : 'text-ink-muted'}`}>
                <TrendingUp aria-hidden="true" className="size-6" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-semibold">{comeback.improved ? 'Comeback!' : 'Second take'}</p>
                <p className="text-sm text-ink-soft">
                  Score {comeback.score_before} → {comeback.score_after}
                  {comeback.grammar_before !== null && comeback.grammar_after !== null && `, grammar ${comeback.grammar_before} → ${comeback.grammar_after}`}
                </p>
                {!comeback.improved && <p className="text-sm text-ink-muted">Not beaten this time. The bar is still {comeback.score_before}.</p>}
              </div>
              {comeback.xp > 0 && <p className="shrink-0 font-display text-xl font-bold text-mint">+{comeback.xp}</p>}
            </Panel>
          )}

          {step >= STEP.EXTRAS && challenge && (
            <Panel className="flex items-center gap-4">
              <span className={`flex size-12 shrink-0 items-center justify-center rounded-full bg-raised ${challenge.completed ? 'text-good' : 'text-ink-muted'}`}>
                <Swords aria-hidden="true" className="size-6" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-semibold">{challenge.completed ? 'Daily challenge complete' : challenge.reason === 'too_short' ? 'Challenge not quite done' : 'Daily challenge'}</p>
                <p className="text-sm text-ink-soft">
                  {challenge.completed
                    ? 'Same time tomorrow, new topic.'
                    : challenge.reason === 'too_short'
                      ? `Speak for at least ${clock(challenge.min_seconds)} to complete it.`
                      : 'Already done today, so this one was bonus practice.'}
                </p>
              </div>
              {challenge.xp > 0 && <p className="shrink-0 font-display text-xl font-bold text-mint">+{challenge.xp}</p>}
            </Panel>
          )}

          {step >= STEP.EXTRAS && badges.length > 0 && (
            <Panel>
              <h2 className="text-lg font-bold">{badges.length === 1 ? 'New badge' : 'New badges'}</h2>
              <ul className="mt-3 flex flex-col gap-3">
                {badges.map((badge, index) => (
                  <li key={badge.id} className="animate-pop flex items-center gap-3" style={{ animationDelay: `${index * 160}ms` }}>
                    <BadgeMedal badge={{ ...badge, unlocked: true }} />
                    <div className="min-w-0">
                      <p className="font-semibold">{badge.name}</p>
                      <p className="text-sm text-ink-soft">{badge.description}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </Panel>
          )}

          {step >= STEP.EXTRAS && quests.length > 0 && (
            <Panel>
              <h2 className="text-lg font-bold">Quests completed</h2>
              <ul className="mt-3 flex flex-col gap-2">
                {quests.map((quest) => (
                  <li key={quest.id} className="flex items-center gap-2.5 text-sm">
                    <Check aria-hidden="true" strokeWidth={2.75} className="size-4 shrink-0 text-mint" />
                    <span className="min-w-0 flex-1 font-medium">{quest.title}</span>
                    <span className="shrink-0 text-xs text-ink-muted">+{quest.xp} XP</span>
                  </li>
                ))}
              </ul>
            </Panel>
          )}
        </div>

        {/* Sticky, so the way onward is on screen however long the list of rewards gets.
            The fade stops panels scrolling behind it from reading as cut-off text. */}
        {step >= STEP.DONE && (
          <div className="animate-rise sticky bottom-0 z-10 mt-2 flex justify-center bg-linear-to-t from-stage via-stage to-transparent pb-4 pt-8">
            <Button
              ref={continueRef}
              size="lg"
              icon={ArrowRight}
              onClick={() => {
                confetti.reset();
                onContinue();
              }}
              className="w-full sm:w-auto"
            >
              See your scorecard
            </Button>
          </div>
        )}

        {/* Scroll target. Below the button, so following the rewards never leaves it covering a panel. */}
        <div ref={panelsEndRef} />
      </div>

      {levelOverlay && (
        <LevelUpMoment
          before={rewards.level_before}
          after={rewards.level_after}
          title={rewards.new_title}
          onContinue={() => {
            setLevelOverlay(false);
            advance();
          }}
        />
      )}
    </div>
  );
}
