/** A row of mutually exclusive options, built on real radio inputs for keyboard and screen reader support. */
import { useId } from 'react';

export function Segmented({ legend, options, value, onChange, legendHidden = false, legendClassName = 'mb-2 text-sm font-medium text-ink-soft', className = '' }) {
  const name = useId();
  return (
    <fieldset className={className}>
      <legend className={legendHidden ? 'sr-only' : legendClassName}>{legend}</legend>
      <div className="inline-flex max-w-full flex-wrap gap-1 rounded-xl border border-line bg-stage p-1">
        {options.map((option) => {
          const selected = String(option.value) === String(value);
          return (
            <label
              key={option.value}
              className={`relative flex min-h-10 cursor-pointer items-center rounded-lg px-3.5 text-sm font-medium transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-1 has-[:focus-visible]:outline-amber-bright ${
                selected ? 'bg-overlay text-ink' : 'text-ink-muted hover:text-ink'
              }`}
            >
              <input type="radio" name={name} value={option.value} checked={selected} onChange={() => onChange(option.value)} className="sr-only" />
              {option.label}
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
