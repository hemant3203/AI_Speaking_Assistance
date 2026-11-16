"""The admin account: how it is created, what it can do, and that nobody else can get it."""
from pydantic import SecretStr
from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.database import get_engine, session_scope
from app.models.user import User
from app.services.admin import ensure_admin

from .conftest import API, create_session, register

EMAIL = "admin@example.com"
PASSWORD = "admin-password-1"


def _settings(email=EMAIL, password=PASSWORD):
    return get_settings().model_copy(update={"admin_email": email, "admin_password": SecretStr(password)})


def _login(client, email=EMAIL, password=PASSWORD):
    return client.post(f"{API}/auth/login", json={"email": email, "password": password})


def _is_admin(email):
    with session_scope() as db:
        return db.scalar(select(User.is_admin).where(User.email == email))


def _use_up_todays_time(user_id):
    with get_engine().begin() as connection:
        connection.execute(
            text(
                "INSERT INTO daily_activity (user_id, local_date, sessions, speaking_seconds, live_seconds, best_score,"
                " low_filler_done, on_pace_done, modes) VALUES (:u, (now() AT TIME ZONE 'Asia/Kolkata')::date,"
                " 0, 0, 1800, 0, false, false, '[]')"
            ),
            {"u": user_id},
        )


def test_admin_account_is_created_and_can_log_in(client):
    ensure_admin(_settings())
    response = _login(client)
    assert response.status_code == 200 and response.json()["user"]["is_admin"] is True
    assert client.get(f"{API}/gamification/profile").status_code == 200


def test_running_it_again_changes_nothing_and_wrong_password_fails(client):
    ensure_admin(_settings())
    ensure_admin(_settings())
    assert _login(client, password="wrong-password").status_code == 401
    assert _login(client).status_code == 200


def test_changing_the_password_in_env_takes_effect(client):
    ensure_admin(_settings())
    ensure_admin(_settings(password="a-new-password-2"))
    assert _login(client).status_code == 401
    assert _login(client, password="a-new-password-2").status_code == 200


def test_someone_who_registered_the_email_first_cannot_keep_their_password(client):
    register(client, email=EMAIL, password="attacker-password")
    ensure_admin(_settings())
    assert _login(client, password="attacker-password").status_code == 401
    assert _login(client).json()["user"]["is_admin"] is True


def test_changing_the_admin_email_removes_the_old_admin(client):
    ensure_admin(_settings())
    ensure_admin(_settings(email="new-admin@example.com"))
    assert _is_admin(EMAIL) is False and _is_admin("new-admin@example.com") is True


def test_removing_the_admin_settings_removes_admin_rights(client):
    ensure_admin(_settings())
    ensure_admin(_settings(email="", password=""))
    assert _is_admin(EMAIL) is False


def test_a_short_password_creates_no_admin(client):
    ensure_admin(_settings(password="short"))
    assert _is_admin(EMAIL) is None


def test_email_case_does_not_create_a_second_account(client):
    ensure_admin(_settings(email="ADMIN@Example.com"))
    assert _login(client).json()["user"]["is_admin"] is True


def test_nobody_can_make_themselves_admin(client):
    response = client.post(
        f"{API}/auth/register",
        json={"email": "a@example.com", "password": "password123", "display_name": "Asha", "timezone": "UTC", "is_admin": True},
    )
    assert response.status_code == 201 and response.json()["user"]["is_admin"] is False
    patched = client.patch(f"{API}/auth/me", json={"is_admin": True, "display_name": "Asha"})
    assert patched.json()["user"]["is_admin"] is False and _is_admin("a@example.com") is False


def test_admin_buys_every_coach_free_and_can_equip_them(client):
    ensure_admin(_settings())
    _login(client)
    shop = client.get(f"{API}/gamification/shop").json()
    assert shop["sparks"] == 0
    assert all(item["price"] == 0 for item in shop["items"])
    for coach in ("hype", "storyteller", "critic"):
        bought = client.post(f"{API}/gamification/shop/{coach}/purchase")
        assert bought.status_code == 200 and bought.json()["sparks"] == 0 and bought.json()["item"]["owned"]
        assert client.post(f"{API}/gamification/coaches/{coach}/equip").json()["user"]["equipped_coach"] == coach


def test_admin_buys_a_streak_freeze_free(client):
    ensure_admin(_settings())
    _login(client)
    bought = client.post(f"{API}/gamification/shop/streak_freeze/purchase")
    assert bought.status_code == 200 and bought.json()["sparks"] == 0


def test_a_normal_user_still_pays(client):
    register(client)
    shop = {item["id"]: item for item in client.get(f"{API}/gamification/shop").json()["items"]}
    assert shop["hype"]["price"] == 60 and not shop["hype"]["can_buy"]
    assert client.post(f"{API}/gamification/shop/hype/purchase").status_code == 402


def test_admin_has_no_daily_limit(client):
    ensure_admin(_settings())
    user = _login(client).json()["user"]
    _use_up_todays_time(user["id"])
    limits = client.get(f"{API}/gamification/profile").json()["limits"]
    assert limits["unlimited"] is True and limits["remaining_seconds"] > 0
    assert create_session(client)["status"]


def test_a_normal_user_still_has_a_daily_limit(client):
    user = register(client, timezone="Asia/Kolkata")
    _use_up_todays_time(user["id"])
    limits = client.get(f"{API}/gamification/profile").json()["limits"]
    assert limits["unlimited"] is False and limits["remaining_seconds"] == 0
    response = client.post(
        f"{API}/practice/sessions",
        json={"mode": "impromptu", "topic": "Why practice matters", "target_seconds": 60, "language": "en"},
    )
    assert response.status_code >= 400
