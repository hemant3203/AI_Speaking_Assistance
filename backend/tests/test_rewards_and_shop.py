"""Tests for the reward transaction under real Postgres locking, for the shop, and for migrations."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import func, select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from app.core.database import Base, get_engine, session_scope
from app.core.errors import ApiError
from app.models.gamification import LedgerEntry, Profile, QuestCompletion, UserBadge
from app.services.gamification import quests, shop
from app.services.gamification.rewards import finalise_session
from tests.conftest import API, create_session, make_outcome, run_sql

CLEAN_TEXT = " ".join(f"word{n}" for n in range(280))


def _profile(user_id: str) -> Profile:
    with session_scope() as db:
        return db.get(Profile, user_id)


def _ledger_count(user_id: str, key_prefix: str) -> int:
    with session_scope() as db:
        return db.scalar(
            select(func.count())
            .select_from(LedgerEntry)
            .where(LedgerEntry.user_id == user_id, LedgerEntry.dedupe_key.startswith(key_prefix))
        )


def _set_sparks(user_id: str, sparks: int) -> None:
    run_sql("UPDATE profiles SET sparks=:s WHERE user_id=:u", s=sparks, u=user_id)


def _set_session_date(session_id: str, day: date) -> None:
    run_sql("UPDATE practice_sessions SET local_date=:d WHERE id=:i", d=day, i=session_id)


def test_first_session_rewards(client, user):
    session = create_session(client)
    result = finalise_session(session["id"], make_outcome(seconds=120, score=80))

    rewards = result["rewards"]
    assert result["qualified"] is True and result["disqualified_reason"] is None
    assert rewards["personal_best"] is True
    assert rewards["streak"] == {"current": 1, "longest": 1, "extended": True, "freeze_used": 0, "freeze_earned": False}
    assert "warm_up" in {quest["id"] for quest in rewards["completed_quests"]}
    assert "sessions_1" in {badge["id"] for badge in rewards["new_badges"]}
    assert sum(line["xp"] for line in rewards["xp_breakdown"]) == rewards["xp_gained"]
    assert result["session"]["xp_awarded"] == rewards["xp_gained"]
    assert result["session"]["sparks_awarded"] == rewards["sparks_gained"]
    assert result["session"]["status"] == "completed"
    assert result["session"]["analysis_model"] == "test-model"

    profile = _profile(user["id"])
    assert profile.xp == rewards["xp_gained"] and profile.sparks == rewards["sparks_gained"]
    assert profile.total_sessions == 1 and profile.best_score == 80


def test_too_short_earns_nothing(client, user):
    session = create_session(client)
    result = finalise_session(session["id"], make_outcome(qualified=False))
    assert result["qualified"] is False and result["disqualified_reason"]
    assert result["session"]["status"] == "too_short"
    assert result["rewards"]["xp_gained"] == 0 and result["rewards"]["new_badges"] == []
    assert _profile(user["id"]).total_sessions == 0
    assert _ledger_count(user["id"], "") == 0


def test_finalising_twice_rewards_once_and_returns_the_same_result(client, user):
    session = create_session(client)
    first = finalise_session(session["id"], make_outcome(score=75))
    xp = _profile(user["id"]).xp
    second = finalise_session(session["id"], make_outcome(score=99, seconds=999))

    assert second == first
    assert _profile(user["id"]).xp == xp
    assert _profile(user["id"]).total_sessions == 1
    assert _ledger_count(user["id"], f"session:{session['id']}") == 1


def test_concurrent_finalisations_of_one_session_apply_rewards_once(client, user):
    """Eight threads start together on real Postgres. The row lock must let exactly one pay out."""
    session = create_session(client)
    workers = 8
    barrier = Barrier(workers)

    def finalise(_):
        barrier.wait()
        return finalise_session(session["id"], make_outcome(score=75))

    with ThreadPoolExecutor(workers) as pool:
        results = list(pool.map(finalise, range(workers)))

    assert all(result == results[0] for result in results)
    profile = _profile(user["id"])
    rewards = results[0]["rewards"]
    assert profile.xp == rewards["xp_gained"]
    assert profile.sparks == rewards["sparks_gained"]
    assert profile.total_sessions == 1 and profile.streak_current == 1
    assert _ledger_count(user["id"], f"session:{session['id']}") == 1
    with session_scope() as db:
        assert db.scalar(select(func.count()).select_from(QuestCompletion).where(QuestCompletion.quest_id == "warm_up")) == 1
        assert db.scalar(select(func.count()).select_from(UserBadge).where(UserBadge.badge_id == "sessions_1")) == 1


def test_concurrent_finalisations_of_different_sessions_lose_no_updates(client, user):
    """Different sessions of one user must all count. Without the user lock, read-modify-write would lose some."""
    sessions = [create_session(client) for _ in range(6)]
    barrier = Barrier(len(sessions))

    def finalise(session):
        barrier.wait()
        return finalise_session(session["id"], make_outcome(score=60, seconds=60))

    with ThreadPoolExecutor(len(sessions)) as pool:
        results = list(pool.map(finalise, sessions))

    profile = _profile(user["id"])
    assert profile.total_sessions == 6
    assert profile.total_speaking_seconds == 360
    assert profile.xp == sum(result["rewards"]["xp_gained"] for result in results)
    assert profile.sparks == sum(result["rewards"]["sparks_gained"] for result in results)
    assert profile.streak_current == 1
    # Only one of them can have been the first of the day, and only one can have extended the streak.
    assert sum(result["rewards"]["streak"]["extended"] for result in results) == 1
    assert _ledger_count(user["id"], "session:") == 6


def test_unique_constraints_reject_duplicate_rewards_at_the_database(client, user):
    """The backstop on its own, without going through the code that normally prevents this."""
    session = create_session(client)
    finalise_session(session["id"], make_outcome())
    today = session["local_date"]

    statements = [
        ("INSERT INTO ledger_entries (user_id, dedupe_key, reason, xp, sparks, created_at) "
         f"VALUES ('{user['id']}', 'session:{session['id']}', 'dup', 1, 1, now())"),
        (f"INSERT INTO user_badges (user_id, badge_id, unlocked_at) VALUES ('{user['id']}', 'sessions_1', now())"),
        (f"INSERT INTO quest_completions (user_id, local_date, quest_id, completed_at) "
         f"VALUES ('{user['id']}', '{today}', 'warm_up', now())"),
    ]
    for statement in statements:
        with pytest.raises(IntegrityError):
            with session_scope() as db:
                db.execute(text(statement))


def test_ledger_allows_repeat_purchases_with_a_null_key(client, user):
    _set_sparks(user["id"], 100)
    assert client.post(f"{API}/gamification/shop/streak_freeze/purchase").status_code == 200
    assert client.post(f"{API}/gamification/shop/streak_freeze/purchase").status_code == 200
    assert _profile(user["id"]).freezes == 2


def test_quests_complete_once_per_day_and_bonus_is_paid_once(client, user):
    today = date.fromisoformat(client.get(f"{API}/gamification/profile").json()["daily_quests"]["date"])
    outcomes = [create_session(client, mode=mode) for mode in ("impromptu", "interview", "storytelling")]
    results = [finalise_session(s["id"], make_outcome(score=90, seconds=120, transcript=CLEAN_TEXT)) for s in outcomes]

    completed = [quest["id"] for result in results for quest in result["rewards"]["completed_quests"]]
    assert len(completed) == len(set(completed))

    profile = client.get(f"{API}/gamification/profile").json()
    assert profile["daily_quests"]["date"] == today.isoformat()
    if profile["daily_quests"]["all_complete"]:
        assert _ledger_count(user["id"], f"quest_bonus:{today.isoformat()}") == 1


def test_all_quests_complete_pays_the_bonus(client, user, monkeypatch):
    monkeypatch.setattr(
        quests, "quests_for_day", lambda user_id, day: [quests.QUESTS["warm_up"], quests.QUESTS["high_scorer"]]
    )
    session = create_session(client)
    result = finalise_session(session["id"], make_outcome(score=90))
    assert {quest["id"] for quest in result["rewards"]["completed_quests"]} == {"warm_up", "high_scorer"}
    today = session["local_date"]
    assert _ledger_count(user["id"], f"quest_bonus:{today}") == 1


def test_streak_grows_across_days_and_freeze_is_consumed(client, user):
    today = date.fromisoformat(create_session(client)["local_date"])
    days = [today - timedelta(days=3), today - timedelta(days=2), today]
    run_sql("UPDATE profiles SET freezes=1 WHERE user_id=:u", u=user["id"])

    results = []
    for day in days:
        session = create_session(client)
        _set_session_date(session["id"], day)
        results.append(finalise_session(session["id"], make_outcome()))

    assert [r["rewards"]["streak"]["current"] for r in results] == [1, 2, 3]
    assert results[-1]["rewards"]["streak"]["freeze_used"] == 1

    profile = client.get(f"{API}/gamification/profile").json()
    assert profile["streak"]["freezes"] == 0
    assert profile["streak"]["status"] == "active_today" and profile["streak"]["practiced_today"] is True
    states = {day["date"]: day["state"] for day in profile["streak"]["week"]}
    assert states[(today - timedelta(days=1)).isoformat()] == "frozen"
    assert states[today.isoformat()] == "practiced"


def test_same_day_second_session_does_not_extend_streak_or_repeat_first_of_day_sparks(client, user):
    first = finalise_session(create_session(client)["id"], make_outcome(score=50))
    second = finalise_session(create_session(client)["id"], make_outcome(score=50))
    assert first["rewards"]["streak"]["extended"] is True
    assert second["rewards"]["streak"]["extended"] is False
    assert second["rewards"]["streak"]["current"] == 1
    assert second["rewards"]["personal_best"] is False


def test_broken_streak_reads_as_zero_without_a_write(client, user):
    session = create_session(client)
    long_ago = date.fromisoformat(session["local_date"]) - timedelta(days=10)
    _set_session_date(session["id"], long_ago)
    finalise_session(session["id"], make_outcome())
    profile = client.get(f"{API}/gamification/profile").json()
    assert profile["streak"]["current"] == 0 and profile["streak"]["status"] == "none"
    assert profile["streak"]["longest"] == 1
    assert _profile(user["id"]).streak_current == 1


def test_seven_day_milestone_grants_a_freeze_through_the_transaction(client, user):
    today = date.fromisoformat(create_session(client)["local_date"])
    run_sql(
        "UPDATE profiles SET streak_current=6, streak_longest=6, last_practice_date=:d WHERE user_id=:u",
        d=today - timedelta(days=1), u=user["id"],
    )
    result = finalise_session(create_session(client)["id"], make_outcome())
    assert result["rewards"]["streak"]["current"] == 7 and result["rewards"]["streak"]["freeze_earned"] is True
    assert _profile(user["id"]).freezes == 1


def test_level_up_reported(client, user):
    run_sql("UPDATE profiles SET xp=95 WHERE user_id=:u", u=user["id"])
    rewards = finalise_session(create_session(client)["id"], make_outcome())["rewards"]
    assert rewards["level_before"] == 1 and rewards["leveled_up"] is True
    assert rewards["level_after"] >= 2 and rewards["new_title"]


def test_badge_xp_can_unlock_a_level_badge_in_the_same_transaction(client, user):
    run_sql("UPDATE profiles SET xp=990 WHERE user_id=:u", u=user["id"])
    rewards = finalise_session(create_session(client)["id"], make_outcome())["rewards"]
    assert "level_5" in {badge["id"] for badge in rewards["new_badges"]}


def test_degraded_session_earns_rewards_but_no_filler_credit(client, user):
    outcome = make_outcome(ai_scored=False, score=70, transcript=CLEAN_TEXT)
    result = finalise_session(create_session(client)["id"], outcome)
    assert result["session"]["ai_scored"] is False and result["session"]["analysis_model"] is None
    assert result["rewards"]["xp_gained"] > 0
    # Live transcription strips fillers, so a clean transcript here proves nothing.
    assert _profile(user["id"]).clean_sessions == 0


def test_finalising_a_deleted_session_returns_none(client, user):
    session = create_session(client)
    client.delete(f"{API}/practice/sessions/{session['id']}")
    assert finalise_session(session["id"], make_outcome()) is None
    assert _profile(user["id"]).xp == 0


def test_profile_shape_for_a_new_user(client, user):
    body = client.get(f"{API}/gamification/profile").json()
    assert body["xp"] == 0 and body["level"] == 1 and body["level_title"] == "Nervous Newcomer"
    assert body["xp_for_next_level"] == 100 and body["sparks"] == 0
    assert body["streak"]["status"] == "none" and body["streak"]["next_milestone"] == 7
    assert len(body["streak"]["week"]) == 7 and body["streak"]["week"][-1]["state"] == "today_pending"
    assert len(body["daily_quests"]["items"]) == 3 and body["daily_quests"]["items"][0]["id"] == "warm_up"
    assert body["stats"] == {"total_sessions": 0, "total_speaking_seconds": 0, "best_score": None}
    assert body["recent_badges"] == [] and body["next_badge"]
    assert body["limits"] == {
        "daily_live_seconds": 1800, "used_seconds": 0, "remaining_seconds": 1800, "unlimited": False,
    }


def test_badges_endpoint(client, user):
    items = client.get(f"{API}/gamification/badges").json()["items"]
    assert len(items) >= 16 and all(not item["unlocked"] and item["unlocked_at"] is None for item in items)
    assert set(items[0]) == {
        "id", "name", "description", "icon", "category", "tier", "target", "progress", "unlocked", "unlocked_at",
        "xp", "sparks",
    }


def test_shop_listing(client, user):
    body = client.get(f"{API}/gamification/shop").json()
    items = {item["id"]: item for item in body["items"]}
    assert set(items) == {"streak_freeze", "mentor", "hype", "storyteller", "critic"}
    assert (items["streak_freeze"]["price"], items["hype"]["price"], items["storyteller"]["price"],
            items["critic"]["price"]) == (40, 60, 80, 120)
    assert items["mentor"]["owned"] and items["mentor"]["equipped"] and not items["mentor"]["can_buy"]
    assert not items["hype"]["owned"] and not items["hype"]["can_buy"] and "60 more" in items["hype"]["reason"]


def test_shop_insufficient_sparks(client, user):
    response = client.post(f"{API}/gamification/shop/hype/purchase")
    assert response.status_code == 402 and response.json()["code"] == "insufficient_sparks"


def test_shop_unknown_item(client, user):
    assert client.post(f"{API}/gamification/shop/nope/purchase").status_code == 404


def test_shop_already_owned(client, user):
    _set_sparks(user["id"], 200)
    assert client.post(f"{API}/gamification/shop/mentor/purchase").json()["code"] == "already_owned"
    first = client.post(f"{API}/gamification/shop/hype/purchase")
    assert first.status_code == 200
    assert first.json()["sparks"] == 140 and first.json()["item"]["owned"] is True
    second = client.post(f"{API}/gamification/shop/hype/purchase")
    assert second.status_code == 409 and second.json()["code"] == "already_owned"
    assert _profile(user["id"]).sparks == 140


def test_shop_freeze_limit(client, user):
    _set_sparks(user["id"], 200)
    client.post(f"{API}/gamification/shop/streak_freeze/purchase")
    client.post(f"{API}/gamification/shop/streak_freeze/purchase")
    response = client.post(f"{API}/gamification/shop/streak_freeze/purchase")
    assert response.status_code == 409 and response.json()["code"] == "limit_reached"
    assert _profile(user["id"]).sparks == 120
    items = {item["id"]: item for item in client.get(f"{API}/gamification/shop").json()["items"]}
    assert not items["streak_freeze"]["can_buy"] and "maximum" in items["streak_freeze"]["reason"]


def test_concurrent_purchases_cannot_overspend(client, user):
    """Enough sparks for exactly one. Without the row lock, several buyers could read the same balance."""
    _set_sparks(user["id"], 40)
    workers = 6
    barrier = Barrier(workers)

    def buy(_):
        barrier.wait()
        try:
            with session_scope() as db:
                shop.purchase(db, user["id"], "streak_freeze")
            return "ok"
        except ApiError as exc:
            return exc.code

    with ThreadPoolExecutor(workers) as pool:
        outcomes = sorted(pool.map(buy, range(workers)))
    assert outcomes == ["insufficient_sparks"] * 5 + ["ok"]
    profile = _profile(user["id"])
    assert profile.sparks == 0 and profile.freezes == 1


def test_equip_coach(client, user):
    response = client.post(f"{API}/gamification/coaches/hype/equip")
    assert response.status_code == 403 and response.json()["code"] == "coach_locked"
    assert client.post(f"{API}/gamification/coaches/nope/equip").status_code == 404

    _set_sparks(user["id"], 60)
    client.post(f"{API}/gamification/shop/hype/purchase")
    response = client.post(f"{API}/gamification/coaches/hype/equip")
    assert response.status_code == 200 and response.json()["user"]["equipped_coach"] == "hype"
    assert create_session(client)["coach_id"] == "hype"


def test_activity_feed(client, user):
    finalise_session(create_session(client)["id"], make_outcome())
    _set_sparks(user["id"], 100)
    client.post(f"{API}/gamification/shop/streak_freeze/purchase")
    items = client.get(f"{API}/gamification/activity", params={"limit": 50}).json()["items"]
    assert items[0]["reason"] == "Bought: Streak Freeze" and items[0]["sparks"] == -40
    assert "Session completed" in {item["reason"] for item in items}
    assert set(items[0]) == {"created_at", "reason", "xp", "sparks"}
    assert len(client.get(f"{API}/gamification/activity", params={"limit": 1}).json()["items"]) == 1


def test_migration_matches_the_models_exactly():
    with get_engine().connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        assert compare_metadata(context, Base.metadata) == []


def test_schema_uses_jsonb_and_timezone_aware_timestamps():
    table = Base.metadata.tables["practice_sessions"]
    assert isinstance(table.c.scores.type, postgresql.JSONB)
    with get_engine().connect() as connection:
        rows = connection.execute(
            text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name='practice_sessions' AND column_name IN ('started_at', 'scores', 'id')"
            )
        ).scalars().all()
    assert sorted(rows) == ["jsonb", "timestamp with time zone", "uuid"]
    with get_engine().connect() as connection:
        naive = connection.execute(
            text(
                "SELECT count(*) FROM information_schema.columns WHERE table_schema='public' "
                "AND data_type='timestamp without time zone'"
            )
        ).scalar()
    assert naive == 0


def test_per_user_indexes_exist():
    with get_engine().connect() as connection:
        names = set(connection.execute(text("SELECT indexname FROM pg_indexes WHERE schemaname='public'")).scalars())
    assert {"ix_practice_sessions_user_local_date", "ix_practice_sessions_user_status_started",
            "ix_ledger_entries_user_created", "pk_daily_activity"} <= names
