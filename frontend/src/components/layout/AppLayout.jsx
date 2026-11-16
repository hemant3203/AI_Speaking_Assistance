/**
 * Signed-in shell: sidebar on desktop, top bar and bottom nav on mobile.
 *
 * It owns the gamification profile because the nav chips, dashboard and practice page all read it.
 * Pages get it through Outlet context, so a purchase or finished session refreshes all of them.
 */
import { Suspense, useEffect, useMemo } from 'react';
import { NavLink, Outlet, useLocation, useOutletContext } from 'react-router-dom';
import { ChartNoAxesColumn, Flame, Gift, History, House, Mic, Settings, Sparkle } from 'lucide-react';
import { fetchProfile } from '../../api/gamification';
import { useApi } from '../../hooks/useApi';
import { Logo } from '../ui/Logo';
import { PageSkeleton } from '../ui/States';
import { ErrorBoundary } from './ErrorBoundary';

const NAV = [
  { to: '/', label: 'Home', icon: House, end: true },
  { to: '/practice', label: 'Practice', icon: Mic },
  { to: '/analytics', label: 'Where to improve', short: 'Improve', icon: ChartNoAxesColumn },
  { to: '/history', label: 'History', icon: History },
  { to: '/rewards', label: 'Rewards', icon: Gift },
];

/** Read the shared profile from any page inside the layout. */
export function useProfile() {
  return useOutletContext();
}

function StatChips({ profile }) {
  if (!profile) return null;
  const live = profile.streak.status !== 'none';
  return (
    <div className="flex items-center gap-3 text-sm font-semibold">
      <span className="flex items-center gap-1.5" title="Current streak">
        <Flame aria-hidden="true" className={`size-4 ${live ? 'text-flame' : 'text-ink-muted'}`} />
        <span className="sr-only">Streak:</span>
        {profile.streak.current}
      </span>
      <span className="flex items-center gap-1.5" title="Sparks">
        <Sparkle aria-hidden="true" className="size-4 text-spark" />
        <span className="sr-only">Sparks:</span>
        {profile.sparks}
      </span>
    </div>
  );
}

function Sidebar({ profile }) {
  const linkClass = ({ isActive }) =>
    `flex min-h-11 items-center gap-3 rounded-xl px-3 text-[0.9375rem] font-medium transition-colors ${
      isActive ? 'bg-raised text-ink' : 'text-ink-soft hover:bg-raised/60 hover:text-ink'
    }`;
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-line bg-stage px-4 py-6 lg:flex">
      <NavLink to="/" className="px-3" aria-label="Spotlight home">
        <Logo />
      </NavLink>
      <nav aria-label="Main" className="mt-8 flex flex-col gap-1">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} className={linkClass}>
            {({ isActive }) => (
              <>
                <Icon aria-hidden="true" className={`size-5 ${isActive ? 'text-amber' : ''}`} />
                {label}
              </>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto flex flex-col gap-3">
        {profile && (
          <div className="rounded-xl border border-line px-3 py-3">
            <p className="truncate text-sm font-semibold">{profile.level_title}</p>
            <p className="mb-2 text-xs text-ink-muted">Level {profile.level}</p>
            <StatChips profile={profile} />
          </div>
        )}
        <NavLink to="/settings" className={linkClass}>
          <Settings aria-hidden="true" className="size-5" />
          Settings
        </NavLink>
      </div>
    </aside>
  );
}

function TopBar({ profile }) {
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-line bg-stage px-4 lg:hidden">
      <NavLink to="/" aria-label="Spotlight home">
        <Logo />
      </NavLink>
      <div className="flex items-center gap-3">
        <StatChips profile={profile} />
        <NavLink to="/settings" aria-label="Settings" className="-mr-2 flex size-11 items-center justify-center rounded-lg text-ink-soft hover:text-ink">
          <Settings aria-hidden="true" className="size-5" />
        </NavLink>
      </div>
    </header>
  );
}

function BottomNav() {
  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-line bg-stage pb-[env(safe-area-inset-bottom)] lg:hidden"
    >
      {NAV.map(({ to, label, short, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          aria-label={label}
          className={({ isActive }) =>
            `flex min-h-16 min-w-0 flex-col items-center justify-center gap-1 text-[0.6875rem] font-medium ${isActive ? 'text-ink' : 'text-ink-muted hover:text-ink-soft'}`
          }
        >
          {({ isActive }) => (
            <>
              <span className={`flex h-7 w-12 items-center justify-center rounded-full ${isActive ? 'bg-raised' : ''}`}>
                <Icon aria-hidden="true" className={`size-5 ${isActive ? 'text-amber' : ''}`} />
              </span>
              {short ?? label}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

export function AppLayout() {
  const { pathname } = useLocation();
  const profile = useApi(fetchProfile, []);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  const context = useMemo(
    () => ({
      profile: profile.data,
      profileLoading: profile.loading,
      profileError: profile.error,
      reloadProfile: profile.reload,
    }),
    [profile.data, profile.loading, profile.error, profile.reload],
  );

  return (
    <div className="house-light min-h-dvh lg:pl-64">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[80] focus:rounded-lg focus:bg-amber focus:px-4 focus:py-2 focus:font-semibold focus:text-on-amber"
      >
        Skip to content
      </a>
      <Sidebar profile={profile.data} />
      <TopBar profile={profile.data} />
      <main id="main" tabIndex={-1} className="mx-auto w-full max-w-6xl px-4 pb-28 pt-6 outline-none sm:px-6 lg:px-10 lg:pb-14 lg:pt-10">
        <ErrorBoundary key={pathname}>
          <Suspense fallback={<PageSkeleton />}>
            <Outlet context={context} />
          </Suspense>
        </ErrorBoundary>
      </main>
      <BottomNav />
    </div>
  );
}
