"""RBAC regression matrix.

Expectations are derived directly from the require_role / get_current_user
dependencies in the routers (read, not guessed):

  ROLE_RANK = operator(1) < supervisor(2) < manager(3) < admin(4)
  require_role(min) -> 403 when rank[user] < rank[min].

  POST   /api/v1/shifts            -> get_current_user  (ANY authenticated role)
  PUT    /api/v1/shifts/{id}       -> require_role(supervisor)
  DELETE /api/v1/shifts/{id}       -> require_role(manager)
  POST   /api/v1/deliveries        -> require_role(supervisor)
  POST   /api/v1/bales             -> require_role(supervisor)
  POST   /api/v1/fuel-dips         -> require_role(supervisor)
  PUT    /api/v1/monthly-stock/{p} -> require_role(supervisor)
  GET    /api/v1/users             -> require_role(admin)
  POST   /api/v1/users             -> require_role(admin)
  GET    /api/v1/audit             -> require_role(admin)

We assert the AUTHORIZATION boundary precisely: denied roles get exactly 403,
and an allowed role gets a non-403 (and, where it's a clean create, 201/200).
"""
import itertools

import pytest

ROLES = ("operator", "supervisor", "manager", "admin")

# date counter so each create in this module uses a unique (work_date, shift)
# slot and never trips the 409 duplicate guard, which would mask a 201/403.
_counter = itertools.count(1)


def _unique_date():
    n = next(_counter)
    # Spread across 2025 so we never collide with seeded May-2026 data.
    return f"2025-{(n % 12) + 1:02d}-{(n % 27) + 1:02d}"


def _shift_payload():
    return {"work_date": _unique_date(), "shift": "Day", "qty": 100}


# ---- POST /api/v1/shifts: ANY authenticated user may create a shift ----------
@pytest.mark.parametrize("role", ROLES)
def test_create_shift_allowed_for_all_roles(client, role_users, role):
    resp = client.post("/api/v1/shifts", headers=role_users[role]["headers"],
                       json=_shift_payload())
    assert resp.status_code == 201, f"{role}: {resp.status_code} {resp.text}"


# ---- POST /api/v1/deliveries: supervisor+ only ------------------------------
@pytest.mark.parametrize("role,expected", [
    ("operator", 403),
    ("supervisor", 201),
    ("manager", 201),
    ("admin", 201),
])
def test_create_delivery_requires_supervisor(client, role_users, role, expected):
    resp = client.post("/api/v1/deliveries", headers=role_users[role]["headers"],
                       json={"work_date": "2025-03-15", "company": "ACME", "tray30": 10})
    assert resp.status_code == expected, f"{role}: {resp.status_code} {resp.text}"


# ---- POST /api/v1/bales: supervisor+ only -----------------------------------
@pytest.mark.parametrize("role,expected", [
    ("operator", 403), ("supervisor", 201), ("manager", 201), ("admin", 201),
])
def test_create_bale_requires_supervisor(client, role_users, role, expected):
    resp = client.post("/api/v1/bales", headers=role_users[role]["headers"],
                       json={"work_date": "2025-03-15", "grn": "G1", "weight_kg": 5})
    assert resp.status_code == expected, f"{role}: {resp.status_code} {resp.text}"


# ---- POST /api/v1/fuel-dips: supervisor+ only -------------------------------
@pytest.mark.parametrize("role,expected", [
    ("operator", 403), ("supervisor", 201), ("manager", 201), ("admin", 201),
])
def test_create_fuel_dip_requires_supervisor(client, role_users, role, expected):
    resp = client.post("/api/v1/fuel-dips", headers=role_users[role]["headers"],
                       json={"work_date": "2025-03-15", "shift": "Day", "open_dip": 1})
    assert resp.status_code == expected, f"{role}: {resp.status_code} {resp.text}"


# ---- PUT /api/v1/monthly-stock/{period}: supervisor+ only -------------------
@pytest.mark.parametrize("role,expected", [
    ("operator", 403), ("supervisor", 200), ("manager", 200), ("admin", 200),
])
def test_upsert_monthly_stock_requires_supervisor(client, role_users, role, expected):
    resp = client.put("/api/v1/monthly-stock/2025-04",
                      headers=role_users[role]["headers"],
                      json={"period": "2025-04", "diesel_eom": 100})
    assert resp.status_code == expected, f"{role}: {resp.status_code} {resp.text}"


# ---- PUT /api/v1/shifts/{id}: supervisor+ -----------------------------------
def test_update_shift_role_boundary(client, role_users):
    # Create a shift to update (operator may create).
    created = client.post("/api/v1/shifts", headers=role_users["operator"]["headers"],
                         json=_shift_payload())
    assert created.status_code == 201, created.text
    sid = created.json()["id"]
    body = {"work_date": created.json()["work_date"], "shift": "Day", "qty": 200}

    # operator cannot update -> 403
    r = client.put(f"/api/v1/shifts/{sid}", headers=role_users["operator"]["headers"], json=body)
    assert r.status_code == 403, r.text
    # supervisor can -> 200
    r = client.put(f"/api/v1/shifts/{sid}", headers=role_users["supervisor"]["headers"], json=body)
    assert r.status_code == 200, r.text


# ---- DELETE /api/v1/shifts/{id}: manager+ -----------------------------------
def test_delete_shift_role_boundary(client, role_users):
    created = client.post("/api/v1/shifts", headers=role_users["operator"]["headers"],
                         json=_shift_payload())
    assert created.status_code == 201, created.text
    sid = created.json()["id"]

    # operator denied
    assert client.delete(f"/api/v1/shifts/{sid}",
                         headers=role_users["operator"]["headers"]).status_code == 403
    # supervisor denied (needs manager)
    assert client.delete(f"/api/v1/shifts/{sid}",
                         headers=role_users["supervisor"]["headers"]).status_code == 403
    # manager allowed -> 204
    assert client.delete(f"/api/v1/shifts/{sid}",
                         headers=role_users["manager"]["headers"]).status_code == 204


# ---- Admin-only endpoints: GET/POST users, GET audit ---------------------
@pytest.mark.parametrize("role,expected", [
    ("operator", 403), ("supervisor", 403), ("manager", 403), ("admin", 200),
])
def test_list_users_admin_only(client, role_users, role, expected):
    resp = client.get("/api/v1/users", headers=role_users[role]["headers"])
    assert resp.status_code == expected, f"{role}: {resp.status_code} {resp.text}"


@pytest.mark.parametrize("role,expected", [
    ("operator", 403), ("supervisor", 403), ("manager", 403), ("admin", 200),
])
def test_list_audit_admin_only(client, role_users, role, expected):
    resp = client.get("/api/v1/audit", headers=role_users[role]["headers"])
    assert resp.status_code == expected, f"{role}: {resp.status_code} {resp.text}"


def test_create_user_non_admin_forbidden(client, role_users):
    for role in ("operator", "supervisor", "manager"):
        resp = client.post("/api/v1/users", headers=role_users[role]["headers"],
                          json={"username": f"x_{role}", "full_name": "X",
                                "password": "password123", "role": "operator"})
        assert resp.status_code == 403, f"{role}: {resp.status_code} {resp.text}"


def test_unauthenticated_write_is_401(client):
    # No token at all -> 401 (authentication) before any role check.
    resp = client.post("/api/v1/shifts", json=_shift_payload())
    assert resp.status_code == 401, resp.text
