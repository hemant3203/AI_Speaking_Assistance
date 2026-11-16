/** Motion helpers: every animated moment checks this so reduced-motion users get the end state at once. */
import { useEffect, useState } from 'react';

export function prefersReducedMotion() {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
}

/** Animate a number from 0 to target with an ease-out. Returns the target straight away if motion is reduced. */
export function useCountUp(target, { duration = 1300, start = true } = {}) {
  const [value, setValue] = useState(() => (prefersReducedMotion() ? target : 0));

  useEffect(() => {
    if (!start) return undefined;
    if (prefersReducedMotion()) {
      setValue(target);
      return undefined;
    }
    let frame;
    const began = performance.now();
    const tick = (now) => {
      const progress = Math.min(1, (now - began) / duration);
      setValue(Math.round(target * (1 - (1 - progress) ** 3)));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, duration, start]);

  return value;
}
