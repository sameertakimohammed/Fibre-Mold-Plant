"""Authentication contract: login success/failure, account lockout, /me."""
from conftest import ADMIN_PASSWORD, ADMIN_USERNAME, _login


def test_login_success_returns_token(client):
    resp = _login(client, ADMIN_USERNAME, ADMIN_PASSWORD)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["username"] == ADMIN_USERNAME
    assert body["role"] == "admin"


def test_login_wrong_password_401(client):
    resp = _login(client, ADMIN_USERNAME, "definitely-wrong-password")
    assert resp.status_code == 401, resp.text


def test_login_unknown_user_401(client):
    # Unknown usernames return the same generic 401 (no existence leak).
    resp = _login(client, "no-such-user", "whatever")
    assert resp.status_code == 401, resp.text


def test_me_requires_token(client):
    # No Authorization header -> 401 from the OAuth2 scheme.
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401, resp.text


def test_me_with_valid_token(client):
    token = _login(client, ADMIN_USERNAME, ADMIN_PASSWORD).json()["access_token"]
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["username"] == ADMIN_USERNAME


def test_me_with_garbage_token_401(client):
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401, resp.text


def test_account_lockout_trips_to_429(client, admin_headers):
    """After settings.lockout_threshold consecutive failures a KNOWN user is
    locked: the next login attempt returns 429 (even with the right password).

    Uses a dedicated user so we never lock the seed admin (shared by other tests).
    """
    from app.core.config import settings

    username = "lockme"
    password = "lockme-password-123"
    # Create the victim user via admin.
    resp = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"username": username, "full_name": "Lock Me",
              "password": password, "role": "operator"},
    )
    assert resp.status_code in (201, 409), resp.text

    threshold = settings.lockout_threshold
    # Drive exactly `threshold` failures. Each is a plain 401 until the one that
    # trips the lock; the row's locked_until is set on the threshold-th failure.
    for i in range(threshold):
        r = _login(client, username, "wrong-password")
        assert r.status_code == 401, f"attempt {i}: expected 401, got {r.status_code} {r.text}"

    # Now the account is locked: even the CORRECT password is refused with 429.
    locked = _login(client, username, password)
    assert locked.status_code == 429, f"expected 429 after lockout, got {locked.status_code} {locked.text}"
