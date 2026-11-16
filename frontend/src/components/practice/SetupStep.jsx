/** First step of practice: choose how, what and how long, before any session is created. */
import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, MessageCircle, RotateCcw, Shuffle, Swords, Target, UserRound } from 'lucide-react';
import { Button } from '../ui/Button';
import { Banner } from '../ui/Banner';
import { DynamicIcon } from '../ui/DynamicIcon';
import { TextField } from '../ui/Field';
import { Segmented } from '../ui/Segmented';
import { clock, humanDuration } from '../../lib/format';

const COACH_NAMES = { mentor: 'The Mentor', hype: 'The Hype Coach', storyteller: 'The Storyteller', critic: 'The Critic' };

export const coachName = (id) => COACH_NAMES[id] ?? 'Your coach';

/** The suggested topics for a mode, in the language the user will speak. */
export const topicsFor = (mode, language) => (language === 'hi' ? mode?.topics_hi : mode?.topics) ?? [];

const VISIBLE_SUGGESTIONS = 6;

function shuffled(items) {
  const copy = [...items];
  for (let index = copy.length - 1; index > 0; index -= 1) {
    const other = Math.floor(Math.random() * (index + 1));
    [copy[index], copy[other]] = [copy[other], copy[index]];
  }
  return copy;
}

function durationLabel(seconds) {
  return seconds % 60 === 0 ? `${seconds / 60} min` : `${seconds}s`;
}

/** A second take: the same speech again, with last time's fixes to hand. */
function RetakeSetup({ parent, onLeave }) {
  const grammar = parent.feedback?.grammar;
  const fixes = grammar?.issues?.slice(0, 5) ?? [];
  return (
    <section aria-labelledby="retake-setup-heading" className="card p-5 sm:p-6">
      <p className="kicker flex items-center gap-1.5">
        <RotateCcw aria-hidden="true" className="size-4" />
        Second take
      </p>
      <h2 id="retake-setup-heading" className="mt-1 text-2xl font-bold">
        {parent.topic}
      </h2>
      <dl className="mt-4 flex flex-wrap gap-3">
        <div className="rounded-xl bg-raised px-4 py-2.5">
          <dt className="text-xs text-ink-soft">Score to beat</dt>
          <dd className="font-display text-2xl font-bold">{parent.overall_score}</dd>
        </div>
        {grammar && (
          <div className="rounded-xl bg-raised px-4 py-2.5">
            <dt className="text-xs text-ink-soft">Grammar to beat</dt>
            <dd className="font-display text-2xl font-bold">{grammar.score}</dd>
          </div>
        )}
      </dl>
      {fixes.length > 0 && (
        <>
          <h3 className="mt-5 font-sans text-sm font-semibold tracking-normal">Say these the right way this time</h3>
          <ul className="mt-2 flex flex-col gap-2 text-sm">
            {fixes.map((issue, index) => (
              <li key={`${issue.said}-${index}`} className="flex flex-wrap items-baseline gap-x-2 rounded-lg bg-raised px-3 py-2">
                <span className="sr-only">Instead of </span>
                <span className="text-ink-muted line-through decoration-danger/80">{issue.said}</span>
                <ArrowRight aria-hidden="true" className="size-3.5 self-center text-ink-muted" />
                <span className="sr-only">say </span>
                <span className="font-semibold">{issue.better}</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-ink-muted">Read each one out loud before you start. Your coach will listen for them.</p>
        </>
      )}
      <button type="button" onClick={onLeave} className="mt-4 inline-flex min-h-10 items-center text-sm text-ink-soft underline underline-offset-2 hover:text-ink">
        Choose a different topic instead
      </button>
    </section>
  );
}

/** Today's challenge, in the language the speaker chose. */
function ChallengeSetup({ challenge, language, targetSeconds, onLeave }) {
  const option = challenge.options.find((item) => item.target_seconds === targetSeconds);
  return (
    <section aria-labelledby="challenge-setup-heading" className="card p-5 sm:p-6">
      <p className="kicker flex items-center gap-1.5">
        <Swords aria-hidden="true" className="size-4" />
        Daily challenge · {challenge.mode_name}
      </p>
      <h2 id="challenge-setup-heading" lang={language} className="mt-1 text-2xl font-bold">
        {language === 'hi' ? challenge.topic_hi : challenge.topic}
      </h2>
      {challenge.completed ? (
        <p className="mt-2 text-sm text-ink-soft">You’ve already completed today’s challenge, so this take is extra practice. You still earn the usual XP.</p>
      ) : (
        option && (
          <p className="mt-2 text-sm text-ink-soft">
            Speak for at least {clock(option.min_seconds)} to complete it and earn <span className="font-semibold text-mint">+{option.xp} XP</span> on top of your usual rewards.
          </p>
        )
      )}
      <button type="button" onClick={onLeave} className="mt-3 inline-flex min-h-10 items-center text-sm text-ink-soft underline underline-offset-2 hover:text-ink">
        Choose my own topic instead
      </button>
    </section>
  );
}

export function SetupStep({ catalog, form, update, onShuffle, onContinue, profile, equippedCoach, coachAvailable, focusName, onLeaveSpecial, retryError }) {
  const challenge = profile?.daily_challenge;
  const special = form.retryParent ? 'retake' : form.challenge && challenge ? 'challenge' : null;
  const selectedMode = catalog.modes.find((mode) => mode.id === form.mode);
  const remaining = profile?.limits?.remaining_seconds;
  const unlimited = profile?.limits?.unlimited;
  const outOfTime = remaining !== undefined && remaining <= 0;
  const topicError = form.topic.length > 200 ? 'Topics can be up to 200 characters.' : null;
  const topicValid = Boolean(special) || form.freeTalk || (form.topic.trim().length >= 3 && !topicError);
  const durationOptions =
    special === 'challenge'
      ? challenge.options.map((option) => ({ value: option.target_seconds, label: `${durationLabel(option.target_seconds)} · +${option.xp} XP` }))
      : catalog.durations.map((seconds) => ({ value: seconds, label: durationLabel(seconds) }));
  // A fresh set for each mode, language and press of Shuffle, not the same few every time.
  const suggestionPool = useMemo(
    () => shuffled(topicsFor(selectedMode, form.language)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [selectedMode, form.language, form.shuffleRound],
  );
  const suggestions = suggestionPool.filter((topic) => topic !== form.topic).slice(0, VISIBLE_SUGGESTIONS);

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (topicValid && !outOfTime && coachAvailable) onContinue();
      }}
      className="flex flex-col gap-8"
    >
      {retryError && (
        <Banner tone="warning" title="We couldn't load that take">
          It may have been deleted. You can still practise any topic below.
        </Banner>
      )}
      {focusName && !special && (
        <Banner tone="info" title={`Let's work on ${focusName.toLowerCase()}`}>
          We picked the mode that drills it best. Change anything you like.
        </Banner>
      )}
      {!coachAvailable && (
        <Banner tone="warning" title="The coach is unavailable right now">
          Practice needs the live coach, and we can't reach it at the moment. Your progress is safe. Please try again in a few minutes.
        </Banner>
      )}
      {outOfTime && (
        <Banner tone="warning" title="That's today's stage time">
          You've used all your practice minutes for today. They reset at midnight your time, and your streak is safe if you've already practised.
        </Banner>
      )}

      {special === 'retake' && <RetakeSetup parent={form.retryParent} onLeave={onLeaveSpecial} />}

      {special !== 'retake' && (
        <Segmented
          legend="Which language will you speak?"
          legendClassName="mb-3 font-display text-xl font-bold"
          value={form.language}
          onChange={(value) => update({ language: value })}
          options={catalog.languages.map((language) => ({ value: language.id, label: language.name }))}
        />
      )}

      {special === 'challenge' && <ChallengeSetup challenge={challenge} language={form.language} targetSeconds={form.target_seconds} onLeave={onLeaveSpecial} />}

      {!special && (
      <>
      <fieldset>
        <legend className="mb-3 font-display text-xl font-bold">How do you want to speak?</legend>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {catalog.modes.map((mode) => {
            const selected = mode.id === form.mode;
            return (
              <label
                key={mode.id}
                className={`relative flex cursor-pointer gap-3 rounded-2xl border p-4 transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-amber-bright ${
                  selected ? 'border-amber bg-raised' : 'border-line bg-surface hover:border-line-strong'
                }`}
              >
                <input type="radio" name="mode" value={mode.id} checked={selected} onChange={() => update({ mode: mode.id })} className="sr-only" />
                <span className={`flex size-11 shrink-0 items-center justify-center rounded-xl ${selected ? 'bg-amber text-on-amber' : 'bg-raised text-ink-soft'}`}>
                  <DynamicIcon name={mode.icon} fallback={Target} className="size-5" />
                </span>
                <span className="min-w-0">
                  <span className="block font-semibold">{mode.name}</span>
                  <span className="mt-0.5 block text-sm text-ink-soft">{mode.description}</span>
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>

      <div>
        <h2 className="mb-3 text-xl font-bold">What will you talk about?</h2>
        <Segmented
          legend="Choose a topic or talk freely"
          legendHidden
          className="mb-4"
          value={form.freeTalk ? 'free' : 'topic'}
          onChange={(value) => update({ freeTalk: value === 'free' })}
          options={[
            { value: 'topic', label: 'Choose a topic' },
            { value: 'free', label: 'Free talk' },
          ]}
        />
        {form.freeTalk ? (
          <div className="flex gap-3 rounded-2xl border border-line bg-surface p-4">
            <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-raised text-ink-soft">
              <MessageCircle aria-hidden="true" className="size-5" />
            </span>
            <span className="min-w-0">
              <span className="block font-semibold">Talk about anything you like</span>
              <span className="mt-0.5 block text-sm text-ink-soft">
                No set topic. Just start speaking, and you'll still get your full scorecard and coach feedback. Your coach works out what you talked about.
              </span>
            </span>
          </div>
        ) : (
          <>
        <div className="flex items-end gap-2">
          <div className="min-w-0 flex-1">
            <TextField
              label="Topic"
              value={form.topic}
              onChange={(event) => update({ topic: event.target.value, customTopic: true })}
              error={topicError}
              hint="Pick one below, shuffle, or type your own."
              maxLength={220}
              placeholder="Type your own topic"
              autoComplete="off"
            />
          </div>
          {/* The field's hint sits under the input, so nudge the button up to line up with the input. */}
          <Button variant="secondary" icon={Shuffle} onClick={onShuffle} className="mb-[1.875rem] shrink-0" aria-label="Shuffle topic">
            <span className="hidden sm:inline">Shuffle</span>
          </Button>
        </div>
        {suggestions.length > 0 && (
          <ul className="mt-3 flex flex-col items-start gap-2 sm:flex-row sm:flex-wrap">
            {suggestions.map((topic) => (
              <li key={topic} className="max-w-full">
                <button
                  type="button"
                  onClick={() => update({ topic, customTopic: false })}
                  className="min-h-9 rounded-lg border border-line px-3 py-1.5 text-left text-sm text-ink-soft transition-colors hover:border-line-strong hover:text-ink"
                >
                  {topic}
                </button>
              </li>
            ))}
          </ul>
        )}
          </>
        )}
      </div>
      </>
      )}

      <Segmented
        legend={special === 'challenge' ? 'Choose your distance' : 'Target length'}
        value={form.target_seconds}
        onChange={(value) => update({ target_seconds: Number(value) })}
        options={durationOptions}
      />
      {!unlimited && remaining > 0 && remaining < form.target_seconds && (
        <p className="-mt-5 text-sm text-ink-soft">You have {humanDuration(remaining)} of stage time left today, so this take would stop there.</p>
      )}

      <div className="card flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
        <div className="flex items-center gap-3">
          <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-raised">
            <UserRound aria-hidden="true" className="size-5 text-ink-soft" />
          </span>
          <div className="min-w-0 text-sm">
            <p className="font-semibold text-ink">{coachName(equippedCoach)} is your coach</p>
            <p className="text-ink-soft">
              {unlimited ? <>Unlimited stage time. </> : remaining !== undefined && <>{humanDuration(remaining)} of stage time left today. </>}
              <Link to="/rewards?tab=shop" className="underline underline-offset-2 hover:text-ink">
                Change coach
              </Link>
            </p>
          </div>
        </div>
        <Button type="submit" size="lg" icon={ArrowRight} disabled={!topicValid || outOfTime || !coachAvailable} className="w-full shrink-0 sm:w-auto">
          Next: check your mic
        </Button>
      </div>
    </form>
  );
}
