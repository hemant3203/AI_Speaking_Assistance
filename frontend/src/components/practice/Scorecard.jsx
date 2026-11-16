/** Everything measured about one speech. Shared by the practice results and the session detail page. */
import { Link } from 'react-router-dom';
import { ArrowUpRight, Check, Dumbbell, Info, MoveRight } from 'lucide-react';
import { Banner } from '../ui/Banner';
import { ProgressBar } from '../ui/ProgressBar';
import { SKILLS } from '../charts/chartTheme';
import { clock, oneDecimal, rounded } from '../../lib/format';

export function CategoryScores({ scores = {} }) {
  return (
    <section className="card p-5 sm:p-6">
      <h2 className="text-xl font-bold">Skill by skill</h2>
      <ul className="mt-4 flex flex-col gap-3.5">
        {SKILLS.map((skill) => {
          const value = scores?.[skill.id];
          const missing = value === null || value === undefined;
          return (
            <li key={skill.id} className="grid grid-cols-[6.5rem_1fr_2.25rem] items-center gap-3 text-sm sm:grid-cols-[8rem_1fr_2.5rem]">
              <span className="text-ink-soft">{skill.name}</span>
              {missing ? (
                <span className="col-span-2 text-xs text-ink-muted">Not scored this time</span>
              ) : (
                <>
                  <ProgressBar value={value} label={`${skill.name}: ${value} out of 100`} />
                  <span className="text-right font-semibold tabular-nums">{value}</span>
                </>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Metric({ label, value, note }) {
  return (
    <div className="min-w-0 rounded-xl bg-raised p-3.5">
      <dt className="text-xs text-ink-soft">{label}</dt>
      <dd className="mt-0.5 font-display text-2xl font-bold leading-tight">{value}</dd>
      {note && <dd className="mt-0.5 text-xs text-ink-muted">{note}</dd>}
    </div>
  );
}

function paceNote(wpm) {
  if (wpm === null || wpm === undefined) return null;
  if (wpm < 120) return 'A little slow. Aim for 120 to 160';
  if (wpm > 160) return 'A little fast. Aim for 120 to 160';
  return 'In the comfortable range';
}

export function SpeechMetrics({ session }) {
  const breakdown = Object.entries(session.filler_breakdown ?? {}).sort((a, b) => b[1] - a[1]);
  return (
    <section className="card p-5 sm:p-6">
      <h2 className="text-xl font-bold">The numbers</h2>
      <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Metric label="Speaking time" value={clock(session.speaking_seconds)} note={session.target_seconds ? `Target ${clock(session.target_seconds)}` : null} />
        <Metric label="Words per minute" value={rounded(session.wpm)} note={paceNote(session.wpm)} />
        <Metric label="Words" value={rounded(session.word_count)} />
        <Metric label="Fillers" value={rounded(session.filler_count)} note={`${oneDecimal(session.filler_per_100)} per 100 words`} />
        <Metric label="Hedges" value={rounded(session.hedge_count)} note={session.language === 'hi' ? 'शायद, लगता है, हो सकता है' : 'Maybe, sort of, I think'} />
        <Metric label="Pauses" value={rounded(session.pause_count)} note={session.longest_pause_seconds ? `Longest ${oneDecimal(session.longest_pause_seconds)}s` : null} />
      </dl>
      {breakdown.length > 0 && (
        <div className="mt-4">
          <h3 className="font-sans text-sm font-semibold tracking-normal text-ink-soft">Filler words you used</h3>
          <ul className="mt-2 flex flex-wrap gap-2">
            {breakdown.map(([word, count]) => (
              <li key={word} className="rounded-lg border border-line px-2.5 py-1 text-sm">
                {word} <span className="font-semibold tabular-nums">{count}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {session.filler_counts_reliable === false && (
        <p className="mt-3 flex items-start gap-2 text-sm text-ink-muted">
          <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          Filler counts may be low for this session, because they came from a transcript that tidies speech up.
        </p>
      )}
    </section>
  );
}

/** `onPractise` replaces the link when already on the practice page, where a link would change nothing. */
export function CoachFeedback({ session, onPractise }) {
  const feedback = session.feedback;
  if (!feedback) {
    return session.ai_scored === false ? (
      <Banner tone="info" title="Detailed coaching wasn't available this time">
        Our scoring service was busy, so this score comes from your pace, pauses and word use only, and filler counts may be low. It still counts towards your progress.
      </Banner>
    ) : null;
  }
  return (
    <section className="card p-5 sm:p-6">
      <h2 className="text-xl font-bold">What your coach noticed</h2>
      <p className="mt-3 text-ink-soft">{feedback.summary}</p>
      <div className="mt-5 grid gap-5 sm:grid-cols-2">
        <div>
          <h3 className="font-sans text-sm font-semibold tracking-normal">What worked</h3>
          <ul className="mt-2 flex flex-col gap-2 text-sm text-ink-soft">
            {(feedback.strengths ?? []).map((item) => (
              <li key={item} className="flex gap-2">
                <Check aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-mint" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="font-sans text-sm font-semibold tracking-normal">What to work on</h3>
          <ul className="mt-2 flex flex-col gap-2 text-sm text-ink-soft">
            {(feedback.improvements ?? []).map((item) => (
              <li key={item} className="flex gap-2">
                <MoveRight aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-ink-muted" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      {feedback.next_drill && (
        <div className="mt-5 flex gap-3 rounded-xl bg-raised p-4">
          <Dumbbell aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-ink-soft" />
          <div>
            <h3 className="font-sans text-sm font-semibold tracking-normal">Your next drill</h3>
            <p className="mt-1 text-sm text-ink-soft">{feedback.next_drill}</p>
            {onPractise ? (
              <button type="button" onClick={onPractise} className="mt-2 inline-flex min-h-10 items-center gap-1 text-sm font-semibold underline underline-offset-2 hover:text-amber-bright">
                Practise this
                <ArrowUpRight aria-hidden="true" className="size-4" />
              </button>
            ) : (
              <Link to={`/practice?mode=${encodeURIComponent(session.mode)}`} className="mt-2 inline-flex min-h-10 items-center gap-1 text-sm font-semibold underline underline-offset-2 hover:text-amber-bright">
                Practise this
                <ArrowUpRight aria-hidden="true" className="size-4" />
              </Link>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
