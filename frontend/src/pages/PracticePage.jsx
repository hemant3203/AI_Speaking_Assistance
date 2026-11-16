/**
 * Practice flow: setup, mic check, live stage, analyzing, reward reveal, results.
 * The hook owns the session's state. This page only decides which screen matches it.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import { CircleAlert, History as HistoryIcon, RotateCw, Shuffle } from 'lucide-react';
import { fetchCatalog, createSession, fetchSession } from '../api/practice';
import { fetchHealth } from '../api/system';
import { useAuth } from '../context/AuthContext';
import { useApi } from '../hooks/useApi';
import { useLiveCoach } from '../hooks/useLiveCoach';
import { useProfile } from '../components/layout/AppLayout';
import { Banner } from '../components/ui/Banner';
import { Button } from '../components/ui/Button';
import { PageHeader, useDocumentTitle } from '../components/ui/PageHeader';
import { ErrorState, PageSkeleton } from '../components/ui/States';
import { SKILL_BY_ID } from '../components/charts/chartTheme';
import { SetupStep, topicsFor } from '../components/practice/SetupStep';
import { MicCheckStep } from '../components/practice/MicCheckStep';
import { AnalyzingStage, LiveStage } from '../components/practice/LiveStage';
import { RewardReveal } from '../components/practice/RewardReveal';
import { CategoryScores, CoachFeedback, SpeechMetrics } from '../components/practice/Scorecard';
import { FollowUp } from '../components/practice/FollowUp';
import { GrammarCard } from '../components/practice/Grammar';
import { ChallengeResult, ComebackResult, RetakeCard } from '../components/practice/Comeback';
import { clock } from '../lib/format';

function randomTopic(mode, language, current) {
  const topics = topicsFor(mode, language).filter((topic) => topic !== current);
  return topics.length ? topics[Math.floor(Math.random() * topics.length)] : current ?? '';
}

function TooShortResult({ result, onTryAgain, onNewTopic }) {
  const { session, disqualified_reason: reason } = result;
  return (
    <section className="card p-6 text-center sm:p-10">
      <h2 className="text-3xl font-bold">Let's give that one more go</h2>
      <p className="mx-auto mt-3 max-w-md text-ink-soft">
        We need at least 20 seconds of speech and 15 words to give you a fair score, and this take came in at {clock(session.speaking_seconds)}. Nothing is lost, and short starts are how everyone begins.
      </p>
      {reason && <p className="mx-auto mt-2 max-w-md text-sm text-ink-muted">{reason}</p>}
      <p className="mx-auto mt-2 max-w-md text-sm text-ink-muted">If you did speak for longer, check that your mic wasn't muted.</p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        <Button size="lg" icon={RotateCw} onClick={onTryAgain}>
          Try again
        </Button>
        <Button size="lg" variant="secondary" icon={Shuffle} onClick={onNewTopic}>
          New topic
        </Button>
      </div>
    </section>
  );
}

function Results({ coach, result, onTryAgain, onNewTopic, onSetup }) {
  const { session, qualified } = result;
  const headingRef = useRef(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  return (
    <div className="flex flex-col gap-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <p className="kicker">Your scorecard</p>
          <h1 ref={headingRef} tabIndex={-1} className="mt-1 text-3xl font-bold outline-none sm:text-4xl">
            {qualified ? `${session.overall_score} out of 100` : 'That was a short one'}
          </h1>
          <p className="mt-1 text-ink-soft">{session.topic}</p>
        </div>
        {qualified && (
          <div className="flex flex-wrap gap-2">
            <Button icon={RotateCw} onClick={onTryAgain}>
              Retake to beat {session.overall_score}
            </Button>
            <Button variant="secondary" icon={Shuffle} onClick={onNewTopic}>
              New topic
            </Button>
          </div>
        )}
      </header>

      {coach.config.demo && (
        <Banner tone="demo" title="Demo mode">
          The coach is simulated for this session, so its feedback is sample text.
        </Banner>
      )}
      {coach.notice && <Banner tone="info">{coach.notice}</Banner>}
      {result.recovered && (
        <Banner tone="info" title="We lost the connection, but your speech is safe">
          Your score is saved and any rewards have been added to your profile. We just couldn't show the reveal this time.
        </Banner>
      )}

      {!qualified ? (
        <TooShortResult result={result} onTryAgain={onTryAgain} onNewTopic={onNewTopic} />
      ) : (
        <>
          <ComebackResult comeback={session.comeback} />
          <ChallengeResult challenge={session.challenge} />
          <div className="grid gap-5 lg:grid-cols-2">
            <CategoryScores scores={session.scores} />
            <SpeechMetrics session={session} />
          </div>
          <CoachFeedback session={session} onPractise={onSetup} />
          <GrammarCard session={session} />
          <FollowUp coach={coach} />
          <RetakeCard session={session} onRetake={onTryAgain} variant="secondary" />
          <div className="flex flex-wrap items-center gap-2">
            {coach.state === 'feedback' && (
              <Button variant="secondary" onClick={coach.endSession}>
                I'm done with the coach
              </Button>
            )}
            <Button variant="ghost" to={`/sessions/${session.id}`}>
              Open full session
            </Button>
            <Button variant="ghost" to="/">
              Back to home
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

function LiveError({ error, onSetup, onLogin }) {
  return (
    <div role="alert" className="card mx-auto flex max-w-lg flex-col items-center px-6 py-10 text-center">
      <CircleAlert aria-hidden="true" className="mb-3 size-8 text-danger" />
      <h1 className="text-2xl font-bold">{error.title}</h1>
      <p className="mt-2 text-ink-soft">{error.message}</p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        {error.action === 'login' && <Button onClick={onLogin}>Log in</Button>}
        {error.action === 'setup' && (
          <Button icon={RotateCw} onClick={onSetup}>
            Back to setup
          </Button>
        )}
        {error.action === 'history' && (
          <Button icon={HistoryIcon} to="/history">
            Go to History
          </Button>
        )}
        {error.action === 'home' && <Button to="/">Back to home</Button>}
      </div>
    </div>
  );
}

export default function PracticePage() {
  const [params] = useSearchParams();
  const { user, setUser } = useAuth();
  const { profile, reloadProfile } = useProfile();
  const catalog = useApi(fetchCatalog, []);
  const health = useApi(fetchHealth, []);
  const coach = useLiveCoach();

  const [step, setStep] = useState('setup');
  const [revealSeen, setRevealSeen] = useState(false);
  // `challenge` takes on today's challenge. `retryParent` is the scored session a second take tries to beat.
  const [form, setForm] = useState({ mode: '', topic: '', customTopic: false, freeTalk: false, shuffleRound: 0, target_seconds: 120, language: 'en', challenge: false, retryParent: null });
  const [busy, setBusy] = useState(false);
  const [createError, setCreateError] = useState(null);
  const [retryError, setRetryError] = useState(false);
  const location = useLocation();

  useDocumentTitle('Practice');

  const focusSkill = params.get('focus');
  const focusName = focusSkill ? SKILL_BY_ID[focusSkill]?.name ?? null : null;
  const modes = catalog.data?.modes;
  const modeById = useMemo(() => Object.fromEntries((modes ?? []).map((mode) => [mode.id, mode])), [modes]);

  // Apply the catalog once it loads. A "Practise this" link can preselect the mode.
  useEffect(() => {
    if (!modes?.length) return;
    setForm((prev) => {
      if (prev.mode) return prev;
      const wanted = params.get('mode');
      const mode = modes.find((item) => item.id === wanted) ?? modes[0];
      const durations = catalog.data.durations ?? [];
      return { ...prev, mode: mode.id, topic: randomTopic(mode, prev.language), target_seconds: durations.includes(120) ? 120 : durations[0] ?? 120 };
    });
  }, [catalog.data, modes, params]);

  const update = useCallback(
    (patch) => {
      setForm((prev) => {
        const next = { ...prev, ...patch };
        // Switching mode or language brings a fitting topic, unless the user wrote their own.
        const changed = next.mode !== prev.mode || next.language !== prev.language;
        if (changed && !prev.customTopic) next.topic = randomTopic(modeById[next.mode], next.language);
        return next;
      });
    },
    [modeById],
  );

  const shuffle = () =>
    setForm((prev) => ({ ...prev, customTopic: false, shuffleRound: prev.shuffleRound + 1, topic: randomTopic(modeById[prev.mode], prev.language, prev.topic) }));

  /** Create the session as late as possible, so a mic problem never burns stage time. */
  const begin = useCallback(
    async (values = form) => {
      coach.unlockAudio();
      setBusy(true);
      setCreateError(null);
      try {
        const parent = values.retryParent;
        let subject;
        if (parent) subject = { retry_of: parent.id };
        else if (values.challenge) subject = { challenge: true };
        else if (values.freeTalk) subject = { free_talk: true };
        else subject = { topic: values.topic.trim() };
        // On a second take the server repeats the first take's mode and language. These just match it.
        const session = await createSession({
          mode: parent?.mode ?? values.mode,
          ...subject,
          target_seconds: values.target_seconds,
          language: parent?.language ?? values.language,
        });
        coach.connect(session.id, values.target_seconds);
      } catch (error) {
        setCreateError(error);
      } finally {
        setBusy(false);
      }
    },
    [coach, form],
  );

  const backToSetup = useCallback(() => {
    coach.reset();
    setCreateError(null);
    setStep('setup');
  }, [coach]);

  /** Go again. After a scored take, that take becomes the one to beat, for a comeback bonus. */
  const tryAgain = useCallback(() => {
    const micIsOn = coach.mic.status === 'on';
    const last = coach.result?.qualified ? coach.result.session : null;
    const next = last ? { ...form, challenge: false, retryParent: last } : form;
    setForm(next);
    coach.reset({ keepMic: micIsOn });
    setCreateError(null);
    setStep('mic');
    if (micIsOn) begin(next);
  }, [begin, coach, form]);

  const newTopic = useCallback(() => {
    coach.reset();
    setForm((prev) => ({ ...prev, challenge: false, retryParent: null, customTopic: false, freeTalk: false, shuffleRound: prev.shuffleRound + 1, topic: randomTopic(modeById[prev.mode], prev.language, prev.topic) }));
    setStep('setup');
    window.scrollTo(0, 0);
  }, [coach, modeById]);

  // Clicking Practice in the nav, or a drill link, lands on this same route, so React keeps this page
  // mounted. Treat it as a request to start over, unless a speech is in progress behind the full-screen stage.
  const lastKey = useRef(location.key);
  useEffect(() => {
    if (location.key === lastKey.current) return;
    lastKey.current = location.key;
    const wanted = new URLSearchParams(location.search).get('mode');
    if (wanted && modeById[wanted]) update({ mode: wanted });
    if (coach.state === 'feedback' || coach.state === 'done' || coach.state === 'error') coach.reset();
    setStep('setup');
    // Only the navigation itself should trigger this.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.key]);

  // Links can start a daily challenge (?challenge=180) or a second take (?retry=<session id>).
  // Applied once per navigation. A plain visit to Practice leaves either one.
  const challengeInfo = profile?.daily_challenge;
  const appliedIntent = useRef(null);
  useEffect(() => {
    if (appliedIntent.current === location.key) return;
    const search = new URLSearchParams(location.search);
    const challengeSeconds = Number(search.get('challenge'));
    const retryId = search.get('retry');
    if (challengeSeconds) {
      if (!challengeInfo) return; // Waits for the profile, which holds today's challenge.
      appliedIntent.current = location.key;
      const lengths = challengeInfo.options.map((option) => option.target_seconds);
      setRetryError(false);
      setForm((prev) => ({
        ...prev,
        challenge: true,
        retryParent: null,
        freeTalk: false,
        mode: challengeInfo.mode,
        target_seconds: lengths.includes(challengeSeconds) ? challengeSeconds : lengths[0],
      }));
      return;
    }
    appliedIntent.current = location.key;
    setForm((prev) => (prev.challenge || prev.retryParent ? { ...prev, challenge: false, retryParent: null } : prev));
    if (!retryId) return;
    // Not cancelled by this effect's cleanup: the profile loading mid-fetch re-runs the effect, and
    // the take must still arrive. Only a newer navigation makes the answer stale.
    const requestKey = location.key;
    setRetryError(false);
    fetchSession(retryId)
      .then((parent) => {
        if (appliedIntent.current !== requestKey) return;
        if (parent.status !== 'completed') throw new Error('not scored');
        setForm((prev) => ({ ...prev, challenge: false, retryParent: parent, mode: parent.mode, language: parent.language, target_seconds: parent.target_seconds }));
      })
      .catch(() => appliedIntent.current === requestKey && setRetryError(true));
  }, [location.key, location.search, challengeInfo]);

  const leaveSpecial = useCallback(() => {
    setForm((prev) => ({ ...prev, challenge: false, retryParent: null, customTopic: false, topic: randomTopic(modeById[prev.mode], prev.language, prev.topic) }));
    setRetryError(false);
  }, [modeById]);

  const { result } = coach;
  useEffect(() => {
    if (!result) return;
    // Rewards changed on the server, so everything reading the profile needs fresh numbers.
    reloadProfile();
  }, [result, reloadProfile]);

  // Each new take earns its own reveal.
  useEffect(() => {
    if (coach.state === 'connecting') setRevealSeen(false);
  }, [coach.state]);

  const state = coach.state;
  let stageTopic = form.freeTalk ? 'Free talk' : form.topic;
  if (form.retryParent) stageTopic = form.retryParent.topic;
  else if (form.challenge && challengeInfo) stageTopic = form.language === 'hi' ? challengeInfo.topic_hi : challengeInfo.topic;
  if (state === 'connecting' || state === 'ready' || state === 'speaking') {
    return <LiveStage coach={coach} topic={stageTopic} onLeave={backToSetup} />;
  }
  if (state === 'analyzing') return <AnalyzingStage coach={coach} topic={stageTopic} />;
  if (state === 'error') return <LiveError error={coach.error} onSetup={backToSetup} onLogin={() => setUser(null)} />;
  if ((state === 'feedback' || state === 'done') && result) {
    // Decided during render, not in an effect: a too-short or recovered result has no rewards,
    // and the reveal must never get a chance to render with them missing.
    if (!revealSeen && result.qualified && result.rewards) {
      return (
        <RewardReveal
          result={result}
          onContinue={() => {
            setRevealSeen(true);
            window.scrollTo(0, 0);
          }}
        />
      );
    }
    return <Results coach={coach} result={result} onTryAgain={tryAgain} onNewTopic={newTopic} onSetup={backToSetup} />;
  }

  if (step === 'mic') {
    return (
      <>
        <PageHeader title="Check your mic" />
        <MicCheckStep
          coach={coach}
          topic={stageTopic}
          busy={busy}
          createError={createError}
          onBack={() => {
            coach.stopMic();
            setStep('setup');
          }}
          onConnect={() => begin()}
        />
      </>
    );
  }

  return (
    <>
      <PageHeader title="Set your stage" description="A few quick choices, then the light is yours." />
      {catalog.loading && <PageSkeleton />}
      {catalog.error && !catalog.data && <ErrorState error={catalog.error} title="We couldn't load the practice options" onRetry={catalog.reload} />}
      {catalog.data && (
        <SetupStep
          catalog={catalog.data}
          form={form}
          update={update}
          onShuffle={shuffle}
          onContinue={() => setStep('mic')}
          profile={profile}
          equippedCoach={user?.equipped_coach}
          // Only an explicit "false" blocks practice. If the check itself failed, let the user try.
          coachAvailable={health.data?.coach_available !== false}
          focusName={focusName}
          onLeaveSpecial={leaveSpecial}
          retryError={retryError}
        />
      )}
    </>
  );
}
