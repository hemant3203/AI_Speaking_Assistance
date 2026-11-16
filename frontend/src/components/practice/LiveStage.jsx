/**
 * The stage itself: connecting, the moment before you speak, the speech, and scoring.
 * It covers the whole viewport on purpose. No nav, no stats, just you and the light.
 */
import { useEffect, useRef, useState } from 'react';
import { LoaderCircle, MicOff, Square, Volume2, X } from 'lucide-react';
import { Button } from '../ui/Button';
import { Banner } from '../ui/Banner';
import { Dialog } from '../ui/Dialog';
import { Logo } from '../ui/Logo';
import { SpotBeam } from '../ui/StageScene';
import { LevelMeter, useHearing } from './LevelMeter';
import { clock } from '../../lib/format';

function StageFrame({ topic, demo, onLeave, leaveLabel, children }) {
  return (
    <div className="fixed inset-0 z-40 flex flex-col overflow-y-auto bg-stage">
      <SpotBeam className="inset-x-0 top-0 mx-auto h-[78vh] w-full max-w-4xl" />
      <header className="relative flex items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <Logo />
        {onLeave && (
          <Button variant="ghost" size="sm" icon={X} onClick={onLeave}>
            {leaveLabel}
          </Button>
        )}
      </header>
      {demo && (
        <div className="relative mx-auto w-full max-w-xl px-4">
          <Banner tone="demo" title="Demo mode">
            The coach is simulated, so its replies and voice aren't real AI coaching.
          </Banner>
        </div>
      )}
      <div className="relative mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center gap-6 px-4 pb-8 pt-4 text-center">
        {topic && <p className="max-w-xl text-pretty text-base font-medium text-ink-soft sm:text-lg">{topic}</p>}
        {children}
      </div>
    </div>
  );
}

function BreathingCue({ text = 'Breathe in, and slowly out.' }) {
  return (
    <div className="flex max-w-md items-center gap-3 text-left text-sm text-ink-soft">
      <span aria-hidden="true" className="relative flex size-8 shrink-0 items-center justify-center">
        <span className="absolute inset-0 rounded-full border border-amber/70 motion-safe:animate-breathe" />
        <span className="size-2 rounded-full bg-amber" />
      </span>
      {text}
    </div>
  );
}

/** Timer ring against the target. It completes at the target and the clock carries on counting after. */
function TimerRing({ elapsed, target }) {
  const radius = 92;
  const circumference = 2 * Math.PI * radius;
  const progress = Math.min(1, elapsed / Math.max(1, target));
  const reached = elapsed >= target;
  return (
    <div className="relative size-56 sm:size-72">
      <svg viewBox="0 0 200 200" className="size-full -rotate-90" aria-hidden="true">
        <circle cx="100" cy="100" r={radius} fill="var(--color-stage)" fillOpacity="0.6" stroke="var(--color-overlay)" strokeWidth="7" />
        <circle
          cx="100"
          cy="100"
          r={radius}
          fill="none"
          stroke={reached ? 'var(--color-mint)' : 'var(--color-amber)'}
          strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - progress)}
          className="transition-[stroke-dashoffset] duration-1000 ease-linear"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span role="timer" className="font-display text-6xl font-bold tracking-tight sm:text-7xl">
          {clock(elapsed)}
        </span>
        <span className="mt-1 text-sm text-ink-soft">target {clock(target)}</span>
      </div>
    </div>
  );
}

function speakingCue(elapsed, target, maxSeconds) {
  if (maxSeconds - elapsed <= 30) return "About 30 seconds until we wrap this take up for you.";
  if (elapsed >= target) return "You've hit your target. Finish your thought and wrap up when you're ready.";
  if (elapsed < 20) return 'Keep going. Speeches of 20 seconds or more earn rewards.';
  if (target - elapsed <= 15) return 'Nearly there. Start bringing it home.';
  return 'Take your time. Pauses sound confident.';
}

export function LiveStage({ coach, topic, onLeave }) {
  const { state, config, elapsed, levelRef } = coach;
  const [confirmLeave, setConfirmLeave] = useState(false);
  const actionRef = useRef(null);
  const { silent } = useHearing(levelRef, { active: state === 'speaking' });
  const target = config.targetSeconds ?? 120;

  // Move focus to the one thing to do next, so keyboard users can start and finish without hunting.
  useEffect(() => {
    if (state === 'ready' || state === 'speaking') actionRef.current?.focus();
  }, [state]);

  if (state === 'connecting') {
    return (
      <StageFrame topic={topic} onLeave={onLeave} leaveLabel="Cancel">
        <div role="status" className="flex flex-col items-center gap-4">
          <LoaderCircle aria-hidden="true" className="size-10 animate-spin text-amber" />
          <h1 className="text-3xl font-bold sm:text-4xl">Warming up the lights</h1>
          <p className="text-ink-soft">Connecting you to your coach. This usually takes a few seconds.</p>
        </div>
      </StageFrame>
    );
  }

  if (state === 'ready') {
    return (
      <StageFrame topic={topic} demo={config.demo} onLeave={onLeave} leaveLabel="Leave">
        <h1 className="text-4xl font-bold sm:text-6xl">The stage is yours</h1>
        <p className="max-w-md text-ink-soft">
          Your coach will listen quietly and reply when you finish. Aim for {clock(target)}. There's no audience, so it's fine to stumble.
        </p>
        <BreathingCue />
        <Button ref={actionRef} size="lg" onClick={coach.startSpeech} className="w-full max-w-xs" autoFocus>
          Start speaking
        </Button>
        <p aria-live="polite" className="sr-only">
          Connected. Your coach is ready. Press Start speaking when you are.
        </p>
      </StageFrame>
    );
  }

  return (
    <StageFrame topic={topic} demo={config.demo} onLeave={() => setConfirmLeave(true)} leaveLabel="Leave">
      <TimerRing elapsed={elapsed} target={target} />
      <LevelMeter levelRef={levelRef} className="h-16 w-full max-w-md" label="Your voice level" />
      {silent ? (
        <p role="status" className="flex items-center gap-2 text-sm font-medium text-warning">
          <MicOff aria-hidden="true" className="size-4" />
          We can't hear you. Is your mic muted?
        </p>
      ) : (
        <BreathingCue text={speakingCue(elapsed, target, config.maxSpeechSeconds)} />
      )}
      <Button ref={actionRef} size="lg" icon={Square} onClick={coach.finishSpeech} className="w-full max-w-xs">
        Finish
      </Button>
      <p aria-live="polite" className="sr-only">
        {elapsed >= target ? 'You have reached your target time.' : elapsed === 20 ? 'Twenty seconds. You now qualify for rewards.' : ''}
      </p>

      <Dialog open={confirmLeave} onClose={() => setConfirmLeave(false)} title="Leave without scoring?">
        <p className="text-sm text-ink-soft">This take won't be scored, and it won't count towards your streak. If you'd like credit for it, press Finish instead.</p>
        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <Button variant="secondary" onClick={() => setConfirmLeave(false)}>
            Keep speaking
          </Button>
          <Button variant="danger" onClick={onLeave}>
            Leave
          </Button>
        </div>
      </Dialog>
    </StageFrame>
  );
}

const ANALYSIS_LINES = ['Listening back to your speech', 'Counting your words, pauses and fillers', 'Weighing up structure and clarity', 'Tallying your rewards'];

export function AnalyzingStage({ coach, topic }) {
  const [line, setLine] = useState(0);
  const [slow, setSlow] = useState(false);
  const lastTurn = coach.coachTurns[coach.coachTurns.length - 1];

  useEffect(() => {
    const cycle = setInterval(() => setLine((value) => Math.min(value + 1, ANALYSIS_LINES.length - 1)), 3500);
    const slowTimer = setTimeout(() => setSlow(true), 25000);
    return () => {
      clearInterval(cycle);
      clearTimeout(slowTimer);
    };
  }, []);

  return (
    <StageFrame topic={topic} demo={coach.config.demo}>
      <div role="status" className="flex flex-col items-center gap-4">
        <LoaderCircle aria-hidden="true" className="size-10 animate-spin text-amber" />
        <h1 className="text-3xl font-bold sm:text-5xl">Nicely done. Take a breath.</h1>
        <p className="text-ink-soft">{ANALYSIS_LINES[line]}…</p>
        {slow && <p className="text-sm text-ink-muted">This is taking longer than usual, which is normal for a long speech. We'll keep trying for a few minutes, and your speech is safe.</p>}
      </div>
      {coach.notice && <Banner tone="info">{coach.notice}</Banner>}
      {(coach.coachSpeaking || lastTurn) && (
        <div className="card w-full max-w-xl p-4 text-left">
          <p className="kicker flex items-center gap-2">
            <Volume2 aria-hidden="true" className={`size-4 ${coach.coachSpeaking ? 'text-amber motion-safe:animate-pulse' : ''}`} />
            {coach.coachSpeaking ? 'Your coach is talking' : 'Your coach said'}
          </p>
          {lastTurn && <p className="mt-2 text-sm text-ink-soft">{lastTurn}</p>}
        </div>
      )}
    </StageFrame>
  );
}
