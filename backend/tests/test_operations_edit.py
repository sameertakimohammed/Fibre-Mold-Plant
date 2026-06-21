"""Edit (PUT) and stock-delete contract for the operations logs.

Covers the inline-edit endpoints added for deliveries, bale receipts and fuel
dips, plus the monthly-stock soft-delete + revive-on-upsert behaviour and their
role boundaries (edit = supervisor+, stock delete = manager+).
"""
import itertools

import pytest

_counter = itertools.count(1)


def _date():
    n = next(_counter)
    return f"2023-{(n % 12) + 1:02d}-{(n % 27) + 1:02d}"


def _period():
    n = next(_counter)
    return f"2023-{(n % 12) + 1:02d}"


# ---- Deliveries: edit ----
def test_update_delivery(client, role_users):
    sup = role_users["supervisor"]["headers"]
    created = client.post("/api/v1/deliveries", headers=sup,
                          json={"work_date": _date(), "company": "ACME", "tray30": 10})
    assert created.status_code == 201, created.text
    did = created.json()["id"]

    edited = client.put(f"/api/v1/deliveries/{did}", headers=sup,
                        json={"work_date": created.json()["work_date"],
                              "company": "BULA COLD STORES", "tray30": 25})
    assert edited.status_code == 200, edited.text
    assert edited.json()["company"] == "BULA COLD STORES"
    assert edited.json()["tray30"] == 25


def test_update_delivery_operator_forbidden(client, role_users):
    sup = role_users["supervisor"]["headers"]
    created = client.post("/api/v1/deliveries", headers=sup,
                          json={"work_date": _date(), "company": "ACME"})
    did = created.json()["id"]
    r = client.put(f"/api/v1/deliveries/{did}", headers=role_users["operator"]["headers"],
                   json={"work_date": created.json()["work_date"], "company": "X"})
    assert r.status_code == 403, r.text


def test_update_delivery_404(client, role_users):
    r = client.put("/api/v1/deliveries/99999999", headers=role_users["supervisor"]["headers"],
                   json={"work_date": _date(), "company": "X"})
    assert r.status_code == 404, r.text


# ---- Bales: edit ----
def test_update_bale(client, role_users):
    sup = role_users["supervisor"]["headers"]
    created = client.post("/api/v1/bales", headers=sup,
                          json={"work_date": _date(), "grn": "G1", "weight_kg": 5})
    assert created.status_code == 201, created.text
    bid = created.json()["id"]
    edited = client.put(f"/api/v1/bales/{bid}", headers=sup,
                        json={"work_date": created.json()["work_date"], "grn": "G2", "weight_kg": 12})
    assert edited.status_code == 200, edited.text
    assert edited.json()["grn"] == "G2"
    assert edited.json()["weight_kg"] == 12


# ---- Fuel dips: edit ----
def test_update_fuel_dip(client, role_users):
    sup = role_users["supervisor"]["headers"]
    created = client.post("/api/v1/fuel-dips", headers=sup,
                          json={"work_date": _date(), "shift": "Day", "open_dip": 100})
    assert created.status_code == 201, created.text
    fid = created.json()["id"]
    edited = client.put(f"/api/v1/fuel-dips/{fid}", headers=sup,
                        json={"work_date": created.json()["work_date"], "shift": "Night",
                              "open_dip": 100, "close_dip": 40, "actual_usage": 60})
    assert edited.status_code == 200, edited.text
    assert edited.json()["shift"] == "Night"
    assert edited.json()["actual_usage"] == 60


# ---- Monthly stock: soft delete + revive on upsert ----
def test_stock_delete_then_revive(client, role_users):
    sup = role_users["supervisor"]["headers"]
    mgr = role_users["manager"]["headers"]
    period = _period()

    created = client.put(f"/api/v1/monthly-stock/{period}", headers=sup,
                         json={"period": period, "diesel_eom": 100})
    assert created.status_code == 200, created.text

    # Manager deletes -> 204 and it disappears from the list.
    deleted = client.delete(f"/api/v1/monthly-stock/{period}", headers=mgr)
    assert deleted.status_code == 204, deleted.text
    listing = client.get("/api/v1/monthly-stock", headers=sup).json()
    assert period not in [r["period"] for r in listing]

    # Re-upserting the SAME period revives the row (no unique-constraint crash).
    revived = client.put(f"/api/v1/monthly-stock/{period}", headers=sup,
                         json={"period": period, "diesel_eom": 250})
    assert revived.status_code == 200, revived.text
    assert revived.json()["diesel_eom"] == 250
    listing2 = client.get("/api/v1/monthly-stock", headers=sup).json()
    assert period in [r["period"] for r in listing2]


@pytest.mark.parametrize("role,expected", [
    ("operator", 403), ("supervisor", 403), ("manager", 204), ("admin", 204),
])
def test_stock_delete_requires_manager(client, role_users, role, expected):
    period = _period()
    client.put(f"/api/v1/monthly-stock/{period}", headers=role_users["supervisor"]["headers"],
               json={"period": period, "diesel_eom": 1})
    r = client.delete(f"/api/v1/monthly-stock/{period}", headers=role_users[role]["headers"])
    assert r.status_code == expected, f"{role}: {r.status_code} {r.text}"
