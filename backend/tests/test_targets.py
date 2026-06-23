"""KPI targets: CRUD, role boundary (manager+ to set), metric validation, and
that the analytics summary surfaces the configured targets."""
import pytest


def test_list_targets_any_authenticated(client, role_users):
    r = client.get("/api/v1/targets", headers=role_users["operator"]["headers"])
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


@pytest.mark.parametrize("role,expected", [
    ("operator", 403), ("supervisor", 403), ("manager", 200), ("admin", 200),
])
def test_set_target_requires_manager(client, role_users, role, expected):
    r = client.put("/api/v1/targets/avg_per_day", headers=role_users[role]["headers"],
                   json={"value": 9000})
    assert r.status_code == expected, f"{role}: {r.status_code} {r.text}"


def test_set_then_get_target(client, role_users):
    mgr = role_users["manager"]["headers"]
    r = client.put("/api/v1/targets/fuel_eff", headers=mgr, json={"value": 12.5})
    assert r.status_code == 200, r.text
    assert r.json()["metric"] == "fuel_eff"
    assert r.json()["value"] == 12.5

    # Upsert (idempotent): a second PUT updates the same row, not a duplicate.
    r2 = client.put("/api/v1/targets/fuel_eff", headers=mgr, json={"value": 11.0})
    assert r2.status_code == 200, r2.text
    listing = client.get("/api/v1/targets", headers=mgr).json()
    fuel = [t for t in listing if t["metric"] == "fuel_eff"]
    assert len(fuel) == 1 and fuel[0]["value"] == 11.0


def test_set_target_unknown_metric_422(client, role_users):
    r = client.put("/api/v1/targets/not_a_metric", headers=role_users["manager"]["headers"],
                   json={"value": 1})
    assert r.status_code == 422, r.text


def test_set_target_negative_rejected_422(client, role_users):
    r = client.put("/api/v1/targets/downtime_pct", headers=role_users["manager"]["headers"],
                   json={"value": -3})
    assert r.status_code == 422, r.text


def test_delete_target(client, role_users):
    mgr = role_users["manager"]["headers"]
    client.put("/api/v1/targets/repulp_rate", headers=mgr, json={"value": 4})
    r = client.delete("/api/v1/targets/repulp_rate", headers=mgr)
    assert r.status_code == 204, r.text
    listing = client.get("/api/v1/targets", headers=mgr).json()
    assert "repulp_rate" not in [t["metric"] for t in listing]


def test_summary_includes_targets(client, role_users, admin_headers):
    client.put("/api/v1/targets/avg_per_day", headers=role_users["manager"]["headers"],
               json={"value": 8500})
    r = client.get("/api/v1/analytics/summary", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "targets" in body
    assert body["targets"].get("avg_per_day") == 8500
