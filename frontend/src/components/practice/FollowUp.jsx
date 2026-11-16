/**
 * Push-to-talk follow-up with the coach. Holding flushes coach audio immediately, then opens the
 * mic. It works by pointer, Space and Enter, and releasing anywhere ends the question.
 */
import { useEffect, useRef } from 'react';
import { Mic, Volume2 } from 'lucide-react';

export function FollowUp({ coach }) {
  const { state, coachConnected, coachSpeaking, coachTurns, followupActive, mic, startFollowup, endFollowup } = coach;
  const heldRef = useRef(false);
  const available = state === 'feedback' && coachConnected && mic.status === 'on';
  const logRef = useRef(null);

  const press = () => {
    if (heldRef.current || !available) return;
    heldRef.current = true;
    startFollowup();
  };
  const release = () => {
    if (!heldRef.current) return;
    heldRef.current = false;
    endFollowup();
  };

  // A release outside the button, or the window losing focus, must never leave the mic open.
  useEffect(() => {
    window.addEventListener('pointerup', release);
    window.addEventListener('pointercancel', release);
    window.addEventListener('blur', release);
    return () => {
      window.removeEventListener('pointerup', release);
      window.removeEventListener('pointercancel', release);
      window.removeEventListener('blur', release);
    };
  });

  // Scroll the log itself. scrollIntoView could yank the whole page away from the scorecard.
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [coachTurns]);

  const onKey = (event) => {
    if (event.key !== ' ' && event.key !== 'Enter') return;
    event.preventDefault();
    if (event.type === 'keydown' && !event.repeat) press();
    if (event.type === 'keyup') release();
  };

  return (
    <section className="card p-5 sm:p-6">
      <h2 className="text-xl font-bold">Ask your coach</h2>
      <p className="mt-1 text-sm text-ink-soft">{available ? 'Hold the button, ask anything about your speech, then let go. This part is not graded.' : 'The coach has left the stage for this take. Start another one to keep talking.'}</p>

      {coachTurns.length > 0 && (
        <div ref={logRef} className="mt-4 max-h-56 overflow-y-auto rounded-xl bg-raised p-4 text-sm text-ink-soft" tabIndex={0} role="log" aria-label="What your coach said" aria-live="polite">
          {coachTurns.map((turn, index) => (
            <p key={index} className="mb-2 last:mb-0">
              {turn}
            </p>
          ))}
        </div>
      )}

      {available && (
        <div className="mt-4 flex flex-col items-start gap-3 sm:flex-row sm:items-center">
          <button
            type="button"
            aria-pressed={followupActive}
            onPointerDown={(event) => {
              event.preventDefault();
              press();
            }}
            onKeyDown={onKey}
            onKeyUp={onKey}
            onContextMenu={(event) => event.preventDefault()}
            className={`flex min-h-14 w-full touch-none select-none items-center justify-center gap-2.5 rounded-2xl border-2 px-6 font-semibold transition-colors sm:w-auto ${
              followupActive ? 'border-amber bg-amber text-on-amber' : 'border-control text-ink hover:bg-raised'
            }`}
          >
            <Mic aria-hidden="true" className="size-5" />
            {followupActive ? "Listening. Let go when you're done" : 'Hold to ask'}
          </button>
          <p role="status" className="flex items-center gap-2 text-sm text-ink-soft">
            {coachSpeaking && (
              <>
                <Volume2 aria-hidden="true" className="size-4 text-amber motion-safe:animate-pulse" />
                Your coach is talking
              </>
            )}
          </p>
        </div>
      )}
    </section>
  );
}
