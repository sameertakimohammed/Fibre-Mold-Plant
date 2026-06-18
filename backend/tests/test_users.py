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
    # password min_length is 6 (UserCreate schema) -> 5 chars fails validation.
    resp = client.post("/api/v1/users", headers=admin_headers,
                      json={"username": "shortpw", "full_name": "Short",
                            "password": "12345", "role": "operator"})
    assert resp.status_code == 422, resp.text


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
