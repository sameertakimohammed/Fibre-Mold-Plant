"""Audit-trail contract: authenticated writes are captured with the right actor,
and the tamper-evident hash chain verifies clean."""
import itertools

from conftest import ADMIN_USERNAME

_counter = itertools.count(1)


def _date():
    n = next(_counter)
    return f"2023-{(n % 12) + 1:02d}-{(n % 27) + 1:02d}"


def test_write_is_audited_with_actor(client, admin_headers):
    # Perform an authenticated write as admin.
    created = client.post("/api/v1/shifts", headers=admin_headers,
                        json={"work_date": _date(), "shift": "Day", "qty": 42})
    assert created.status_code == 201, created.text
    entity_id = str(created.json()["id"])

    # The audit log (admin only) should contain a create row for this shift,
    # attributed to the admin actor.
    resp = client.get("/api/v1/audit", headers=admin_headers,
                     params={"entity_type": "ProductionShift", "entity_id": entity_id})
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert rows, "expected at least one audit row for the new shift"
    row = rows[0]
    assert row["entity_type"] == "ProductionShift"
    assert row["action"] == "create"
    assert row["actor_username"] == ADMIN_USERNAME


def test_audit_filter_by_actor(client, admin_headers):
    # Generate a write, then confirm the actor filter returns admin rows only.
    client.post("/api/v1/shifts", headers=admin_headers,
                json={"work_date": _date(), "shift": "Afternoon", "qty": 7})
    resp = client.get("/api/v1/audit", headers=admin_headers,
                     params={"actor": ADMIN_USERNAME})
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert rows, "expected audit rows for the admin actor"
    assert all(r["actor_username"] == ADMIN_USERNAME for r in rows)


def test_audit_chain_verifies_ok(client, admin_headers):
    # Do at least one write first so the chain is non-trivial.
    client.post("/api/v1/shifts", headers=admin_headers,
                json={"work_date": _date(), "shift": "Night", "qty": 3})
    resp = client.get("/api/v1/audit/verify", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True, body
    assert body["broken_at_id"] is None
    assert body["checked"] >= 1
