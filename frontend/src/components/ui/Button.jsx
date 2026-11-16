/** The app's one button. Amber "primary" is the single action color, so use it once per view. */
import { Link } from 'react-router-dom';
import { LoaderCircle } from 'lucide-react';

const VARIANTS = {
  primary: 'bg-amber text-on-amber hover:bg-amber-bright active:bg-amber-deep disabled:bg-overlay disabled:text-ink-muted',
  secondary: 'border border-control text-ink hover:bg-raised active:bg-overlay disabled:border-line disabled:text-ink-muted',
  ghost: 'text-ink-soft hover:bg-raised hover:text-ink disabled:text-ink-muted',
  danger: 'bg-danger-solid text-white hover:brightness-110 disabled:bg-overlay disabled:text-ink-muted',
};

const SIZES = {
  sm: 'min-h-10 px-3.5 text-sm rounded-lg gap-1.5',
  md: 'min-h-11 px-5 text-[0.9375rem] rounded-xl gap-2',
  lg: 'min-h-14 px-7 text-lg rounded-2xl gap-2.5',
};

export function Button({ variant = 'primary', size = 'md', to, href, loading = false, icon: Icon, children, className = '', disabled, ...props }) {
  const classes = `inline-flex items-center justify-center font-semibold transition-colors duration-150 ${VARIANTS[variant]} ${SIZES[size]} ${className}`;
  const content = (
    <>
      {loading ? <LoaderCircle aria-hidden="true" className="size-[1.15em] animate-spin" /> : Icon && <Icon aria-hidden="true" className="size-[1.15em] shrink-0" />}
      {children}
    </>
  );
  if (to) {
    return (
      <Link to={to} className={classes} {...props}>
        {content}
      </Link>
    );
  }
  return (
    <button type="button" className={classes} disabled={disabled || loading} aria-busy={loading || undefined} {...props}>
      {content}
    </button>
  );
}
