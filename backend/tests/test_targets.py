"""KPI targets: per-cadence CRUD (daily/weekly/monthly), role boundary
(manager+ to set), metric/period validation, seeded defaults, and that the
analytics summary surfaces the cadence-appropriate targets."""
import pytest


def test_list_targets_any_authenticated(client, role_users):
    r = client.get("/api/v1/targets", headers=role_users["operator"]["headers"])
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


def test_defaults_seeded(client, admin_headers):
    """A fresh DB is seeded with the supervisor's figures (one row per cadence)."""
    rows = client.get("/api/v1/targets", headers=admin_headers).json()
    by = {(t["metric"], t["period"]): t["value"] for t in rows}
    assert by[("prod_30", "daily")] == 30450
    assert by[("prod_30", "monthly")] == 619150
    assert by[("prod_12", "daily")] == 33600
    assert by[("diesel", "monthly")] == 21070
    # Each volume/rate metric carries all three cadences.
    for metric in ("prod_30", "prod_12", "diesel", "fuel_eff", "downtime_pct", "repulp_rate"):
        periods = {t["period"] for t in rows if t["metric"] == metric}
        assert periods == {"daily", "weekly", "monthly"}, metric


@pytest.mark.parametrize("role,expected", [
    ("operator", 403), ("supervisor", 403), ("manager", 200), ("admin", 200),
])
def test_set_target_requires_manager(client, role_users, role, expected):
    r = client.put("/api/v1/targets/monthly/prod_30", headers=role_users[role]["headers"],
                   json={"value": 600000})
    assert r.status_code == expected, f"{role}: {r.status_code} {r.text}"


def test_set_then_get_target(client, role_users):
    mgr = role_users["manager"]["headers"]
    r = client.put("/api/v1/targets/daily/fuel_eff", headers=mgr, json={"value": 22.0})
    assert r.status_code == 200, r.text
    assert r.json()["metric"] == "fuel_eff"
    assert r.json()["period"] == "daily"
    assert r.json()["value"] == 22.0

    # Upsert (idempotent): a second PUT updates the same (metric, period) row.
    r2 = client.put("/api/v1/targets/daily/fuel_eff", headers=mgr, json={"value": 21.0})
    assert r2.status_code == 200, r2.text
    listing = client.get("/api/v1/targets", headers=mgr).json()
    match = [t for t in listing if t["metric"] == "fuel_eff" and t["period"] == "daily"]
    assert len(match) == 1 and match[0]["value"] == 21.0


def test_same_metric_distinct_per_period(client, role_users):
    """daily/weekly/monthly are independent rows for the same metric."""
    mgr = role_users["manager"]["headers"]
    client.put("/api/v1/targets/daily/diesel", headers=mgr, json={"value": 700})
    client.put("/api/v1/targets/weekly/diesel", headers=mgr, json={"value": 4900})
    listing = client.get("/api/v1/targets", headers=mgr).json()
    vals = {t["period"]: t["value"] for t in listing if t["metric"] == "diesel"}
    assert vals["daily"] == 700 and vals["weekly"] == 4900


def test_set_target_unknown_metric_422(client, role_users):
    r = client.put("/api/v1/targets/monthly/not_a_metric", headers=role_users["manager"]["headers"],
                   json={"value": 1})
    assert r.status_code == 422, r.text


def test_set_target_unknown_period_422(client, role_users):
    r = client.put("/api/v1/targets/hourly/prod_30", headers=role_users["manager"]["headers"],
                   json={"value": 1})
    assert r.status_code == 422, r.text


def test_set_target_negative_rejected_422(client, role_users):
    r = client.put("/api/v1/targets/monthly/downtime_pct", headers=role_users["manager"]["headers"],
                   json={"value": -3})
    assert r.status_code == 422, r.text


def test_delete_target(client, role_users):
    mgr = role_users["manager"]["headers"]
    client.put("/api/v1/targets/weekly/repulp_rate", headers=mgr, json={"value": 4})
    r = client.delete("/api/v1/targets/weekly/repulp_rate", headers=mgr)
    assert r.status_code == 204, r.text
    listing = client.get("/api/v1/targets", headers=mgr).json()
    assert ("repulp_rate", "weekly") not in [(t["metric"], t["period"]) for t in listing]


def test_summary_uses_monthly_targets_by_default(client, role_users, admin_headers):
    """No date window == the whole-month default, so monthly targets apply."""
    client.put("/api/v1/targets/monthly/prod_30", headers=role_users["manager"]["headers"],
               json={"value": 620000})
    r = client.get("/api/v1/analytics/summary", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["target_period"] == "monthly"
    assert body["targets"].get("prod_30") == 620000


def test_summary_daily_window_uses_daily_target(client, role_users, admin_headers):
    """A 1-day window resolves to the daily volume target, not the monthly one."""
    mgr = role_users["manager"]["headers"]
    client.put("/api/v1/targets/daily/prod_30", headers=mgr, json={"value": 31000})
    r = client.get("/api/v1/analytics/summary?start=2026-05-10&end=2026-05-10",
                   headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["target_period"] == "daily"
    assert body["targets"].get("prod_30") == 31000


def test_summary_one_sided_window_has_no_cadence(client, admin_headers):
    """A window with only start (open-ended) has no cadence: target_period None."""
    r = client.get("/api/v1/analytics/summary?start=2026-05-10", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["target_period"] is None
    assert "prod_30" not in body["targets"]            # volume omitted, no cadence


def test_summary_custom_range_drops_volume_keeps_rate(client, role_users, admin_headers):
    """A 10-day span has no cadence: volume targets drop, rate targets fall back."""
    r = client.get("/api/v1/analytics/summary?start=2026-05-05&end=2026-05-14",
                   headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["target_period"] is None
    assert "prod_30" not in body["targets"]          # volume: no matching cadence
    assert body["targets"].get("repulp_rate") is not None  # rate: falls back
