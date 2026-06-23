"""Run-rate forecast: the analytics summary projects period output while the
window is still open (today falls inside start..end)."""
from datetime import date, timedelta
import itertools

_counter = itertools.count(1)


def test_summary_forecast_present_for_inprogress_window(client, admin_headers):
    today = date.today()
    # A window centred on today: 5 days elapsed, 11 total -> in progress.
    start = today - timedelta(days=5)
    end = today + timedelta(days=5)

    # Log output dated today so total_qty > 0 inside the window.
    created = client.post("/api/v1/shifts", headers=admin_headers,
                          json={"work_date": today.isoformat(), "shift": "Day", "qty": 1000})
    assert created.status_code in (201, 409), created.text  # 409 if a prior test logged today

    r = client.get("/api/v1/analytics/summary", headers=admin_headers,
                   params={"start": start.isoformat(), "end": end.isoformat()})
    assert r.status_code == 200, r.text
    fc = r.json()["forecast"]
    assert fc is not None, "expected a forecast for an in-progress window"
    assert fc["elapsed_days"] < fc["total_days"]
    # Projected total scales up from the elapsed run-rate.
    assert fc["projected_qty"] >= r.json()["kpis"]["total_qty"]


def test_summary_no_forecast_for_completed_window(client, admin_headers):
    # A fully-past window (well before today) is complete -> no projection.
    start = date(2021, 1, 1)
    end = date(2021, 1, 31)
    r = client.get("/api/v1/analytics/summary", headers=admin_headers,
                   params={"start": start.isoformat(), "end": end.isoformat()})
    assert r.status_code == 200, r.text
    assert r.json()["forecast"] is None
