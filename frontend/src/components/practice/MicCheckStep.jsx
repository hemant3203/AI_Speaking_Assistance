/** Second step: prove the mic works before spending any of the user's daily stage time. */
import { ArrowLeft, CircleCheck, Ear, Mic, MicOff } from 'lucide-react';
import { Button } from '../ui/Button';
import { Banner } from '../ui/Banner';
import { LevelMeter, useHearing } from './LevelMeter';

const MIC_HELP = {
  denied: {
    title: 'Your browser is blocking the microphone',
    body: 'Click the lock or microphone icon next to the address bar, set Microphone to Allow, then try again. You may need to reload the page.',
  },
  not_found: {
    title: "We can't find a microphone",
    body: 'Plug in a headset or check that your mic is switched on in your system sound settings, then try again.',
  },
  busy: {
    title: 'Another app is using your microphone',
    body: 'Close anything else that might be holding it, such as Zoom, Meet or Teams, then try again.',
  },
  unsupported: {
    title: "This browser can't use the microphone here",
    body: 'Spotlight needs a recent version of Chrome, Edge, Firefox or Safari, opened over https or on localhost.',
  },
  lost: {
    title: 'Your microphone disconnected',
    body: 'Check that it is still plugged in, then turn it back on.',
  },
  unknown: {
    title: "We couldn't start your microphone",
    body: 'Check your browser and system sound settings, then try again.',
  },
};

export function MicCheckStep({ coach, topic, onBack, onConnect, busy, createError }) {
  const { status, code } = coach.mic;
  const on = status === 'on';
  const { heard } = useHearing(coach.levelRef, { active: on });
  const help = status === 'error' ? MIC_HELP[code] ?? MIC_HELP.unknown : null;

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <div className="card p-5 sm:p-8">
        <p className="kicker">Your topic</p>
        <p className="mt-1 text-lg font-semibold">{topic}</p>

        <div className="mt-6 border-t border-line pt-6">
          <h2 className="text-2xl font-bold">{on ? 'Say something out loud' : 'Quick mic check'}</h2>
          <p className="mt-2 text-ink-soft">
            {on
              ? 'Say a sentence or two aloud. The bars should move as you speak.'
              : "We'll ask your browser for the microphone. Speech is only sent while you're on stage, and it isn't stored on our servers."}
          </p>

          {help && (
            <Banner tone="danger" title={help.title} className="mt-4">
              {help.body}
            </Banner>
          )}

          {status === 'requesting' && (
            <p role="status" className="mt-4 flex items-center gap-2 text-sm text-ink-soft">
              <Mic aria-hidden="true" className="size-4 motion-safe:animate-pulse" />
              Look for your browser's permission prompt, usually near the address bar.
            </p>
          )}

          {on && (
            <div className="mt-5 rounded-xl border border-line bg-stage p-4">
              <LevelMeter levelRef={coach.levelRef} className="h-20 w-full" label="Live microphone level" />
              <p role="status" className={`mt-3 flex items-center gap-2 text-sm font-medium ${heard ? 'text-good' : 'text-ink-soft'}`}>
                {heard ? <CircleCheck aria-hidden="true" className="size-4" /> : <Ear aria-hidden="true" className="size-4" />}
                {heard ? 'We can hear you. Sounding good.' : 'Listening. Nothing heard yet.'}
              </p>
            </div>
          )}

          {!on && (
            <Button
              size="lg"
              icon={status === 'error' ? MicOff : Mic}
              onClick={coach.startMic}
              loading={status === 'requesting'}
              className="mt-6 w-full sm:w-auto"
            >
              {status === 'error' ? 'Try the mic again' : 'Turn on my mic'}
            </Button>
          )}

          {on && (
            <Button size="lg" onClick={onConnect} loading={busy} className="mt-6 w-full sm:w-auto">
              {heard ? "I'm ready, take me to the stage" : 'Continue to the stage'}
            </Button>
          )}

          {createError && (
            <Banner tone="danger" title="We couldn't set up your session" className="mt-4">
              {createError.message}
            </Banner>
          )}
        </div>
      </div>
      <Button variant="ghost" icon={ArrowLeft} onClick={onBack} className="self-start">
        Back to setup
      </Button>
    </div>
  );
}
