"""Tests for level math, XP, sparks, quest selection and badge rules."""
from datetime import date, datetime, timezone
from types import SimpleNamespace

from app.services.gamification import badges, quests
from app.services.gamification.xp import (
    level_for_xp,
    level_progress,
    level_title,
    session_sparks,
    session_xp,
    xp_to_reach,
)


def test_cumulative_xp_formula():
    assert [xp_to_reach(level) for level in (1, 2, 3, 5, 6)] == [0, 100, 300, 1000, 1500]


def test_level_boundaries():
    assert level_for_xp(0) == 1
    assert level_for_xp(99) == 1
    assert level_for_xp(100) == 2
    assert level_for_xp(999) == 4
    assert level_for_xp(1000) == 5


def test_level_progress_matches_contract_example():
    progress = level_progress(1240)
    assert (progress.level, progress.title, progress.xp_into_level, progress.xp_for_next_level) == (
        5,
        "Confident Speaker",
        240,
        500,
    )


def test_titles_cap_at_legend():
    assert level_title(1) == "Nervous Newcomer"
    assert level_title(9) == "Keynote Speaker"
    assert level_title(10) == level_title(50) == "Spotlight Legend"


def test_xp_formula():
    # (20 + 20 + 37 + 0) * 1.1 = 84.7
    total, breakdown = session_xp(120, 74, False, 2)
    assert total == 85
    assert sum(line["xp"] for line in breakdown) == total


def test_xp_breakdown_adds_up_and_only_shows_a_streak_line_with_a_streak():
    for seconds in (15, 45, 75, 123, 299):
        for score in (1, 37, 75, 99):
            total, breakdown = session_xp(seconds, score, False, 0)
            assert sum(line["xp"] for line in breakdown) == total
            assert "Streak bonus" not in {line["label"] for line in breakdown}
            streak_total, streak_breakdown = session_xp(seconds, score, True, 7)
            assert sum(line["xp"] for line in streak_breakdown) == streak_total


def test_xp_time_is_capped_and_personal_best_added():
    total, breakdown = session_xp(3600, 100, True, 0)
    assert total == 20 + 50 + 50 + 15
    assert {"label": "Personal best", "xp": 15} in breakdown


def test_xp_streak_bonus_caps_at_ten_days():
    assert session_xp(60, 0, False, 10)[0] == session_xp(60, 0, False, 99)[0] == 45


def test_sparks():
    assert session_sparks(False, 50) == 5
    assert session_sparks(True, 50) == 10
    assert session_sparks(False, 80) == 10
    assert session_sparks(True, 95) == 15


def _activity(**overrides):
    values = dict(sessions=0, speaking_seconds=0.0, best_score=0, low_filler_done=False, on_pace_done=False, modes=[])
    return SimpleNamespace(**{**values, **overrides})


def test_quests_are_deterministic_and_include_warm_up():
    day = date(2026, 11, 5)
    first = quests.quests_for_day("user-1", day)
    assert [q.id for q in first] == [q.id for q in quests.quests_for_day("user-1", day)]
    assert len(first) == 3 and len({q.id for q in first}) == 3
    assert first[0].id == "warm_up"


def test_quests_vary_by_user_and_day():
    day = date(2026, 11, 5)
    by_user = {tuple(q.id for q in quests.quests_for_day(f"user-{n}", day)) for n in range(30)}
    by_day = {tuple(q.id for q in quests.quests_for_day("user-1", date(2026, 11, n))) for n in range(1, 29)}
    assert len(by_user) > 1 and len(by_day) > 1


def test_each_quest_progress_rule():
    rules = {
        "warm_up": _activity(sessions=1),
        "double_up": _activity(sessions=2),
        "three_minutes": _activity(speaking_seconds=180),
        "high_scorer": _activity(best_score=70),
        "clean_speech": _activity(low_filler_done=True),
        "in_the_zone": _activity(on_pace_done=True),
        "mix_it_up": _activity(modes=["impromptu", "interview"]),
    }
    assert set(rules) == set(quests.QUESTS)
    for quest_id, activity in rules.items():
        quest = quests.QUESTS[quest_id]
        assert quest.progress(activity) >= quest.target, quest_id
        assert quest.progress(_activity()) < quest.target, quest_id


def test_quest_items_cap_progress_and_handle_no_activity():
    items = quests.daily_quest_items("user-1", date(2026, 11, 5), _activity(sessions=9), set())
    warm_up = next(item for item in items if item["id"] == "warm_up")
    assert warm_up["progress"] == 1 and warm_up["completed"]
    assert not any(item["completed"] for item in quests.daily_quest_items("user-1", date(2026, 11, 5), None, set()))


def _profile(**overrides):
    values = dict(
        xp=0,
        streak_longest=0,
        total_sessions=0,
        total_speaking_seconds=0.0,
        best_score=None,
        clean_sessions=0,
        pace_in_band_sessions=0,
        modes_practised=[],
        challenges_completed=0,
        comebacks=0,
    )
    return SimpleNamespace(**{**values, **overrides})


def test_badge_catalog_covers_the_contract():
    ids = {badge.id for badge in badges.BADGES}
    assert len(badges.BADGES) >= 16
    assert {
        "streak_3", "streak_7", "streak_30", "streak_100", "sessions_1", "sessions_10", "sessions_50", "minutes_60",
        "minutes_300", "score_80", "score_90", "clean_speaker", "pace_setter", "all_modes", "level_5", "level_10",
    } <= ids
    assert {badge.tier for badge in badges.BADGES} == {"bronze", "silver", "gold"}


def test_newly_earned_respects_thresholds_and_already_unlocked():
    profile = _profile(total_sessions=1, streak_longest=3, best_score=85)
    assert {b.id for b in badges.newly_earned(profile, set())} == {"sessions_1", "streak_3", "score_80"}
    assert {b.id for b in badges.newly_earned(profile, {"sessions_1"})} == {"streak_3", "score_80"}


def test_level_and_mode_badges():
    assert "level_5" in {b.id for b in badges.newly_earned(_profile(xp=1000), set())}
    modes = ["impromptu", "presentation", "interview", "storytelling", "persuasion"]
    assert "all_modes" in {b.id for b in badges.newly_earned(_profile(modes_practised=modes), set())}
    assert "all_modes" not in {b.id for b in badges.newly_earned(_profile(modes_practised=modes[:4]), set())}


def test_badge_view_caps_progress():
    badge = badges.BADGES_BY_ID["sessions_1"]
    when = datetime(2026, 11, 5, tzinfo=timezone.utc)
    view = badges.badge_view(badge, _profile(total_sessions=7), when)
    assert view["progress"] == 1 and view["unlocked"] and view["unlocked_at"] == when


def test_next_badge_is_the_closest_locked_one():
    profile = _profile(total_sessions=9, streak_longest=1)
    assert badges.next_badge_view(profile, {"sessions_1": datetime.now(timezone.utc)})["id"] == "sessions_10"
    all_unlocked = {badge.id: datetime.now(timezone.utc) for badge in badges.BADGES}
    assert badges.next_badge_view(profile, all_unlocked) is None
