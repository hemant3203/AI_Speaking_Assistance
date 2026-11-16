"""Language metrics computed locally from a transcript.

Tokenising is by whitespace after removing punctuation, because the regex class `\\w` treats Devanagari
vowel signs as word boundaries and would split most Hindi words in pieces.
"""
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

_SINGLE_WORD_FILLERS = frozenset({
    # English
    "um", "umm", "ummm", "uh", "uhh", "uhm", "er", "erm", "ah", "hmm", "mm", "like", "basically",
    "actually", "literally",
    # Hindi, in Roman script
    "matlab", "yaani", "yani",
    # Hindi, in Devanagari. तो, बस, अच्छा and हाँ are left out: they are normal grammar in most Hindi
    # sentences, so counting them would penalise people for speaking correctly.
    "मतलब", "यानी", "यानि", "अ", "अह", "उम", "उम्", "अं", "अम", "अम्", "आं", "हम्म", "बेसिकली", "एक्चुअली", "लाइक",
})
_FILLER_PHRASES = (("you", "know"), ("i", "mean"), ("you", "see"))

_SINGLE_WORD_HEDGES = frozenset({
    "maybe", "perhaps", "probably", "possibly", "might", "kinda", "sorta", "shayad", "शायद",
})
_HEDGE_PHRASES = (
    ("ho", "sakta", "hai"),
    ("हो", "सकता", "है"),
    ("i", "think"),
    ("i", "guess"),
    ("i", "suppose"),
    ("sort", "of"),
    ("kind", "of"),
    ("lagta", "hai"),
    ("लगता", "है"),
)

# "like" is a filler in "it was, like, huge" but not in "I like this" or "it looks like rain", and
# मतलब is a filler in "मैं, मतलब, ..." but not in "इसका मतलब" ("this means").
# Punctuation is gone by now, so the preceding word is the only clue we have left.
_LIKE_AS_REAL_WORD_AFTER = frozenset({
    "i", "we", "you", "they", "would", "look", "looks", "looked", "feel", "feels", "felt", "sound",
    "sounds", "seem", "seems", "something", "anything", "nothing", "things", "people", "not", "dont",
    "don't", "didn't", "much", "more", "just",
})
_MATLAB_AS_REAL_WORD_AFTER = frozenset({
    "का", "इसका", "उसका", "जिसका", "क्या", "कोई", "ka", "iska", "uska", "jiska", "kya", "koi",
})
_REAL_WORD_AFTER = {
    "like": _LIKE_AS_REAL_WORD_AFTER,
    "मतलब": _MATLAB_AS_REAL_WORD_AFTER,
    "matlab": _MATLAB_AS_REAL_WORD_AFTER,
}

_KEEP_INSIDE_WORDS = frozenset("'-")
_ZERO_WIDTH_JOINERS = dict.fromkeys(map(ord, "‌‍"))


@dataclass(frozen=True)
class TextMetrics:
    """Language measurements for one transcript."""

    word_count: int = 0
    wpm: float | None = None
    filler_count: int = 0
    filler_per_100: float = 0.0
    filler_breakdown: dict[str, int] = field(default_factory=dict)
    hedge_count: int = 0
    hedges_per_100: float = 0.0
    vocabulary_ratio: float = 0.0
    unique_words: int = 0
    content_words: int = 0


def tokenize(text: str) -> list[str]:
    """Split a transcript into casefolded words, in any script."""
    normalised = unicodedata.normalize("NFC", text).translate(_ZERO_WIDTH_JOINERS).replace("’", "'")
    cleaned = "".join(
        " " if unicodedata.category(ch)[0] in "PS" and ch not in _KEEP_INSIDE_WORDS else ch for ch in normalised
    )
    tokens = (token.strip("'-").casefold() for token in cleaned.split())
    return [token for token in tokens if token]


def _count_matches(
    tokens: list[str], words: frozenset[str], phrases: tuple[tuple[str, ...], ...]
) -> tuple[Counter[str], set[int]]:
    """Count words and phrases, returning the matches and the token positions they used."""
    counts: Counter[str] = Counter()
    used: set[int] = set()
    index = 0
    while index < len(tokens):
        for phrase in phrases:
            if tuple(tokens[index : index + len(phrase)]) == phrase:
                counts[" ".join(phrase)] += 1
                used.update(range(index, index + len(phrase)))
                index += len(phrase)
                break
        else:
            token = tokens[index]
            is_real_word = index > 0 and tokens[index - 1] in _REAL_WORD_AFTER.get(token, ())
            if token in words and not is_real_word:
                counts[token] += 1
                used.add(index)
            index += 1
    return counts, used


def compute_text_metrics(transcript: str, speaking_seconds: float) -> TextMetrics:
    """Compute WPM, fillers, hedges and vocabulary from a transcript."""
    tokens = tokenize(transcript)
    if not tokens:
        return TextMetrics()

    fillers, filler_positions = _count_matches(tokens, _SINGLE_WORD_FILLERS, _FILLER_PHRASES)
    hedges, _ = _count_matches(tokens, _SINGLE_WORD_HEDGES, _HEDGE_PHRASES)

    # Fillers are left out so that repeating "um" can neither raise nor lower the vocabulary score.
    content = [token for position, token in enumerate(tokens) if position not in filler_positions]
    unique = len(set(content))
    word_count = len(tokens)
    per_100 = 100 / word_count

    return TextMetrics(
        word_count=word_count,
        wpm=round(word_count / (speaking_seconds / 60), 1) if speaking_seconds > 0 else None,
        filler_count=sum(fillers.values()),
        filler_per_100=round(sum(fillers.values()) * per_100, 2),
        filler_breakdown=dict(fillers.most_common()),
        hedge_count=sum(hedges.values()),
        hedges_per_100=round(sum(hedges.values()) * per_100, 2),
        vocabulary_ratio=round(unique / len(content), 3) if content else 0.0,
        unique_words=unique,
        content_words=len(content),
    )
