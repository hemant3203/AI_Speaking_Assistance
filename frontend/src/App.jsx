// Routes. Pages other than auth are lazy loaded, which keeps Recharts out of the login bundle.
import { lazy } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import { AppLayout } from './components/layout/AppLayout';
import { ErrorState, FullPageLoader } from './components/ui/States';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';

const RELOAD_FLAG = 'spotlight:reloaded-for-update';
// A failure this soon after our own reload means the reload didn't help, so stop and show the error.
// The flag holds a time, not a yes/no, so one bad deploy can't turn off recovery for the rest of the tab's life.
const RELOAD_WINDOW_MS = 30_000;

function readReloadTime() {
  try {
    return Number(sessionStorage.getItem(RELOAD_FLAG)) || 0;
  } catch {
    return null; // Storage blocked: we can't tell whether we already reloaded, so never auto-reload.
  }
}

/**
 * Page files have hashed names, so a restart replaces them and a tab left open asks for ones that are gone.
 * Reloading once fetches the new ones. The flag stops a page that is really missing from reloading forever.
 */
function lazyPage(load) {
  return lazy(async () => {
    try {
      return await load();
    } catch (error) {
      const last = readReloadTime();
      if (last === null || Date.now() - last < RELOAD_WINDOW_MS) throw error;
      try {
        sessionStorage.setItem(RELOAD_FLAG, String(Date.now()));
      } catch {
        throw error;
      }
      window.location.reload();
      return new Promise(() => {});
    }
  });
}

const DashboardPage = lazyPage(() => import('./pages/DashboardPage'));
const PracticePage = lazyPage(() => import('./pages/PracticePage'));
const SessionDetailPage = lazyPage(() => import('./pages/SessionDetailPage'));
const AnalyticsPage = lazyPage(() => import('./pages/AnalyticsPage'));
const HistoryPage = lazyPage(() => import('./pages/HistoryPage'));
const RewardsPage = lazyPage(() => import('./pages/RewardsPage'));
const SettingsPage = lazyPage(() => import('./pages/SettingsPage'));
const NotFoundPage = lazyPage(() => import('./pages/NotFoundPage'));

/** Remembers where the user was heading, so login can send them back. */
function RequireAuth({ children }) {
  const { status, retry, bootError } = useAuth();
  const location = useLocation();
  if (status === 'loading') return <FullPageLoader />;
  if (status === 'error') {
    return (
      <main className="mx-auto max-w-md px-4 py-24">
        <ErrorState error={bootError} title="We can't reach Spotlight" onRetry={retry} />
      </main>
    );
  }
  if (status === 'anon') return <Navigate to="/login" replace state={{ from: location }} />;
  return children;
}

function RedirectIfAuthed({ children }) {
  const { status } = useAuth();
  const location = useLocation();
  if (status === 'loading') return <FullPageLoader />;
  if (status === 'authed') return <Navigate to={location.state?.from ?? '/'} replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<RedirectIfAuthed><LoginPage /></RedirectIfAuthed>} />
      <Route path="/register" element={<RedirectIfAuthed><RegisterPage /></RedirectIfAuthed>} />
      <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
        <Route index element={<DashboardPage />} />
        <Route path="practice" element={<PracticePage />} />
        <Route path="sessions/:id" element={<SessionDetailPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="history" element={<HistoryPage />} />
        <Route path="rewards" element={<RewardsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
