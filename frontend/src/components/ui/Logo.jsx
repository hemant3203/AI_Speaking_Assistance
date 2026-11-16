/** Wordmark: a lamp throwing a small pool of light. */
export function LogoMark({ className = 'size-7' }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <path d="M12.5 5h7l6.5 19H6z" fill="var(--color-amber)" opacity=".28" />
      <ellipse cx="16" cy="24.5" rx="10.5" ry="3.3" fill="var(--color-amber)" />
      <rect x="11.5" y="3" width="9" height="4" rx="1.6" fill="var(--color-amber)" />
    </svg>
  );
}

export function Logo({ className = '' }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <LogoMark />
      <span className="font-display text-xl font-bold tracking-tight text-ink">Spotlight</span>
    </span>
  );
}
