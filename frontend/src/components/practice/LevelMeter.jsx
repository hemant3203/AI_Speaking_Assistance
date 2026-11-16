/**
 * Live voice meter drawn on a canvas. It reads a ref, not React state, so 30 updates a second never
 * re-render the page. With reduced motion it is a plain bar instead of a scrolling trace.
 */
import { useEffect, useRef, useState } from 'react';
import { prefersReducedMotion } from '../../lib/motion';

const BAR_WIDTH = 4;
const BAR_GAP = 3;
const SAMPLE_MS = 50;

// Speech RMS sits around 0.02 to 0.2. The square root spreads that across the meter's height.
const normalize = (rms) => Math.min(1, Math.sqrt(rms * 6));

export function LevelMeter({ levelRef, className = 'h-20 w-full', label = 'Microphone level' }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas.getContext('2d');
    const color = getComputedStyle(document.documentElement).getPropertyValue('--color-amber').trim() || '#ffb84d';
    const reduced = prefersReducedMotion();
    let history = [];
    let frame;
    let lastSample = 0;
    let width = 0;
    let height = 0;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const ratio = window.devicePixelRatio || 1;
      width = rect.width;
      height = rect.height;
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);

    const draw = (now) => {
      frame = requestAnimationFrame(draw);
      if (now - lastSample < SAMPLE_MS) return;
      lastSample = now;
      const level = normalize(levelRef.current ?? 0);
      context.clearRect(0, 0, width, height);

      if (reduced) {
        context.fillStyle = 'rgba(245, 239, 230, 0.12)';
        context.fillRect(0, height / 2 - 4, width, 8);
        context.fillStyle = color;
        context.fillRect(0, height / 2 - 4, width * level, 8);
        return;
      }

      const barCount = Math.max(8, Math.floor(width / (BAR_WIDTH + BAR_GAP)));
      history.push(level);
      if (history.length > barCount) history = history.slice(-barCount);

      // Newest bar on the right. Older ones fade, like a trail behind the voice.
      history.forEach((value, index) => {
        const age = history.length - 1 - index;
        const barHeight = Math.max(3, value * height);
        const x = width - (age + 1) * (BAR_WIDTH + BAR_GAP);
        context.globalAlpha = Math.max(0.16, 1 - age / barCount);
        context.fillStyle = color;
        context.beginPath();
        context.roundRect(x, (height - barHeight) / 2, BAR_WIDTH, barHeight, 2);
        context.fill();
      });
      context.globalAlpha = 1;
    };
    frame = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [levelRef]);

  return <canvas ref={canvasRef} role="img" aria-label={label} className={className} />;
}

/**
 * Turns the raw level into plain facts for the UI: whether the mic has heard anything, and whether
 * it has gone quiet for a while. Quiet only matters for a long stretch, because pauses are normal.
 */
export function useHearing(levelRef, { active = true, silentAfterMs = 8000, threshold = 0.012 } = {}) {
  const [hearing, setHearing] = useState({ heard: false, silent: false });

  useEffect(() => {
    if (!active) return undefined;
    let lastLoud = performance.now();
    let heard = false;
    const timer = setInterval(() => {
      const now = performance.now();
      if ((levelRef.current ?? 0) > threshold) {
        lastLoud = now;
        heard = true;
      }
      const silent = now - lastLoud > silentAfterMs;
      setHearing((prev) => (prev.heard === heard && prev.silent === silent ? prev : { heard, silent }));
    }, 50); // Fast enough to catch a single short word. State only changes when the facts do.
    return () => clearInterval(timer);
  }, [active, levelRef, silentAfterMs, threshold]);

  return hearing;
}
