"""Saving a scored session and granting its rewards, in one idempotent transaction.

Two independent layers stop a double grant. The `SELECT ... FOR UPDATE` on the user row serialises
all reward writes for a user, and whoever gets the lock second sees `finalised_at` and returns the
stored result. Unique constraints on the ledger, quest and badge tables are the backstop, so even a
future code path that forgot the lock couldn't pay out twice.
"""
import logging
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.database import session_scope
from app.core.timeutils import utcnow
from app.models.gamification import (
    DailyActivity,
    LedgerEntry,
    Profile,
    QuestCompletion,
    StreakDay,
    UserBadge,
)
from app.models.practice import PracticeSession
from app.models.user import lock_user
from app.schemas.gamification import Rewards
from app.schemas.practice import SessionDetail, SessionResult
from app.services.analysis import scoring
from app.services.analysis.speech_analyzer import SpeechOutcome
from app.services.catalog import FREE_TALK_TOPIC
from app.services.gamification import badges, challenges, comebacks, quests, streaks, xp

logger = logging.getLogger("spotlight.rewards")


def _credit(
    db: Session,
    profile: Profile,
    key: str,
    reason: str,
    xp_amount: int,
    sparks: int,
    session_id: str | None,
) -> bool:
    """Write a ledger line and pay it out. Returns False, paying nothing, if the key was already used."""
    inserted = db.scalar(
        insert(LedgerEntry)
        .values(
            user_id=profile.user_id,
            session_id=session_id,
            dedupe_key=key,
            reason=reason,
            xp=xp_amount,
            sparks=sparks,
            created_at=utcnow(),
        )
        .on_conflict_do_nothing(constraint="uq_ledger_entries_user_dedupe_key")
        .returning(LedgerEntry.id)
    )
    if inserted is None:
        return False
    profile.xp += xp_amount
    profile.sparks += sparks
    return True


def _daily_activity(db: Session, user_id: str, day: date) -> DailyActivity:
    db.execute(
        insert(DailyActivity).values(user_id=user_id, local_date=day).on_conflict_do_nothing()
    )
    return db.scalars(
        select(DailyActivity)
        .where(DailyActivity.user_id == user_id, DailyActivity.local_date == day)
        .execution_options(populate_existing=True)
    ).one()


def _record_streak(db: Session, profile: Profile, day: date) -> streaks.StreakUpdate:
    update = streaks.apply_practice(
        day, profile.last_practice_date, profile.streak_current, profile.streak_longest, profile.freezes
    )
    if update.extended:
        profile.streak_current = update.current
        profile.streak_longest = update.longest
        profile.freezes = update.freezes
        profile.last_practice_date = day
        day_states = [(day, "practiced"), *((frozen, "frozen") for frozen in update.frozen_dates)]
        for local_day, state in day_states:
            db.execute(
                insert(StreakDay)
                .values(user_id=profile.user_id, local_date=local_day, state=state)
                .on_conflict_do_nothing()
            )
    return update


def _update_counters(
    profile: Profile, activity: DailyActivity, row: PracticeSession, outcome: SpeechOutcome
) -> None:
    seconds = outcome.audio.speaking_seconds
    score = outcome.overall_score or 0
    filler_rate = outcome.text.filler_per_100
    in_band = scoring.is_pace_in_band(outcome.text.wpm)
    reliable = outcome.filler_counts_reliable

    activity.sessions += 1
    activity.speaking_seconds += seconds
    activity.best_score = max(activity.best_score, score)
    activity.low_filler_done = activity.low_filler_done or (reliable and filler_rate <= scoring.LOW_FILLER_PER_100)
    activity.on_pace_done = activity.on_pace_done or in_band
    if row.mode not in activity.modes:
        # Assigned as a new list: SQLAlchemy doesn't notice in-place changes to a JSONB value.
        activity.modes = [*activity.modes, row.mode]

    profile.total_sessions += 1
    profile.total_speaking_seconds += seconds
    profile.best_score = max(profile.best_score or 0, score)
    profile.clean_sessions += int(reliable and filler_rate < scoring.CLEAN_FILLER_PER_100)
    profile.pace_in_band_sessions += int(in_band)
    if row.mode not in profile.modes_practised:
        profile.modes_practised = [*profile.modes_practised, row.mode]


def _comeback_bonus(
    db: Session, profile: Profile, activity: DailyActivity, row: PracticeSession, outcome: SpeechOutcome
) -> dict[str, Any] | None:
    """Pay a second take for beating the take it retried. Each take can be beaten for a bonus once."""
    if row.retry_of is None:
        return None
    parent = db.get(PracticeSession, row.retry_of)
    if parent is None or parent.user_id != row.user_id or parent.overall_score is None:
        return None
    result = comebacks.evaluate(parent.id, parent.overall_score, outcome.overall_score or 0, parent.feedback, outcome.feedback)
    if not result["improved"]:
        return result
    if activity.comebacks >= comebacks.DAILY_LIMIT:
        return {**result, "xp": 0, "sparks": 0, "reason": "daily_limit"}
    if not _credit(db, profile, comebacks.dedupe_key(parent.id), "Comeback bonus", result["xp"], result["sparks"], row.id):
        return {**result, "xp": 0, "sparks": 0, "reason": "already_claimed"}
    activity.comebacks += 1
    profile.comebacks += 1
    return result


def _challenge_bonus(db: Session, profile: Profile, row: PracticeSession, outcome: SpeechOutcome) -> dict[str, Any] | None:
    """Pay the day's challenge, once per day, to the first take that speaks for long enough."""
    length = challenges.LENGTHS.get(row.target_seconds)
    if row.challenge_date is None or length is None:
        return None
    spoken = outcome.audio.speaking_seconds
    result = {
        "date": row.challenge_date.isoformat(),
        "target_seconds": length.seconds,
        "min_seconds": length.min_seconds,
        "spoken_seconds": round(spoken),
        "completed": False,
        "xp": 0,
        "sparks": 0,
        "reason": None,
    }
    if spoken < length.min_seconds:
        return {**result, "reason": "too_short"}
    key = challenges.dedupe_key(row.challenge_date)
    if not _credit(db, profile, key, "Daily challenge", length.xp, length.sparks, row.id):
        return {**result, "reason": "already_done"}
    profile.challenges_completed += 1
    return {**result, "completed": True, "xp": length.xp, "sparks": length.sparks}


def _complete_quests(
    db: Session, profile: Profile, activity: DailyActivity, day: date, session_id: str
) -> tuple[list[dict[str, Any]], int, int]:
    """Pay out quests that have just been completed. Returns them with the XP and sparks they earned."""
    user_id = profile.user_id
    already_done = set(
        db.scalars(
            select(QuestCompletion.quest_id).where(
                QuestCompletion.user_id == user_id, QuestCompletion.local_date == day
            )
        )
    )
    items = quests.daily_quest_items(user_id, day, activity, already_done)
    completed: list[dict[str, Any]] = []
    xp_gained = sparks_gained = 0

    for item in items:
        if not item["completed"] or item["id"] in already_done:
            continue
        inserted = db.scalar(
            insert(QuestCompletion)
            .values(user_id=user_id, local_date=day, quest_id=item["id"], completed_at=utcnow())
            .on_conflict_do_nothing()
            .returning(QuestCompletion.quest_id)
        )
        key = f"quest:{day.isoformat()}:{item['id']}"
        if inserted and _credit(db, profile, key, f"Quest: {item['title']}", item["xp"], item["sparks"], session_id):
            completed.append(item)
            xp_gained += item["xp"]
            sparks_gained += item["sparks"]

    if completed and all(item["completed"] for item in items):
        key = f"quest_bonus:{day.isoformat()}"
        if _credit(db, profile, key, "All daily quests complete", 0, quests.BONUS_SPARKS, session_id):
            sparks_gained += quests.BONUS_SPARKS
    return completed, xp_gained, sparks_gained


def _unlock_badges(db: Session, profile: Profile, session_id: str) -> tuple[list[dict[str, Any]], int, int]:
    """Unlock everything newly earned. Loops because a badge's XP can itself unlock a level badge."""
    user_id = profile.user_id
    unlocked = dict(
        db.execute(select(UserBadge.badge_id, UserBadge.unlocked_at).where(UserBadge.user_id == user_id)).tuples().all()
    )
    earned: list[dict[str, Any]] = []
    xp_gained = sparks_gained = 0

    while pending := badges.newly_earned(profile, set(unlocked)):
        for badge in pending:
            now: datetime = utcnow()
            unlocked[badge.id] = now
            inserted = db.scalar(
                insert(UserBadge)
                .values(user_id=user_id, badge_id=badge.id, unlocked_at=now)
                .on_conflict_do_nothing()
                .returning(UserBadge.badge_id)
            )
            if inserted and _credit(
                db, profile, f"badge:{badge.id}", f"Badge: {badge.name}", badge.xp, badge.sparks, session_id
            ):
                earned.append(badges.badge_view(badge, profile, now))
                xp_gained += badge.xp
                sparks_gained += badge.sparks
    return earned, xp_gained, sparks_gained


def _grant_rewards(db: Session, row: PracticeSession, outcome: SpeechOutcome) -> Rewards:
    day = row.local_date
    profile = db.get(Profile, row.user_id)
    level_before = xp.level_for_xp(profile.xp)
    activity = _daily_activity(db, row.user_id, day)

    score = outcome.overall_score or 0
    first_of_day = activity.sessions == 0
    personal_best = score > (profile.best_score or 0)

    streak = _record_streak(db, profile, day)
    session_xp, breakdown = xp.session_xp(outcome.audio.speaking_seconds, score, personal_best, profile.streak_current)
    session_sparks = xp.session_sparks(first_of_day, score)
    _update_counters(profile, activity, row, outcome)

    if not _credit(db, profile, f"session:{row.id}", "Session completed", session_xp, session_sparks, row.id):
        raise RuntimeError("session reward already granted but finalised_at was not set")

    # Before badges, which count comebacks and completed challenges.
    comeback = _comeback_bonus(db, profile, activity, row, outcome)
    challenge = _challenge_bonus(db, profile, row, outcome)
    bonus_xp = (comeback or {}).get("xp", 0) + (challenge or {}).get("xp", 0)
    bonus_sparks = (comeback or {}).get("sparks", 0) + (challenge or {}).get("sparks", 0)

    completed_quests, quest_xp, quest_sparks = _complete_quests(db, profile, activity, day, row.id)
    new_badges, badge_xp, badge_sparks = _unlock_badges(db, profile, row.id)

    if comeback and comeback["xp"]:
        breakdown.append({"label": "Comeback bonus", "xp": comeback["xp"]})
    if challenge and challenge["xp"]:
        breakdown.append({"label": "Daily challenge", "xp": challenge["xp"]})
    if quest_xp:
        breakdown.append({"label": "Daily quests", "xp": quest_xp})
    if badge_xp:
        breakdown.append({"label": "Badges", "xp": badge_xp})

    level_after = xp.level_for_xp(profile.xp)
    leveled_up = level_after > level_before
    return Rewards(
        xp_gained=session_xp + bonus_xp + quest_xp + badge_xp,
        xp_breakdown=breakdown,
        sparks_gained=session_sparks + bonus_sparks + quest_sparks + badge_sparks,
        level_before=level_before,
        level_after=level_after,
        leveled_up=leveled_up,
        new_title=xp.level_title(level_after) if leveled_up else None,
        personal_best=personal_best,
        streak={
            "current": profile.streak_current,
            "longest": profile.streak_longest,
            "extended": streak.extended,
            "freeze_used": streak.freeze_used,
            "freeze_earned": streak.freeze_earned,
        },
        new_badges=new_badges,
        completed_quests=completed_quests,
        comeback=comeback,
        challenge=challenge,
    )


def _no_rewards(db: Session, row: PracticeSession) -> Rewards:
    profile = db.get(Profile, row.user_id)
    level = xp.level_for_xp(profile.xp)
    return Rewards(
        xp_gained=0,
        xp_breakdown=[],
        sparks_gained=0,
        level_before=level,
        level_after=level,
        leveled_up=False,
        new_title=None,
        personal_best=False,
        streak={
            "current": streaks.read_status(
                row.local_date, profile.last_practice_date, profile.streak_current, profile.freezes
            ).current,
            "longest": profile.streak_longest,
            "extended": False,
            "freeze_used": 0,
            "freeze_earned": False,
        },
        new_badges=[],
        completed_quests=[],
    )


def _apply_outcome(row: PracticeSession, outcome: SpeechOutcome, ended_at: datetime) -> None:
    audio, text = outcome.audio, outcome.text
    row.status = "completed" if outcome.qualified else "too_short"
    if row.free_talk and outcome.detected_topic:
        # So History can say what the speech was about. Without a scored speech it stays "Free talk".
        row.topic = f"{FREE_TALK_TOPIC}: {outcome.detected_topic}"[:200]
    row.ended_at = ended_at
    row.speaking_seconds = audio.speaking_seconds
    row.word_count = text.word_count
    row.wpm = text.wpm
    row.filler_count = text.filler_count
    row.filler_per_100 = text.filler_per_100
    row.filler_breakdown = text.filler_breakdown
    row.hedge_count = text.hedge_count
    row.pause_count = audio.pause_count
    row.longest_pause_seconds = audio.longest_pause_seconds
    row.pause_ratio = audio.pause_ratio
    row.volume_variation = audio.volume_variation
    row.vocabulary_ratio = text.vocabulary_ratio
    row.scores = outcome.scores
    row.overall_score = outcome.overall_score
    row.ai_scored = outcome.ai_scored
    row.analysis_model = outcome.analysis_model
    row.filler_counts_reliable = outcome.filler_counts_reliable
    row.feedback = outcome.feedback
    row.transcript = outcome.transcript


def _stored_result(row: PracticeSession) -> dict[str, Any]:
    return SessionResult(session=SessionDetail.from_row(row), **row.result_payload).model_dump(mode="json")


def finalise_session(session_id: str, outcome: SpeechOutcome, ended_at: datetime | None = None) -> dict[str, Any] | None:
    """Save a scored session and grant its rewards, exactly once.

    Returns the SessionResult as a JSON-ready dict, or None if the session or its user was deleted in
    the meantime. Calling it again returns the original result and changes nothing.
    """
    with session_scope() as db:
        user_id = db.scalar(select(PracticeSession.user_id).where(PracticeSession.id == session_id))
        if user_id is None or lock_user(db, user_id) is None:
            return None
        # Read only after holding the user lock, so a concurrent finalisation's commit is visible.
        row = db.scalar(select(PracticeSession).where(PracticeSession.id == session_id).with_for_update())
        if row is None:
            return None
        if row.finalised_at is not None:
            return _stored_result(row)

        _apply_outcome(row, outcome, ended_at or utcnow())
        rewards = _grant_rewards(db, row, outcome) if outcome.qualified else _no_rewards(db, row)
        row.xp_awarded = rewards.xp_gained
        row.sparks_awarded = rewards.sparks_gained
        row.finalised_at = utcnow()
        row.result_payload = {
            "qualified": outcome.qualified,
            "disqualified_reason": outcome.disqualified_reason,
            "rewards": rewards.model_dump(mode="json"),
        }
        db.flush()
        logger.info(
            "session finalised session=%s status=%s score=%s model=%s xp=%d",
            session_id, row.status, row.overall_score, row.analysis_model, rewards.xp_gained,
        )
        return _stored_result(row)
