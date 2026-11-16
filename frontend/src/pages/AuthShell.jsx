/** Shared split layout for login and register: the stage on one side, the form on the other. */
import { Link } from 'react-router-dom';
import { ShieldCheck } from 'lucide-react';
import { Logo } from '../components/ui/Logo';
import { StageScene } from '../components/ui/StageScene';

export function AuthShell({ heading, subheading, children, footer }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-[1.1fr_1fr]">
      <aside className="relative h-64 overflow-hidden bg-stage sm:h-72 lg:sticky lg:top-0 lg:h-dvh">
        <StageScene className="absolute inset-0 size-full" />
        <div aria-hidden="true" className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-stage/90 to-transparent lg:h-2/5" />
        <div className="absolute left-5 top-5 lg:left-10 lg:top-8">
          <Link to="/login" aria-label="Spotlight home">
            <Logo />
          </Link>
        </div>
        <div className="absolute inset-x-5 bottom-4 lg:inset-x-10 lg:bottom-10">
          <p className="max-w-[12.5rem] font-display text-2xl font-bold leading-[1.08] tracking-tight sm:max-w-xs sm:text-3xl lg:max-w-[20rem] lg:text-4xl xl:max-w-[26rem] xl:text-5xl">
            The room gets easier once you've stood in the light.
          </p>
          <p className="mt-4 hidden max-w-[20rem] text-ink-soft lg:block xl:max-w-[26rem] xl:text-lg">Speak for a minute. Hear exactly what to work on. Come back tomorrow a little braver.</p>
        </div>
      </aside>

      <main className="flex items-start justify-center bg-stage px-5 py-8 sm:px-8 lg:items-center lg:py-12">
        <div className="w-full max-w-sm">
          <h1 className="text-3xl font-bold sm:text-4xl">{heading}</h1>
          {subheading && <p className="mt-2 text-ink-soft">{subheading}</p>}
          <div className="mt-7">{children}</div>
          {footer && <p className="mt-6 text-sm text-ink-soft">{footer}</p>}
          <p className="mt-6 flex gap-2 border-t border-line pt-5 text-xs text-ink-muted">
            <ShieldCheck aria-hidden="true" className="size-4 shrink-0" />
            <span>Your speech audio is sent to Google Gemini for coaching and is not stored on our servers.</span>
          </p>
        </div>
      </main>
    </div>
  );
}
