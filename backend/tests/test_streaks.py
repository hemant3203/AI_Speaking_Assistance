"""Tests for the streak rules."""
from datetime import date, datetime, timedelta, timezone

from app.core.timeutils import local_date
from app.services.gamification.streaks import apply_practice, next_milestone, read_status, week_view

DAY = date(2026, 11, 5)


def _day(offset: int) -> date:
    return DAY + timedelta(days=offset)


def test_first_practice_starts_a_streak():
    update = apply_practice(DAY, None, 0, 0, 0)
    assert (update.current, update.longest, update.extended) == (1, 1, True)


def test_consecutive_day_extends():
    update = apply_practice(DAY, _day(-1), 4, 4, 0)
    assert (update.current, update.longest, update.freeze_used) == (5, 5, 0)


def test_same_day_repeat_changes_nothing():
    update = apply_practice(DAY, DAY, 4, 9, 1)
    assert (update.current, update.longest, update.freezes, update.extended) == (4, 9, 1, False)


def test_gap_without_freezes_resets_but_keeps_longest():
    update = apply_practice(DAY, _day(-2), 10, 10, 0)
    assert (update.current, update.longest, update.extended) == (1, 10, True)


def test_gap_covered_by_a_freeze_consumes_it():
    update = apply_practice(DAY, _day(-2), 4, 4, 2)
    assert (update.current, update.freezes, update.freeze_used) == (5, 1, 1)
    assert update.frozen_dates == [_day(-1)]


def test_gap_covered_by_two_freezes():
    update = apply_practice(DAY, _day(-3), 4, 4, 2)
    assert (update.current, update.freezes, update.freeze_used) == (5, 0, 2)
    assert update.frozen_dates == [_day(-2), _day(-1)]


def test_gap_larger_than_freezes_resets_and_keeps_them():
    update = apply_practice(DAY, _day(-4), 4, 4, 2)
    assert (update.current, update.freezes, update.freeze_used) == (1, 2, 0)


def test_seven_day_milestone_earns_a_freeze():
    update = apply_practice(DAY, _day(-1), 6, 6, 0)
    assert (update.current, update.freezes, update.freeze_earned) == (7, 1, True)


def test_milestone_does_not_exceed_two_freezes():
    update = apply_practice(DAY, _day(-1), 13, 13, 2)
    assert (update.current, update.freezes, update.freeze_earned) == (14, 2, False)


def test_timezone_moving_west_counts_as_same_day():
    update = apply_practice(_day(-1), DAY, 4, 4, 0)
    assert (update.current, update.extended) == (4, False)


def test_timezone_boundary_same_instant_different_dates():
    instant = datetime(2026, 11, 5, 19, 0, tzinfo=timezone.utc)
    assert local_date("UTC", instant) == date(2026, 11, 5)
    assert local_date("Asia/Kolkata", instant) == date(2026, 11, 6)
    assert local_date("America/Los_Angeles", instant) == date(2026, 11, 5)
    # Two sessions an hour apart in UTC fall on consecutive days for a user in India.
    first = local_date("Asia/Kolkata", datetime(2026, 11, 5, 18, 0, tzinfo=timezone.utc))
    second = local_date("Asia/Kolkata", datetime(2026, 11, 5, 19, 0, tzinfo=timezone.utc))
    assert apply_practice(second, first, 1, 1, 0).current == 2


def test_read_status_states():
    assert read_status(DAY, None, 0, 0).status == "none"
    assert read_status(DAY, DAY, 3, 0).status == "active_today"
    assert read_status(DAY, _day(-1), 3, 0).status == "at_risk"
    assert read_status(DAY, _day(-2), 3, 1).status == "at_risk"


def test_broken_streak_reads_as_zero():
    status = read_status(DAY, _day(-2), 9, 0)
    assert (status.current, status.status, status.practiced_today) == (0, "none", False)


def test_next_milestone():
    assert next_milestone(0) == 7
    assert next_milestone(6) == 7
    assert next_milestone(7) == 14


def test_week_view():
    week = week_view(DAY, {_day(-1): "practiced", _day(-2): "frozen"})
    assert [day["state"] for day in week] == [
        "missed",
        "missed",
        "missed",
        "missed",
        "frozen",
        "practiced",
        "today_pending",
    ]
    assert week[-1]["date"] == "2026-11-05"
    assert week_view(DAY, {DAY: "practiced"})[-1]["state"] == "practiced"
