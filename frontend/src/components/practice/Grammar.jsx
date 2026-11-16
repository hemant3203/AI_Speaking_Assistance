/**
 * Grammar coaching for one speech: which kind of slip to focus on first, each slip with its fix and
 * the rule behind it, and the slips marked in the transcript so the speaker sees them in context.
 */
import { ArrowRight, CircleCheck, SpellCheck } from 'lucide-react';
import { plural } from '../../lib/format';

/** Names and tips for the slip types the analysis returns. Tips are for English speeches. */
export const GRAMMAR_TYPES = {
  tense: { name: 'Verb tense', tip: 'Pick one time frame and stay in it. A story about yesterday stays in the past: "we went", "we ate", "it was".' },
  agreement: { name: 'Agreement', tip: 'Match the verb to its subject: "the sun rises", "she goes", "they go". Check every he, she and it.' },
  articles: { name: 'Articles', tip: 'Use "a" for something new, "the" for something your listener already knows, and nothing before most names.' },
  prepositions: { name: 'Prepositions', tip: 'Learn them as pairs with their words: "on that day", "at the festival", "after Diwali", "in the morning".' },
  word_order: { name: 'Word order', tip: 'Inside a longer sentence, a question keeps statement order: "I will tell you how it happened".' },
  word_choice: { name: 'Word choice', tip: 'Reach for the word a listener expects, and say it once instead of repeating it for emphasis.' },
  plurals: { name: 'Singular and plural', tip: 'Add -s for more than one, and match "this or these" and "is or are" to the count.' },
  sentence: { name: 'Sentence structure', tip: 'Finish one sentence before you start the next. Pause at the full stop instead of joining ideas with "and".' },
  other: { name: 'Other', tip: 'Read the fixes below out loud once, so the corrected version is the one that comes out next time.' },
};

const typeName = (type) => GRAMMAR_TYPES[type]?.name ?? GRAMMAR_TYPES.other.name;

function verdict(score, slips) {
  if (slips === 0) return 'No grammar slips spotted. Your sentences were clean.';
  if (score >= 90) return 'Nearly flawless. Polish the last few slips and this is spotless.';
  if (score >= 75) return 'Mostly correct, with a few slips worth tidying up.';
  if (score >= 55) return 'Easy to understand, but the slips below get noticed. Start with the top focus.';
  return 'Grammar is holding this speech back. Fix one pattern at a time, starting with the top focus.';
}

/** The slip types ranked by how often they came up. */
function focusAreas(issues) {
  const counts = new Map();
  issues.forEach((issue) => counts.set(issue.type, (counts.get(issue.type) ?? 0) + 1));
  return [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([type, count]) => ({ type, count }));
}

export function GrammarCard({ session }) {
  const grammar = session.feedback?.grammar;
  if (!grammar) return null;
  const issues = grammar.issues ?? [];
  const focus = focusAreas(issues).slice(0, 3);
  const showTips = session.language !== 'hi';

  return (
    <section aria-labelledby="grammar-heading" className="card p-5 sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 id="grammar-heading" className="flex items-center gap-2 text-xl font-bold">
            <SpellCheck aria-hidden="true" className="size-5 text-ink-soft" />
            Grammar check
          </h2>
          <p className="mt-2 text-ink-soft">{verdict(grammar.score, issues.length)}</p>
        </div>
        <div className="shrink-0 text-right">
          <p className="font-display text-4xl font-bold leading-none">{grammar.score}</p>
          <p className="mt-1 text-xs text-ink-muted">grammar, out of 100</p>
        </div>
      </div>

      {issues.length === 0 ? (
        <p className="mt-4 flex items-center gap-2 rounded-xl bg-raised p-4 text-sm">
          <CircleCheck aria-hidden="true" className="size-5 shrink-0 text-good" />
          Keep it up. Grammar is a strength in this take.
        </p>
      ) : (
        <>
          <h3 className="mt-5 font-sans text-sm font-semibold tracking-normal">Where to focus</h3>
          <ol className="mt-2 grid gap-3 sm:grid-cols-3">
            {focus.map(({ type, count }, index) => (
              <li key={type} className={`rounded-xl p-3.5 ${index === 0 ? 'border border-line-strong bg-raised' : 'bg-raised'}`}>
                {index === 0 && <p className="kicker text-amber-bright">Start here</p>}
                <p className="font-semibold">{typeName(type)}</p>
                <p className="text-xs text-ink-muted">{plural(count, 'slip')}</p>
                {showTips && <p className="mt-2 text-sm text-ink-soft">{GRAMMAR_TYPES[type]?.tip ?? GRAMMAR_TYPES.other.tip}</p>}
              </li>
            ))}
          </ol>

          <h3 className="mt-6 font-sans text-sm font-semibold tracking-normal">Your fixes</h3>
          <ol className="mt-2 flex flex-col divide-y divide-line">
            {issues.map((issue, index) => (
              <li key={`${issue.said}-${index}`} id={`slip-${index + 1}`} className="flex gap-3 py-3 first:pt-1 last:pb-0">
                <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-raised text-xs font-bold tabular-nums">{index + 1}</span>
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                    <span className="sr-only">You said: </span>
                    <span className="text-ink-muted line-through decoration-danger/80 decoration-2">{issue.said}</span>
                    <ArrowRight aria-hidden="true" className="size-4 shrink-0 self-center text-ink-muted" />
                    <span className="sr-only">Better: </span>
                    <span className="font-semibold text-ink">{issue.better}</span>
                  </p>
                  {issue.why && <p className="mt-1 text-sm text-ink-soft">{issue.why}</p>}
                  <p className="mt-1.5 inline-block rounded-md border border-line px-2 py-0.5 text-xs text-ink-muted">{typeName(issue.type)}</p>
                </div>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}

const WORD_EDGE = /^[^\p{L}\p{M}\p{N}]+|[^\p{L}\p{M}\p{N}]+$/gu;
const escapeRegex = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/**
 * Find each slip in the transcript. Words are matched ignoring case and the punctuation between them,
 * because the model's quote and its transcript don't always agree on commas. Marks never overlap.
 */
export function locateSlips(text, issues) {
  const ranges = [];
  issues.forEach((issue, index) => {
    const words = issue.said.split(/\s+/).map((word) => word.replace(WORD_EDGE, '')).filter(Boolean);
    if (!words.length) return;
    let pattern;
    try {
      pattern = new RegExp(words.map(escapeRegex).join('[^\\p{L}\\p{M}\\p{N}]+'), 'giu');
    } catch {
      return;
    }
    for (const match of text.matchAll(pattern)) {
      const start = match.index;
      const end = start + match[0].length;
      if (!ranges.some((range) => start < range.end && end > range.start)) {
        ranges.push({ start, end, number: index + 1, better: issue.better });
        break;
      }
    }
  });
  return ranges.sort((a, b) => a.start - b.start);
}

export function HighlightedTranscript({ text, issues = [] }) {
  const ranges = locateSlips(text, issues);
  const parts = [];
  let cursor = 0;
  ranges.forEach((range) => {
    if (range.start > cursor) parts.push(text.slice(cursor, range.start));
    parts.push(
      <mark key={range.start} title={`Better: ${range.better}`} className="rounded-sm bg-warning/15 text-ink underline decoration-warning decoration-wavy underline-offset-4">
        {text.slice(range.start, range.end)}
        <sup className="ml-0.5 text-[0.65rem] font-bold text-warning">
          <span className="sr-only"> (grammar slip </span>
          {range.number}
          <span className="sr-only">, better: {range.better})</span>
        </sup>
      </mark>,
    );
    cursor = range.end;
  });
  if (cursor < text.length) parts.push(text.slice(cursor));
  return parts;
}
