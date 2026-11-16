"""Tests for authentication, the rate limit, secrets handling and account deletion."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.database import session_scope
from app.core.rate_limit import RateLimiter
from app.core.security import COOKIE_NAME
from app.main import app
from app.models.gamification import Profile
from app.models.user import User
from tests.conftest import API, create_session, register

BODY = {"email": "a@example.com", "password": "password123", "display_name": "Asha", "timezone": "Asia/Kolkata"}


def test_register_sets_a_secure_cookie_and_returns_the_user(client):
    response = client.post(f"{API}/auth/register", json=BODY)
    assert response.status_code == 201
    user = response.json()["user"]
    assert set(user) == {"id", "email", "display_name", "timezone", "equipped_coach", "is_admin", "created_at"}
    assert user["equipped_coach"] == "mentor"
    assert user["created_at"].endswith("Z")
    cookie = response.headers["set-cookie"].lower()
    assert COOKIE_NAME in cookie and "httponly" in cookie and "samesite=lax" in cookie


def test_password_is_hashed_with_argon2(client):
    client.post(f"{API}/auth/register", json=BODY)
    with session_scope() as db:
        stored = db.scalar(select(User.password_hash))
    assert stored.startswith("$argon2") and "password123" not in stored


def test_duplicate_email_is_409_even_with_different_case(client):
    client.post(f"{API}/auth/register", json=BODY)
    response = client.post(f"{API}/auth/register", json={**BODY, "email": "A@EXAMPLE.COM"})
    assert response.status_code == 409
    assert response.json() == {"detail": response.json()["detail"], "code": "email_taken"}


def test_concurrent_registrations_produce_one_account(client):
    """No pre-check exists, so the unique constraint alone must turn the race into one 201 and the rest 409."""
    workers = 4
    barrier = Barrier(workers)

    def attempt(_):
        barrier.wait()
        return TestClient(app).post(f"{API}/auth/register", json=BODY).status_code

    with ThreadPoolExecutor(workers) as pool:
        statuses = sorted(pool.map(attempt, range(workers)))
    assert statuses == [201, 409, 409, 409]
    with session_scope() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1
        assert db.scalar(select(func.count()).select_from(Profile)) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"email": "not-an-email"},
        {"password": "short"},
        {"password": "x" * 129},
        {"display_name": "A"},
        {"display_name": "x" * 41},
        {"timezone": "Mars/Olympus"},
        {"timezone": "../../etc/passwd"},
    ],
)
def test_invalid_registration_is_422_with_the_uniform_body(client, change):
    response = client.post(f"{API}/auth/register", json={**BODY, **change})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error" and isinstance(body["detail"], str) and body["detail"]


def test_login_logout_me_flow(client):
    client.post(f"{API}/auth/register", json=BODY)
    assert client.get(f"{API}/auth/me").status_code == 200

    assert client.post(f"{API}/auth/logout").status_code == 204
    client.cookies.clear()
    response = client.get(f"{API}/auth/me")
    assert response.status_code == 401 and response.json()["code"] == "not_authenticated"

    response = client.post(f"{API}/auth/login", json={"email": "A@example.com", "password": "password123"})
    assert response.status_code == 200 and response.json()["user"]["email"] == "a@example.com"
    assert client.get(f"{API}/auth/me").status_code == 200


def test_login_errors_are_identical_for_unknown_email_and_wrong_password(client):
    client.post(f"{API}/auth/register", json=BODY)
    wrong = client.post(f"{API}/auth/login", json={"email": BODY["email"], "password": "wrong-password"})
    unknown = client.post(f"{API}/auth/login", json={"email": "nobody@example.com", "password": "wrong-password"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert wrong.json()["code"] == "invalid_credentials"


def test_unknown_email_still_runs_a_password_verification(client, monkeypatch):
    calls = []
    monkeypatch.setattr("app.api.routes.auth.dummy_verify", lambda password: calls.append(1))
    client.post(f"{API}/auth/login", json={"email": "nobody@example.com", "password": "whatever-it-is"})
    assert calls == [1]


def test_login_rate_limit_after_ten_attempts(client):
    body = {"email": "a@example.com", "password": "wrong-password"}
    statuses = [client.post(f"{API}/auth/login", json=body).status_code for _ in range(11)]
    assert statuses == [401] * 10 + [429]
    assert client.post(f"{API}/auth/login", json=body).json()["code"] == "too_many_attempts"


def test_rate_limit_is_per_email(client):
    for _ in range(11):
        client.post(f"{API}/auth/login", json={"email": "a@example.com", "password": "wrong-password"})
    other = client.post(f"{API}/auth/login", json={"email": "b@example.com", "password": "wrong-password"})
    assert other.status_code == 401


def test_successful_login_resets_the_counter(client):
    client.post(f"{API}/auth/register", json=BODY)
    good = {"email": BODY["email"], "password": BODY["password"]}
    bad = {"email": BODY["email"], "password": "wrong-password"}
    for _ in range(9):
        client.post(f"{API}/auth/login", json=bad)
    assert client.post(f"{API}/auth/login", json=good).status_code == 200
    assert client.post(f"{API}/auth/login", json=bad).status_code == 401


def test_rate_limiter_window_expires():
    now = [0.0]
    limiter = RateLimiter(limit=2, window_seconds=10, clock=lambda: now[0])
    assert limiter.hit("k") and limiter.hit("k") and not limiter.hit("k")
    now[0] = 11.0
    assert limiter.hit("k")


def test_patch_me(client):
    client.post(f"{API}/auth/register", json=BODY)
    response = client.patch(f"{API}/auth/me", json={"display_name": "New Name", "timezone": "UTC"})
    assert response.json()["user"]["display_name"] == "New Name"
    assert response.json()["user"]["timezone"] == "UTC"
    assert client.patch(f"{API}/auth/me", json={"timezone": "Nope"}).status_code == 422


def test_delete_me_needs_the_password_and_removes_everything(client):
    client.post(f"{API}/auth/register", json=BODY)
    create_session(client)

    response = client.request("DELETE", f"{API}/auth/me", json={"password": "wrong-password"})
    assert response.status_code == 401

    assert client.request("DELETE", f"{API}/auth/me", json={"password": BODY["password"]}).status_code == 204
    with session_scope() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 0
        assert db.scalar(select(func.count()).select_from(Profile)) == 0


def test_token_for_a_deleted_user_is_rejected(client):
    register(client)
    token = client.cookies[COOKIE_NAME]
    client.request("DELETE", f"{API}/auth/me", json={"password": "password123"})
    client.cookies.set(COOKIE_NAME, token)
    assert client.get(f"{API}/auth/me").status_code == 401


def test_forged_token_is_rejected(client):
    user = register(client)
    forged = jwt.encode({"sub": user["id"], "exp": 9999999999}, "x" * 40, algorithm="HS256")
    client.cookies.set(COOKIE_NAME, forged)
    assert client.get(f"{API}/auth/me").status_code == 401


def test_short_jwt_secret_refuses_to_boot_without_leaking_it():
    with pytest.raises(ValidationError) as caught:
        Settings(jwt_secret="too-short-secret", database_url="postgresql+psycopg://u:p@h/d")
    assert "too-short-secret" not in str(caught.value)


def test_missing_required_settings_refuse_to_boot(monkeypatch):
    monkeypatch.delenv("JWT_SECRET")
    with pytest.raises(ValidationError):
        Settings()
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.delenv("DATABASE_URL")
    with pytest.raises(ValidationError):
        Settings()


def test_sqlite_url_is_refused():
    with pytest.raises(ValidationError):
        Settings(jwt_secret="x" * 40, database_url="sqlite:////data/spotlight.db")


def test_settings_defaults_match_the_contract():
    settings = Settings(jwt_secret="x" * 40, database_url="postgresql+psycopg://u:p@h/d")
    assert settings.analysis_models == ["gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
    assert "x" * 40 not in repr(settings) and "u:p@h" not in repr(settings)
