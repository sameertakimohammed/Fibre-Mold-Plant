"""Sliding-session token refresh: requires a valid token and returns a fresh,
working one."""


def test_refresh_requires_auth(client):
    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 401, r.text


def test_refresh_returns_usable_token(client, admin_headers):
    r = client.post("/api/v1/auth/refresh", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"]
    assert body["username"] == "admin"

    # The new token authenticates a follow-up request.
    new_headers = {"Authorization": f"Bearer {body['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=new_headers)
    assert me.status_code == 200, me.text
    assert me.json()["username"] == "admin"
