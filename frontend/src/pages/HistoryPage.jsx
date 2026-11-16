/** Past sessions: paginated, filterable by mode. Filter and page live in the URL, so back works. */
import { Link, useSearchParams } from 'react-router-dom';
import { ChevronLeft, ChevronRight, History as HistoryIcon, Target } from 'lucide-react';
import { fetchCatalog, fetchSessions } from '../api/practice';
import { useApi } from '../hooks/useApi';
import { Button } from '../components/ui/Button';
import { DynamicIcon } from '../components/ui/DynamicIcon';
import { PageHeader } from '../components/ui/PageHeader';
import { EmptyState, ErrorState, Skeleton } from '../components/ui/States';
import { clock, oneDecimal, rounded, shortDate } from '../lib/format';

const PAGE_SIZE = 20;

function SessionRow({ session, mode }) {
  const tooShort = session.status === 'too_short';
  return (
    <li>
      <Link to={`/sessions/${session.id}`} className="flex items-center gap-3 rounded-xl p-3 transition-colors hover:bg-raised sm:gap-4 sm:p-4">
        <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-raised text-ink-soft">
          <DynamicIcon name={mode?.icon} fallback={Target} className="size-5" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold">{session.topic}</p>
          <p className="mt-0.5 flex flex-wrap gap-x-3 text-sm text-ink-muted">
            <span>{shortDate(session.local_date)}</span>
            <span>{mode?.name ?? session.mode}</span>
            <span>{clock(session.speaking_seconds)}</span>
            {session.challenge_date && <span className="text-ink-soft">Challenge</span>}
            {session.retry_of && <span className="text-ink-soft">Second take</span>}
            {!tooShort && <span className="hidden sm:inline">{rounded(session.wpm)} wpm</span>}
            {!tooShort && <span className="hidden sm:inline">{oneDecimal(session.filler_per_100)} fillers/100</span>}
          </p>
        </div>
        <div className="shrink-0 text-right">
          {tooShort ? (
            <p className="text-sm text-ink-muted">Too short</p>
          ) : (
            <>
              <p className="font-display text-2xl font-bold leading-none">{session.overall_score ?? '–'}</p>
              <p className="mt-1 text-xs font-medium text-mint">+{session.xp_awarded ?? 0} XP</p>
            </>
          )}
        </div>
      </Link>
    </li>
  );
}

export default function HistoryPage() {
  const [params, setParams] = useSearchParams();
  const mode = params.get('mode') ?? '';
  const page = Math.max(1, Number(params.get('page')) || 1);
  const catalog = useApi(fetchCatalog, []);
  const { data, loading, refreshing, error, reload } = useApi(() => fetchSessions({ limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE, mode }), [mode, page]);

  const modes = catalog.data?.modes ?? [];
  const modeById = Object.fromEntries(modes.map((item) => [item.id, item]));
  const total = data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const setFilter = (next) => setParams(next ? { mode: next } : {});
  const goTo = (nextPage) => {
    const nextParams = {};
    if (mode) nextParams.mode = mode;
    if (nextPage > 1) nextParams.page = String(nextPage);
    setParams(nextParams);
    window.scrollTo(0, 0);
  };

  return (
    <>
      <PageHeader title="History" description="Every take you've finished. Tap one to see its scores and transcript." />

      {modes.length > 0 && (
        <div role="group" aria-label="Filter by mode" className="mb-5 flex flex-wrap gap-2">
          {[{ id: '', name: 'All modes' }, ...modes].map((item) => {
            const on = item.id === mode;
            return (
              <button
                key={item.id || 'all'}
                type="button"
                aria-pressed={on}
                onClick={() => setFilter(item.id)}
                className={`min-h-10 rounded-lg border px-3.5 text-sm font-medium transition-colors ${on ? 'border-line-strong bg-overlay text-ink' : 'border-line text-ink-muted hover:text-ink'}`}
              >
                {item.name}
              </button>
            );
          })}
        </div>
      )}

      {loading && (
        <div role="status" aria-label="Loading your sessions" className="flex flex-col gap-2">
          {Array.from({ length: 6 }, (_, index) => (
            <Skeleton key={index} className="h-20" />
          ))}
        </div>
      )}
      {error && !data && <ErrorState error={error} title="We couldn't load your sessions" onRetry={reload} />}
      {data && data.items.length === 0 && (
        <EmptyState
          icon={HistoryIcon}
          title={mode ? `No ${modeById[mode]?.name ?? ''} sessions yet` : 'Nothing here yet'}
          action={<Button to={mode ? `/practice?mode=${encodeURIComponent(mode)}` : '/practice'}>{mode ? 'Try this mode' : 'Step into the spotlight'}</Button>}
        >
          {mode ? 'Give this mode a go, and your take will show up here.' : 'Your first take will show up here, with its score and transcript.'}
        </EmptyState>
      )}
      {data && data.items.length > 0 && (
        <div className={`transition-opacity duration-200 ${refreshing ? 'opacity-50' : ''}`} aria-busy={refreshing}>
          <ul className="card divide-y divide-line p-1 sm:p-2">
            {data.items.map((session) => (
              <SessionRow key={session.id} session={session} mode={modeById[session.mode]} />
            ))}
          </ul>
          <nav aria-label="Pagination" className="mt-5 flex items-center justify-between gap-3">
            <Button variant="secondary" size="sm" icon={ChevronLeft} disabled={page <= 1} onClick={() => goTo(page - 1)}>
              Newer
            </Button>
            <p className="text-sm text-ink-soft" aria-live="polite">
              Page {page} of {pageCount}
            </p>
            <Button variant="secondary" size="sm" disabled={page >= pageCount} onClick={() => goTo(page + 1)}>
              Older
              <ChevronRight aria-hidden="true" className="size-[1.15em]" />
            </Button>
          </nav>
        </div>
      )}
    </>
  );
}
