"""Pytest fixtures for the FastAPI backend contract/RBAC suite.

Everything here runs fully OFFLINE against a throwaway SQLite database:

  * Environment is set BEFORE the app (and therefore app.core.config.settings,
    which is constructed at import time via an lru_cache) is imported, so the
    test config wins. We force APP_ENV=development (relaxes the secret check),
    a real 32+ char SECRET_KEY, a temp-file SQLite DATABASE_URL, the scheduler
    OFF, AD/SMTP OFF, and a known admin password so we can log the seed admin in.

  * A temp-FILE sqlite DB (not :memory:) is used deliberately: the app's engine
    is created once at import with fixed connect_args and the default pool, so a
    bare sqlite:///:memory: would hand each new connection its own empty
    database and the lifespan-created schema would vanish. A file path is shared
    by every connection, so the schema + seed survive for the whole session.

  * The app lifespan (see app/main.py) creates all tables on the sqlite path and
    runs run_seed(), which creates the first admin user. Entering the TestClient
    as a context manager triggers that lifespan.
"""
import os
import tempfile

import pytest

# --- Environment MUST be configured before importing the app/config ---------
# settings = get_settings() is evaluated at import time of app.core.config, and
# the engine is built at import time of app.core.database, so these env vars have
# to be present before the very first `from app...` import below.

# A unique temp-file sqlite DB for this test session (removed at the end).
_DB_FD, _DB_PATH = tempfile.mkstemp(prefix="fmp_test_", suffix=".db")
os.close(_DB_FD)
# SQLite wants forward slashes in the URL even on Windows.
_DB_URL = "sqlite:///" + _DB_PATH.replace("\\", "/")

# Known admin password so the lockout/auth tests can log the seed admin in.
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "test-admin-password-123"

os.environ["APP_ENV"] = "development"
os.environ["DATABASE_URL"] = _DB_URL
os.environ["SCHEDULER_ENABLED"] = "false"
# A genuine 32+ char secret so config validation passes even if APP_ENV were
# ever read as production. 48 chars, not a known placeholder.
os.environ["SECRET_KEY"] = "test-secret-key-fmp-0123456789abcdef-XYZ-32plus"
os.environ["AD_ENABLED"] = "false"
os.environ["SMTP_ENABLED"] = "false"
# first_admin_username / first_admin_password map to these env vars.
os.environ["FIRST_ADMIN_USERNAME"] = ADMIN_USERNAME
os.environ["FIRST_ADMIN_PASSWORD"] = ADMIN_PASSWORD
# Belt-and-suspenders for anyone reading ADMIN_PASSWORD directly.
os.environ["ADMIN_PASSWORD"] = ADMIN_PASSWORD

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.core.config import settings  # noqa: E402

# Disable the slowapi IP rate limiter for the test run. We are NOT testing the
# per-IP rate limit here; every test request comes from the same TestClient IP,
# so the 10/min login limit would otherwise interfere with the account-lockout
# test (the real security control we DO assert). This is a test-side runtime
# toggle, not an app-code change.
app.state.limiter.enabled = False


def pytest_sessionfinish(session, exitstatus):
    """Remove the temp sqlite DB once the whole run is done.

    Dispose the engine first so SQLite releases its file handle — on Windows an
    open connection keeps the file locked and os.remove would fail.
    """
    try:
        from app.core.database import engine
        engine.dispose()
    except Exception:
        pass
    try:
        os.remove(_DB_PATH)
    except OSError:
        pass


@pytest.fixture(scope="session")
def client():
    """A TestClient whose lifespan creates the schema + seeds the admin.

    Session-scoped: the seed/admin and any users created by tests persist for the
    whole run (cheaper than re-seeding per test, and lets us reuse role users).
    """
    with TestClient(app) as c:
        yield c


# --- Auth helpers -----------------------------------------------------------
def _login(client, username: str, password: str):
    """Raw login call (OAuth2 password form). Returns the httpx Response."""
    return client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    )


def login_token(client, username: str, password: str) -> str:
    """Log in and return the bearer access token (asserts success)."""
    resp = _login(client, username, password)
    assert resp.status_code == 200, f"login failed for {username}: {resp.text}"
    return resp.json()["access_token"]


def auth_header(client, username: str, password: str) -> dict:
    """Authorization header dict for the given user."""
    return {"Authorization": f"Bearer {login_token(client, username, password)}"}


@pytest.fixture(scope="session")
def admin_password() -> str:
    return ADMIN_PASSWORD


@pytest.fixture(scope="session")
def admin_username() -> str:
    return ADMIN_USERNAME


@pytest.fixture
def admin_headers(client):
    """Fresh admin auth header (the seeded admin)."""
    return auth_header(client, ADMIN_USERNAME, ADMIN_PASSWORD)


@pytest.fixture(scope="session")
def role_users(client):
    """Create one user per non-admin role via the admin account, return a dict.

    {role: {"username", "password", "headers"}}. The admin entry points at the
    seeded admin. Created users have must_change_password=True but that does not
    block API access (only the UI nudges a change), so their tokens work.
    """
    admin_h = auth_header(client, ADMIN_USERNAME, ADMIN_PASSWORD)
    password = "user-password-123"  # >= 6 chars
    users = {
        "admin": {
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD,
            "headers": auth_header(client, ADMIN_USERNAME, ADMIN_PASSWORD),
        }
    }
    for role in ("operator", "supervisor", "manager"):
        username = f"test_{role}"
        resp = client.post(
            "/api/v1/users",
            headers=admin_h,
            json={
                "username": username,
                "full_name": f"Test {role.title()}",
                "password": password,
                "role": role,
            },
        )
        # 201 on first create; if the session-scoped fixture somehow re-runs,
        # 409 means the user already exists and we can still log in.
        assert resp.status_code in (201, 409), f"create {role} failed: {resp.text}"
        users[role] = {
            "username": username,
            "password": password,
            "headers": auth_header(client, username, password),
        }
    return users
