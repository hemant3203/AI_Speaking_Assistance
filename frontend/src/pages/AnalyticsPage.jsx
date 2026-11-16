/**
 * "Where to improve". It leads with the actionable answer (focus areas), then the evidence. One
 * range filter sits above everything, so every number on the page always agrees.
 */
import { useState } from 'react';
import { ArrowDown, ArrowRight, ArrowUp, ChartNoAxesColumn, CalendarSearch, Lightbulb, Minus, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { fetchOverview } from '../api/analytics';
import { useAuth } from '../context/AuthContext';
import { useApi } from '../hooks/useApi';
import { useProfile } from '../components/layout/AppLayout';
import { Button } from '../components/ui/Button';
import { PageHeader } from '../components/ui/PageHeader';
import { Segmented } from '../components/ui/Segmented';
import { EmptyState, ErrorState, Skeleton } from '../components/ui/States';
import { ActivityHeatmap } from '../components/charts/ActivityHeatmap';
import { ModesBreakdown, TopFillers } from '../components/charts/BreakdownCharts';
import { SkillBars, SkillRadar } from '../components/charts/SkillCharts';
import { Delta, StatTile } from '../components/charts/StatTile';
import { FillerTrend, PaceTrend, ScoreTrend } from '../components/charts/TrendCharts';
import { humanDuration, oneDecimal, rounded, signed } from '../lib/format';

const RANGES = [
  { value: 7, label: '7 days' },
  { value: 30, label: '30 days' },
  { value: 90, label: '90 days' },
  { value: 0, label: 'All time' },
];

function FocusDelta({ delta }) {
  if (delta === null || delta === undefined) return null;
  const Icon = delta > 0 ? ArrowUp : delta < 0 ? ArrowDown : Minus;
  const tone = delta > 0 ? 'text-good' : delta < 0 ? 'text-serious' : 'text-ink-soft';
  return (
    <span className={`inline-flex items-center gap-0.5 text-sm font-medium ${tone}`}>
      <Icon aria-hidden="true" className="size-3.5" />
      {delta === 0 ? 'No change' : signed(delta)}
    </span>
  );
}

function FocusAreas({ areas, strengths }) {
  const [first, ...rest] = areas;
  return (
    <section aria-labelledby="focus-heading" className="mb-8">
      <h2 id="focus-heading" className="mb-4 text-2xl font-bold">
        Start here
      </h2>
      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        {first && (
          <article className="card flex flex-col border-line-strong p-5 sm:p-7">
            <p className="kicker">Your biggest opportunity</p>
            <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <h3 className="text-3xl font-bold sm:text-4xl">{first.name}</h3>
              <p className="text-ink-soft">
                <span className="font-semibold text-ink">{first.score}</span>/100
              </p>
              <FocusDelta delta={first.delta} />
            </div>
            <p className="mt-3 text-ink-soft">{first.why}</p>
            <p className="mt-4 flex gap-2.5 rounded-xl bg-raised p-3.5 text-sm text-ink">
              <Lightbulb aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-amber" />
              {first.tip}
            </p>
            <div className="mt-5">
              <Button to={`/practice?mode=${encodeURIComponent(first.drill_mode)}&focus=${encodeURIComponent(first.skill)}`} icon={ArrowRight}>
                Practise this
              </Button>
            </div>
          </article>
        )}
        <div className="flex flex-col gap-4">
          {rest.map((area) => (
            <article key={area.skill} className="card flex flex-1 flex-col p-5">
              <div className="flex flex-wrap items-baseline gap-x-2.5">
                <h3 className="text-xl font-bold">{area.name}</h3>
                <p className="text-sm text-ink-soft">
                  <span className="font-semibold text-ink">{area.score}</span>/100
                </p>
                <FocusDelta delta={area.delta} />
              </div>
              <p className="mt-1.5 text-sm text-ink-soft">{area.tip}</p>
              <Link
                to={`/practice?mode=${encodeURIComponent(area.drill_mode)}&focus=${encodeURIComponent(area.skill)}`}
                className="mt-auto inline-flex min-h-10 items-center gap-1 pt-2 text-sm font-semibold underline underline-offset-2 hover:text-amber-bright"
              >
                Practise this
                <ArrowRight aria-hidden="true" className="size-4" />
              </Link>
            </article>
          ))}
        </div>
      </div>
      {strengths?.length > 0 && (
        <p className="mt-4 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-ink-soft">
          <Sparkles aria-hidden="true" className="size-4 text-mint" />
          Going well:
          {strengths.map((strength, index) => (
            <span key={strength.skill}>
              <span className="font-semibold text-ink">{strength.name}</span> {strength.score}
              {index < strengths.length - 1 ? ',' : ''}
            </span>
          ))}
        </p>
      )}
    </section>
  );
}

function Summary({ summary, periodLabel }) {
  const deltas = summary.deltas ?? {};
  return (
    <section aria-label="Summary" className="mb-8 grid grid-cols-2 gap-3 md:grid-cols-3">
      <StatTile label="Sessions" value={rounded(summary.sessions)}>
        <Delta value={deltas.sessions} periodLabel={periodLabel} />
      </StatTile>
      <StatTile label="Speaking time" value={humanDuration(summary.speaking_seconds)} />
      <StatTile label="Average score" value={rounded(summary.avg_score)}>
        <Delta value={deltas.avg_score} periodLabel={periodLabel} />
      </StatTile>
      <StatTile label="Best score" value={rounded(summary.best_score)} />
      <StatTile label="Average words per minute" value={rounded(summary.avg_wpm)}>
        <Delta value={deltas.avg_wpm} goodWhen="neutral" periodLabel={periodLabel} />
      </StatTile>
      <StatTile label="Fillers per 100" value={oneDecimal(summary.avg_filler_per_100)}>
        <Delta value={deltas.avg_filler_per_100} goodWhen="down" digits={1} periodLabel={periodLabel} />
      </StatTile>
    </section>
  );
}

function AnalyticsSkeleton() {
  return (
    <div role="status" aria-label="Loading your analytics" className="flex flex-col gap-5">
      <Skeleton className="h-64 rounded-[var(--radius-card)]" />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        {Array.from({ length: 6 }, (_, index) => (
          <Skeleton key={index} className="h-24 rounded-[var(--radius-card)]" />
        ))}
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Skeleton className="h-80 rounded-[var(--radius-card)]" />
        <Skeleton className="h-80 rounded-[var(--radius-card)]" />
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  const { user } = useAuth();
  const { profile } = useProfile();
  const [days, setDays] = useState(30);
  const { data, loading, refreshing, error, reload } = useApi(() => fetchOverview(days), [days]);
  const periodLabel = days === 0 ? null : `previous ${days} days`;
  // Someone who has never practised needs an invitation, not "nothing in the last 30 days".
  const neverPractised = profile?.stats?.total_sessions === 0;

  const filter = (
    <Segmented legend="Date range" legendHidden value={days} onChange={(value) => setDays(Number(value))} options={RANGES} className="mb-6" />
  );

  let body;
  if (loading) {
    body = <AnalyticsSkeleton />;
  } else if (error && !data) {
    body = <ErrorState error={error} title="We couldn't load your analytics" onRetry={reload} />;
  } else if (data.summary.sessions === 0 && days !== 0 && !neverPractised) {
    body = (
      <EmptyState
        icon={CalendarSearch}
        title={`No sessions in the last ${days} days`}
        action={
          <>
            <Button to="/practice">Practise now</Button>
            <Button variant="secondary" onClick={() => setDays(0)}>
              See all time
            </Button>
          </>
        }
      >
        One session today puts this page back to work.
      </EmptyState>
    );
  } else if (data.summary.sessions === 0) {
    body = (
      <EmptyState icon={ChartNoAxesColumn} title="Your first chart starts with one speech" action={<Button to="/practice">Step into the spotlight</Button>}>
        Finish a session and this page will show exactly which skills to work on, with a drill for each.
      </EmptyState>
    );
  } else {
    const focusIds = data.focus_areas.map((area) => area.skill);
    body = (
      // Refetch keeps the frame: the old numbers dim rather than disappear behind a skeleton.
      <div className={`transition-opacity duration-200 ${refreshing ? 'opacity-50' : ''}`} aria-busy={refreshing}>
        <FocusAreas areas={data.focus_areas} strengths={data.strengths} />
        <Summary summary={data.summary} periodLabel={periodLabel} />

        <div className="grid gap-5 lg:grid-cols-2">
          <SkillBars skills={data.skills} focusSkillIds={focusIds} />
          <SkillRadar skills={data.skills} />
          <div className="lg:col-span-2">
            <ScoreTrend rows={data.score_trend} />
          </div>
          <PaceTrend rows={data.pace_trend} band={data.pace_band} />
          <FillerTrend rows={data.filler_trend} />
          <TopFillers fillers={data.top_fillers} />
          <ModesBreakdown modes={data.modes} />
          <div className="lg:col-span-2">
            <ActivityHeatmap heatmap={data.heatmap} timeZone={user?.timezone} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <PageHeader title="Where to improve" description="What to work on next, and the evidence behind it." />
      {filter}
      {body}
    </>
  );
}
