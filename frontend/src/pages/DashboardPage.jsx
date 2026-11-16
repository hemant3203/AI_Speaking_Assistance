/**
 * Home, and the reason people come back. The hero answers "what should I do today?" in one line
 * with one amber button, and everything else is the progress that makes that worth doing.
 */
import { Link } from 'react-router-dom';
import { ArrowRight, ArrowUpRight, Lightbulb, Mic, Snowflake, Target } from 'lucide-react';
import { fetchOverview } from '../api/analytics';
import { useAuth } from '../context/AuthContext';
import { useApi } from '../hooks/useApi';
import { useProfile } from '../components/layout/AppLayout';
import { BadgeMedal } from '../components/gamification/BadgeCard';
import { DailyChallengeCard } from '../components/gamification/DailyChallenge';
import { LevelBlock, QuestRow, SparksAmount } from '../components/gamification/Progress';
import { StreakFlame, WeekRow, streakCopy } from '../components/gamification/Streak';
import { Button } from '../components/ui/Button';
import { useDocumentTitle } from '../components/ui/PageHeader';
import { ProgressBar } from '../components/ui/ProgressBar';
import { SpotBeam } from '../components/ui/StageScene';
import { ErrorState, Skeleton } from '../components/ui/States';
import { humanDuration, plural, signed } from '../lib/format';

function greeting() {
  const hour = new Date().getHours();
  if (hour < 5) return 'Still up';
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

function Hero({ profile, name }) {
  const { streak, stats } = profile;
  const firstRun = stats.total_sessions === 0;
  const copy = streakCopy(streak, stats.total_sessions);
  const atRisk = streak.status === 'at_risk' && !firstRun;

  return (
    <section aria-labelledby="hero-heading" className="card relative overflow-hidden">
      {/* The beam lands on the streak, so the thing the user is protecting is what's in the light. */}
      <SpotBeam className="right-0 top-0 hidden h-full w-[52%] lg:block" />
      <div className="relative grid gap-8 p-5 sm:p-8 lg:grid-cols-[1.25fr_1fr] lg:items-center lg:gap-6 lg:p-10">
        <div className="min-w-0">
          <p className="text-ink-soft">
            {greeting()}, {name}
          </p>
          <h1 id="hero-heading" className="mt-2 text-4xl font-bold sm:text-5xl">
            {copy.headline}
          </h1>
          <p className="mt-3 max-w-lg text-ink-soft">{copy.detail}</p>
          <Button to="/practice" size="lg" icon={Mic} className={`mt-6 w-full sm:w-auto ${atRisk ? 'motion-safe:animate-pulse-ring' : ''}`}>
            Step into the spotlight
          </Button>
        </div>

        {firstRun ? (
          <ol className="flex flex-col gap-3 text-sm">
            {['Pick a topic, or let us shuffle one for you', 'Talk for a minute. Stumbling is allowed', 'Get your score, XP and one clear thing to try next'].map((text, index) => (
              <li key={text} className="flex items-center gap-3 rounded-xl border border-line bg-stage/60 p-3">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-raised font-display font-bold">{index + 1}</span>
                <span className="text-ink-soft">{text}</span>
              </li>
            ))}
          </ol>
        ) : (
          <div className="flex flex-col items-stretch gap-5">
            <div className="flex items-center justify-center gap-4">
              <StreakFlame status={streak.status} className="h-24 w-20 shrink-0" />
              <div>
                <p className="font-display text-7xl font-bold leading-none tracking-tight">{streak.current}</p>
                <p className="mt-1 text-sm font-medium text-ink-soft">day streak</p>
              </div>
            </div>
            <WeekRow week={streak.week} />
            <p className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-ink-soft">
              <span>Longest: {plural(streak.longest, 'day')}</span>
              <span className="inline-flex items-center gap-1">
                <Snowflake aria-hidden="true" className="size-3.5 text-frost" />
                {plural(streak.freezes, 'freeze')} saved
              </span>
            </p>
          </div>
        )}
      </div>
    </section>
  );
}

function Quests({ quests }) {
  const done = quests.items.filter((quest) => quest.completed).length;
  return (
    <section aria-labelledby="quests-heading" className="card p-5 sm:p-6">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="quests-heading" className="text-xl font-bold">
          Today's quests
        </h2>
        <p className="text-sm text-ink-soft">{done} of {quests.items.length} done</p>
      </div>
      <ul className="mt-4 divide-y divide-line">
        {quests.items.map((quest) => (
          <QuestRow key={quest.id} quest={quest} />
        ))}
      </ul>
      <p className="mt-4 border-t border-line pt-3 text-sm text-ink-soft">
        {quests.all_complete ? (
          <>All done today. You earned the <SparksAmount amount={quests.bonus_sparks} className="font-semibold text-ink" /> bonus.</>
        ) : (
          <>Finish all {quests.items.length} for a bonus of <SparksAmount amount={quests.bonus_sparks} className="font-semibold text-ink" />.</>
        )}
      </p>
    </section>
  );
}

function FocusCard({ overview }) {
  const { data, loading } = overview;
  if (loading) return <Skeleton className="h-44 flex-1 rounded-[var(--radius-card)]" />;
  const focus = data?.focus_areas?.[0];
  if (!focus) {
    return (
      <section className="card flex-1 p-5 sm:p-6">
        <p className="kicker flex items-center gap-1.5">
          <Target aria-hidden="true" className="size-4" />
          Your top focus
        </p>
        <p className="mt-2 text-ink-soft">Finish a session or two and we'll point out the one skill that will make the biggest difference.</p>
      </section>
    );
  }
  return (
    <section className="card flex flex-1 flex-col p-5 sm:p-6">
      <p className="kicker flex items-center gap-1.5">
        <Target aria-hidden="true" className="size-4" />
        Your top focus
      </p>
      <div className="mt-2 flex items-baseline justify-between gap-3">
        <h2 className="text-2xl font-bold">{focus.name}</h2>
        <p className="shrink-0 text-sm text-ink-soft">
          <span className="font-semibold text-ink">{focus.score}</span>/100
          {focus.delta !== null && focus.delta !== undefined && <span className="text-ink-muted"> ({signed(focus.delta)})</span>}
        </p>
      </div>
      {focus.why && <p className="mt-2 text-sm text-ink-soft">{focus.why}</p>}
      <p className="mt-3 flex gap-2.5 rounded-xl bg-raised p-3.5 text-sm text-ink">
        <Lightbulb aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-ink-soft" />
        {focus.tip}
      </p>
      <div className="mt-auto flex flex-wrap gap-x-4 pt-3">
        <Link to={`/practice?mode=${encodeURIComponent(focus.drill_mode)}&focus=${encodeURIComponent(focus.skill)}`} className="inline-flex min-h-10 items-center gap-1 text-sm font-semibold underline underline-offset-2 hover:text-amber-bright">
          Practise this
          <ArrowRight aria-hidden="true" className="size-4" />
        </Link>
        <Link to="/analytics" className="inline-flex min-h-10 items-center gap-1 text-sm text-ink-soft underline underline-offset-2 hover:text-ink">
          See all
          <ArrowUpRight aria-hidden="true" className="size-4" />
        </Link>
      </div>
    </section>
  );
}

function NextBadge({ badge }) {
  if (!badge) {
    return (
      <section className="card p-5 sm:p-6">
        <p className="kicker">Next badge</p>
        <p className="mt-2 text-ink-soft">You've earned every badge there is. That's remarkable.</p>
      </section>
    );
  }
  const left = Math.max(0, badge.target - badge.progress);
  return (
    <section className="card flex flex-col p-5 sm:p-6">
      <p className="kicker">Next badge</p>
      <div className="mt-3 flex items-center gap-4">
        <BadgeMedal badge={badge} />
        <div className="min-w-0">
          <h2 className="font-sans text-lg font-semibold tracking-normal">{badge.name}</h2>
          <p className="text-sm text-ink-soft">{badge.description}</p>
        </div>
      </div>
      <ProgressBar value={badge.progress} max={badge.target} label={`${badge.name} progress`} className="mt-4" />
      <p className="mt-2 text-xs text-ink-muted">
        {badge.progress} of {badge.target}, {left} to go
      </p>
      <Link to="/rewards" className="mt-auto inline-flex min-h-10 items-center gap-1 pt-2 text-sm text-ink-soft underline underline-offset-2 hover:text-ink">
        All badges
        <ArrowUpRight aria-hidden="true" className="size-4" />
      </Link>
    </section>
  );
}

function DashboardSkeleton() {
  return (
    <div role="status" aria-label="Loading your dashboard" className="flex flex-col gap-5">
      <Skeleton className="h-80 rounded-[var(--radius-card)]" />
      <div className="grid gap-5 lg:grid-cols-2">
        <Skeleton className="h-72 rounded-[var(--radius-card)]" />
        <Skeleton className="h-72 rounded-[var(--radius-card)]" />
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const { profile, profileLoading, profileError, reloadProfile } = useProfile();
  const overview = useApi(() => fetchOverview(30), []);
  useDocumentTitle('Home');

  if (profileLoading && !profile) return <DashboardSkeleton />;
  if (!profile) return <ErrorState error={profileError} title="We couldn't load your progress" onRetry={reloadProfile} />;

  const { stats, limits } = profile;
  const firstRun = stats.total_sessions === 0;
  return (
    <div className="flex flex-col gap-5">
      <Hero profile={profile} name={user?.display_name?.split(' ')[0] ?? 'there'} />
      <DailyChallengeCard challenge={profile.daily_challenge} timeZone={user?.timezone} />

      <div className="grid gap-5 lg:grid-cols-[1fr_1.15fr]">
        <div className="flex flex-col gap-5">
          <section className="card p-5 sm:p-6">
            <LevelBlock profile={profile} />
            <dl className="mt-5 grid grid-cols-3 gap-3 border-t border-line pt-4 text-sm">
              <div>
                <dt className="text-ink-muted">Sparks</dt>
                <dd className="mt-0.5 font-display text-xl font-bold">
                  <SparksAmount amount={profile.sparks} />
                </dd>
              </div>
              <div>
                <dt className="text-ink-muted">Sessions</dt>
                <dd className="mt-0.5 font-display text-xl font-bold">{stats.total_sessions}</dd>
              </div>
              <div>
                <dt className="text-ink-muted">Best score</dt>
                <dd className="mt-0.5 font-display text-xl font-bold">{stats.best_score ?? '–'}</dd>
              </div>
            </dl>
          </section>
          {/* New users have no focus area yet, so their next badge fills that slot instead. */}
          {firstRun ? <NextBadge badge={profile.next_badge} /> : <FocusCard overview={overview} />}
        </div>
        <div className="flex flex-col gap-5">
          <Quests quests={profile.daily_quests} />
          {!firstRun && <NextBadge badge={profile.next_badge} />}
        </div>
      </div>

      <p className="text-center text-xs text-ink-muted">
        {limits.unlimited ? 'Unlimited stage time.' : `${humanDuration(limits.remaining_seconds)} of stage time left today.`}
        {!firstRun && ` ${humanDuration(stats.total_speaking_seconds)} spoken in total.`}
      </p>
    </div>
  );
}
