"""User-management contract (admin only): duplicate username, short-password
validation, and username normalization (lowercasing)."""


def test_create_user_lowercases_username(client, admin_headers):
    resp = client.post("/api/v1/users", headers=admin_headers,
                      json={"username": "MixedCaseUser", "full_name": "Mixed",
                            "password": "password123", "role": "operator"})
    assert resp.status_code == 201, resp.text
    assert resp.json()["username"] == "mixedcaseuser"


def test_duplicate_username_conflict_409(client, admin_headers):
    payload = {"username": "dupuser", "full_name": "Dup",
               "password": "password123", "role": "operator"}
    first = client.post("/api/v1/users", headers=admin_headers, json=payload)
    assert first.status_code == 201, first.text
    dup = client.post("/api/v1/users", headers=admin_headers, json=payload)
    assert dup.status_code == 409, dup.text


def test_duplicate_detected_after_lowercasing(client, admin_headers):
    # "Casey" and "casey" normalize to the same username -> second is a 409.
    a = client.post("/api/v1/users", headers=admin_headers,
                  json={"username": "Casey", "full_name": "C",
                        "password": "password123", "role": "operator"})
    assert a.status_code == 201, a.text
    b = client.post("/api/v1/users", headers=admin_headers,
                  json={"username": "casey", "full_name": "C2",
                        "password": "password123", "role": "operator"})
    assert b.status_code == 409, b.text


def test_short_password_rejected_422(client, admin_headers):
    # password min_length is 8 (UserCreate schema) -> 5 chars fails validation.
    resp = client.post("/api/v1/users", headers=admin_headers,
                      json={"username": "shortpw", "full_name": "Short",
                            "password": "12345", "role": "operator"})
    assert resp.status_code == 422, resp.text


def test_seven_char_password_rejected_422(client, admin_headers):
    # Enforces the raised 8-char floor: 7 chars must still fail.
    resp = client.post("/api/v1/users", headers=admin_headers,
                      json={"username": "sevenpw", "full_name": "Seven",
                            "password": "1234567", "role": "operator"})
    assert resp.status_code == 422, resp.text


def test_admin_reset_password_sets_must_change_and_rotates_login(client, admin_headers):
    # Admin resets a user's password via PATCH: must_change_password flips back
    # on, the old password stops working, and the new one logs in.
    create = client.post("/api/v1/users", headers=admin_headers,
                       json={"username": "resetme", "full_name": "Reset Me",
                             "password": "original-password-123", "role": "operator"})
    assert create.status_code == 201, create.text
    uid = create.json()["id"]

    new_pw = "fresh-temp-password-456"
    patch = client.patch(f"/api/v1/users/{uid}", headers=admin_headers,
                         json={"password": new_pw})
    assert patch.status_code == 200, patch.text
    assert patch.json()["must_change_password"] is True

    old = client.post("/api/v1/auth/login",
                      data={"username": "resetme", "password": "original-password-123"})
    assert old.status_code == 401, old.text
    fresh = client.post("/api/v1/auth/login",
                        data={"username": "resetme", "password": new_pw})
    assert fresh.status_code == 200, fresh.text
    assert fresh.json()["must_change_password"] is True


def test_admin_reset_short_password_rejected_422(client, admin_headers):
    # The 8-char floor now applies to admin resets (UserUpdate.password), too.
    create = client.post("/api/v1/users", headers=admin_headers,
                       json={"username": "resetshort", "full_name": "Reset Short",
                             "password": "original-password-123", "role": "operator"})
    assert create.status_code == 201, create.text
    uid = create.json()["id"]
    patch = client.patch(f"/api/v1/users/{uid}", headers=admin_headers,
                         json={"password": "1234567"})  # 7 chars
    assert patch.status_code == 422, patch.text


def test_blank_username_rejected_422(client, admin_headers):
    # A blank username ("   ") makes the UserCreate field_validator raise a bare
    # ValueError ("username must not be blank"). Pydantic surfaces that in
    # exc.errors() with a non-JSON-serializable ctx (the ValueError object).
    # The app's RequestValidationError handler now SANITIZES exc.errors() before
    # serializing, so this returns a clean 422 (it previously 500'd because the
    # handler tried to json-encode the ValueError). Regression guard.
    resp = client.post("/api/v1/users", headers=admin_headers,
                      json={"username": "   ", "full_name": "Blank",
                            "password": "password123", "role": "operator"})
    assert resp.status_code == 422, resp.text
    body = resp.json()
    # The clean error envelope must carry the request id and serializable details.
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["request_id"]
