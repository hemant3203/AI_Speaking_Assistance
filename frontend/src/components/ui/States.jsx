/** The three non-happy views every data screen needs: loading, empty, and error with retry. */
import { CircleAlert, RotateCw } from 'lucide-react';
import { Button } from './Button';
import { LogoMark } from './Logo';

export function Skeleton({ className = '' }) {
  return <div aria-hidden="true" className={`skeleton ${className}`} />;
}

export function PageSkeleton() {
  return (
    <div role="status" aria-label="Loading" className="flex flex-col gap-5">
      <Skeleton className="h-10 w-64 max-w-full" />
      <Skeleton className="h-56 w-full rounded-[var(--radius-card)]" />
      <div className="grid gap-5 md:grid-cols-2">
        <Skeleton className="h-48 rounded-[var(--radius-card)]" />
        <Skeleton className="h-48 rounded-[var(--radius-card)]" />
      </div>
    </div>
  );
}

export function FullPageLoader() {
  return (
    <div role="status" aria-label="Loading Spotlight" className="flex min-h-dvh items-center justify-center">
      <LogoMark className="size-12 motion-safe:animate-pulse" />
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children, action, className = '' }) {
  return (
    <div className={`card flex flex-col items-center px-6 py-12 text-center ${className}`}>
      {Icon && (
        <span className="mb-4 flex size-14 items-center justify-center rounded-full bg-raised">
          <Icon aria-hidden="true" className="size-7 text-ink-soft" />
        </span>
      )}
      <h2 className="text-2xl font-bold">{title}</h2>
      {children && <p className="mt-2 max-w-md text-ink-soft">{children}</p>}
      {action && <div className="mt-6 flex flex-wrap justify-center gap-3">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, title = "That didn't load", onRetry, className = '' }) {
  return (
    <div role="alert" className={`card flex flex-col items-center px-6 py-10 text-center ${className}`}>
      <CircleAlert aria-hidden="true" className="mb-3 size-8 text-danger" />
      <h2 className="text-xl font-bold">{title}</h2>
      <p className="mt-2 max-w-md text-ink-soft">{error?.message ?? 'Something went wrong. Please try again.'}</p>
      {onRetry && (
        <Button variant="secondary" icon={RotateCw} onClick={onRetry} className="mt-5">
          Try again
        </Button>
      )}
    </div>
  );
}
