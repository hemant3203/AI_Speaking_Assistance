"""Tests for transcript tokenising and language metrics."""
from app.services.analysis.text_metrics import compute_text_metrics, tokenize


def test_tokenize_strips_punctuation_and_case():
    assert tokenize('Hello, WORLD! "Quoted" (text)...') == ["hello", "world", "quoted", "text"]


def test_tokenize_keeps_devanagari_words_whole():
    # Vowel signs are combining marks, which is exactly where a \w based tokeniser would split.
    assert tokenize("नमस्ते, मेरा नाम राहुल है।") == ["नमस्ते", "मेरा", "नाम", "राहुल", "है"]


def test_tokenize_splits_on_punctuation_without_spaces():
    assert tokenize("um,like") == ["um", "like"]


def test_tokenize_keeps_apostrophes_and_hyphens_inside_words():
    assert tokenize("don't well-known -edge- 'quoted'") == ["don't", "well-known", "edge", "quoted"]


def test_tokenize_empty():
    assert tokenize("  ... !! ") == []


def test_fillers_counted_with_breakdown():
    metrics = compute_text_metrics("Um, this is, um, basically, you know, a test uh of it.", 60)
    assert metrics.filler_breakdown == {"um": 2, "basically": 1, "you know": 1, "uh": 1}
    assert metrics.filler_count == 5
    assert metrics.word_count == 12
    assert metrics.filler_per_100 == round(5 / 12 * 100, 2)


def test_hindi_fillers():
    assert compute_text_metrics("matlab yeh yaani theek hai", 60).filler_breakdown == {"matlab": 1, "yaani": 1}
    assert compute_text_metrics("मतलब यह यानी ठीक है", 60).filler_breakdown == {"मतलब": 1, "यानी": 1}


def test_hindi_hesitation_sounds_count_however_they_are_transcribed():
    assert compute_text_metrics("आज मैं अम् बात करूँगी अं फिर उम्", 60).filler_breakdown == {"अम्": 1, "अं": 1, "उम्": 1}


def test_hindi_hesitation_written_with_dots_counts():
    assert compute_text_metrics("अ... तो... मैं बात कर रहा था", 60).filler_breakdown == {"अ": 1}
    assert compute_text_metrics("शुरू में अह मुझे डर लगता था", 60).filler_breakdown == {"अह": 1}


def test_normal_hindi_grammar_is_not_a_filler():
    sentence = "जब मैंने बोलना शुरू किया तो मैं डरी हुई थी। अच्छा लगा, हाँ, बस इतना ही।"
    assert compute_text_metrics(sentence, 60).filler_count == 0


def test_matlab_meaning_this_means_is_not_a_filler():
    assert compute_text_metrics("इसका मतलब साफ़ है", 60).filler_count == 0
    assert compute_text_metrics("मैं मतलब रोज़ कोशिश करती रही", 60).filler_breakdown == {"मतलब": 1}


def test_like_as_verb_or_comparison_is_not_a_filler():
    assert compute_text_metrics("I like pizza and it looks like rain", 60).filler_count == 0
    assert compute_text_metrics("it was like huge", 60).filler_breakdown == {"like": 1}


def test_hedges_including_phrases():
    assert compute_text_metrics("I think maybe this is sort of right, shayad", 60).hedge_count == 4


def test_wpm_uses_speaking_time():
    assert compute_text_metrics(" ".join(["word"] * 150), 60).wpm == 150.0
    assert compute_text_metrics(" ".join(["word"] * 150), 30).wpm == 300.0


def test_vocabulary_ratio_excludes_fillers():
    assert compute_text_metrics("alpha beta um um um", 60).vocabulary_ratio == 1.0
    assert compute_text_metrics("alpha alpha beta beta", 60).vocabulary_ratio == 0.5


def test_empty_transcript():
    metrics = compute_text_metrics("", 60)
    assert metrics.word_count == 0
    assert metrics.wpm is None
