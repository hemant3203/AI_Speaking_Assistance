/** Labelled form fields with inline errors wired up through aria-describedby. */
import { useId, useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';

const INPUT =
  'w-full min-h-11 rounded-xl border bg-stage px-3.5 py-2.5 text-[0.9375rem] text-ink placeholder:text-ink-muted transition-colors focus:outline-2 focus:outline-offset-1 focus:outline-amber-bright disabled:opacity-60';

function borderFor(error) {
  return error ? 'border-danger' : 'border-control hover:border-ink-muted';
}

export function FieldShell({ id, label, hint, error, children }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-ink-soft">
        {label}
      </label>
      {children}
      {error ? (
        <p id={`${id}-error`} className="mt-1.5 text-sm text-danger">
          {error}
        </p>
      ) : (
        hint && (
          <p id={`${id}-hint`} className="mt-1.5 text-sm text-ink-muted">
            {hint}
          </p>
        )
      )}
    </div>
  );
}

const describedBy = (id, error, hint) => (error ? `${id}-error` : hint ? `${id}-hint` : undefined);

export function TextField({ label, hint, error, id: givenId, className = '', ...props }) {
  const autoId = useId();
  const id = givenId ?? autoId;
  return (
    <FieldShell id={id} label={label} hint={hint} error={error}>
      <input id={id} aria-invalid={error ? true : undefined} aria-describedby={describedBy(id, error, hint)} className={`${INPUT} ${borderFor(error)} ${className}`} {...props} />
    </FieldShell>
  );
}

export function PasswordField({ label = 'Password', hint, error, ...props }) {
  const id = useId();
  const [visible, setVisible] = useState(false);
  return (
    <FieldShell id={id} label={label} hint={hint} error={error}>
      <div className="relative">
        <input
          id={id}
          type={visible ? 'text' : 'password'}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy(id, error, hint)}
          className={`${INPUT} pr-12 ${borderFor(error)}`}
          {...props}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? 'Hide password' : 'Show password'}
          aria-pressed={visible}
          className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-xl text-ink-muted hover:text-ink"
        >
          {visible ? <EyeOff aria-hidden="true" className="size-5" /> : <Eye aria-hidden="true" className="size-5" />}
        </button>
      </div>
    </FieldShell>
  );
}

export function SelectField({ label, hint, error, children, className = '', ...props }) {
  const id = useId();
  return (
    <FieldShell id={id} label={label} hint={hint} error={error}>
      <select id={id} aria-invalid={error ? true : undefined} aria-describedby={describedBy(id, error, hint)} className={`${INPUT} ${borderFor(error)} ${className}`} {...props}>
        {children}
      </select>
    </FieldShell>
  );
}
