/** One past session in full. Deleting removes the record, but XP and badges already earned stay. */
import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, FileQuestion, RotateCcw, Swords, Trash2 } from 'lucide-react';
import { deleteSession, fetchSession } from '../api/practice';
import { useToast } from '../context/ToastContext';
import { useApi } from '../hooks/useApi';
import { Banner } from '../components/ui/Banner';
import { Button } from '../components/ui/Button';
import { Dialog } from '../components/ui/Dialog';
import { useDocumentTitle } from '../components/ui/PageHeader';
import { EmptyState, ErrorState, PageSkeleton } from '../components/ui/States';
import { CategoryScores, CoachFeedback, SpeechMetrics } from '../components/practice/Scorecard';
import { GrammarCard, HighlightedTranscript } from '../components/practice/Grammar';
import { ChallengeResult, ComebackResult, RetakeCard } from '../components/practice/Comeback';
import { clock, longDate } from '../lib/format';

const MODE_NAMES = { impromptu: 'Impromptu', presentation: 'Presentation', interview: 'Interview', storytelling: 'Storytelling', persuasion: 'Persuasion' };

function TranscriptBlock({ title, text, empty, slips }) {
  const marked = Boolean(text && slips?.length);
  return (
    <section className="card p-5 sm:p-6">
      <h2 className="text-xl font-bold">{title}</h2>
      {marked && <p className="mt-1 text-sm text-ink-muted">Grammar slips are underlined and numbered to match your fixes above. Hover one to see the better version.</p>}
      {text ? (
        <div className="mt-3 max-h-96 overflow-y-auto whitespace-pre-wrap leading-relaxed text-ink-soft" tabIndex={0} role="region" aria-label={title}>
          {marked ? <HighlightedTranscript text={text} issues={slips} /> : text}
        </div>
      ) : (
        <p className="mt-3 text-sm text-ink-muted">{empty}</p>
      )}
    </section>
  );
}

export default function SessionDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { data: session, loading, error, reload } = useApi(() => fetchSession(id), [id]);
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  useDocumentTitle('Session');

  const back = (
    <Button variant="ghost" size="sm" icon={ArrowLeft} to="/history" className="-ml-3 mb-3">
      History
    </Button>
  );

  if (loading) return <PageSkeleton />;
  if (error?.status === 404) {
    return (
      <EmptyState icon={FileQuestion} title="We can't find that session" action={<Button to="/history">Back to History</Button>}>
        It may have been deleted, or the link may be wrong.
      </EmptyState>
    );
  }
  if (error || !session) {
    return (
      <>
        {back}
        <ErrorState error={error} title="We couldn't load this session" onRetry={reload} />
      </>
    );
  }

  const remove = async () => {
    setDeleting(true);
    try {
      await deleteSession(session.id);
      toast.success('Session deleted. Your XP and badges are still yours.');
      navigate('/history', { replace: true });
    } catch (err) {
      toast.error(err.message);
      setDeleting(false);
      setConfirming(false);
    }
  };

  const scored = session.status === 'completed';
  return (
    <div className="flex flex-col gap-5">
      <div>
        {back}
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <p className="kicker flex flex-wrap items-center gap-x-2 gap-y-1">
              <span>
                {MODE_NAMES[session.mode] ?? session.mode} · {longDate(session.local_date)}
              </span>
              {session.challenge_date && (
                <span className="inline-flex items-center gap-1 rounded-md border border-line px-1.5 py-0.5 normal-case tracking-normal">
                  <Swords aria-hidden="true" className="size-3.5" />
                  Daily challenge
                </span>
              )}
              {session.retry_of && (
                <Link to={`/sessions/${encodeURIComponent(session.retry_of)}`} className="inline-flex items-center gap-1 rounded-md border border-line px-1.5 py-0.5 normal-case tracking-normal underline-offset-2 hover:text-ink hover:underline">
                  <RotateCcw aria-hidden="true" className="size-3.5" />
                  Second take
                </Link>
              )}
            </p>
            <h1 className="mt-1 text-3xl font-bold sm:text-4xl">{session.topic}</h1>
          </div>
          {scored && (
            <div className="shrink-0 text-right">
              <p className="font-display text-6xl font-bold leading-none tracking-tight">{session.overall_score}</p>
              <p className="mt-1 text-sm text-ink-soft">out of 100</p>
              {session.xp_awarded > 0 && <p className="mt-1 text-sm font-medium text-mint">+{session.xp_awarded} XP</p>}
            </div>
          )}
        </header>
      </div>

      {session.status === 'too_short' && (
        <Banner tone="info" title="This take was too short to score">
          It came in at {clock(session.speaking_seconds)}. We need at least 20 seconds of speech and 15 words.
        </Banner>
      )}

      {scored && (
        <>
          <ComebackResult comeback={session.comeback} />
          <ChallengeResult challenge={session.challenge} />
          <CoachFeedback session={session} />
          <GrammarCard session={session} />
          <div className="grid gap-5 lg:grid-cols-2">
            <CategoryScores scores={session.scores} />
            <SpeechMetrics session={session} />
          </div>
        </>
      )}

      <TranscriptBlock title="What you said" text={session.transcript} slips={session.feedback?.grammar?.issues} empty="We don't have a transcript for this session." />
      {scored && <RetakeCard session={session} />}
      <TranscriptBlock title="What your coach said" text={session.coach_transcript} empty="Your coach didn't say anything out loud this time." />

      <div>
        <Button variant="secondary" icon={Trash2} onClick={() => setConfirming(true)}>
          Delete this session
        </Button>
      </div>

      <Dialog open={confirming} onClose={() => setConfirming(false)} title="Delete this session?">
        <p className="text-sm text-ink-soft">Its scores and transcript will be gone for good. You'll keep the XP and badges you earned from it.</p>
        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <Button variant="secondary" onClick={() => setConfirming(false)}>
            Keep it
          </Button>
          <Button variant="danger" loading={deleting} onClick={remove}>
            Delete
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
