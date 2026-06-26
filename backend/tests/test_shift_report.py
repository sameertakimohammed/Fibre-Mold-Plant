"""End-of-shift report sheet: the extra log fields round-trip, the PDF renders,
partial edits don't wipe the report fields, and the scheduler job is safe."""


def _payload(**over):
    body = {
        "work_date": "2026-07-01", "shift": "Day",
        "qty": 9930, "hp1": 2001, "hp2": 2003, "labelling": 5000,
        "fuel_use": 200, "fuel_open": 6900, "fuel_close": 6300,
        "downtime_min": 30, "sched_hours": 8, "water_meter": 12, "carton_bales": 1.5,
        "supervisor": "Munesh/Asenaca", "staff_count": 4, "casual_count": 5,
        "absenteeism": "-", "stock_notes": "Quality 1 – 25,200pcs (6 pallets)",
        "delivery_notes": "Q2 – 20,000pcs (30's small)",
        "machines": {
            "HGHY": {"paid_hours": 8, "run_hours": 7.5, "target_per_hr": 1400,
                     "actual_per_hr": 1324, "operators": "Former – John/Munesh",
                     "product_detail": "30's Small"},
            "HT1": {"paid_hours": 8, "run_hours": 6, "target_per_hr": 250,
                    "actual_per_hr": 333, "operators": "Laisani", "product_detail": "12's Normal"},
        },
        "comment": "Down Time: 30 minutes — washing the molds.",
    }
    body.update(over)
    return body


def test_create_shift_with_report_fields_roundtrips(client, admin_headers):
    r = client.post("/api/v1/shifts", headers=admin_headers, json=_payload())
    assert r.status_code in (201, 409), r.text
    if r.status_code == 409:
        # Re-fetch the existing row for this date+shift.
        rows = client.get("/api/v1/shifts?start=2026-07-01&end=2026-07-01", headers=admin_headers).json()
        body = next(s for s in rows if s["shift"] == "Day")
    else:
        body = r.json()
    assert body["supervisor"] == "Munesh/Asenaca"
    assert body["staff_count"] == 4 and body["casual_count"] == 5
    assert body["machines"]["HGHY"]["actual_per_hr"] == 1324
    assert body["machines"]["HGHY"]["operators"] == "Former – John/Munesh"
    assert body["stock_notes"].startswith("Quality 1")


def test_shift_report_pdf_download(client, admin_headers):
    r = client.post("/api/v1/shifts", headers=admin_headers,
                    json=_payload(work_date="2026-07-02"))
    assert r.status_code in (201, 409), r.text
    if r.status_code == 201:
        sid = r.json()["id"]
    else:
        rows = client.get("/api/v1/shifts?start=2026-07-02&end=2026-07-02", headers=admin_headers).json()
        sid = next(s["id"] for s in rows if s["shift"] == "Day")
    rep = client.get(f"/api/v1/shifts/{sid}/report", headers=admin_headers)
    assert rep.status_code == 200, rep.text
    assert rep.headers["content-type"] == "application/pdf"
    assert rep.content[:5] == b"%PDF-"
    assert "shift-report-2026-07-02-day.pdf" in rep.headers.get("content-disposition", "")


def test_partial_update_preserves_report_fields(client, admin_headers, role_users):
    # Create with full report fields...
    r = client.post("/api/v1/shifts", headers=admin_headers,
                    json=_payload(work_date="2026-07-03"))
    assert r.status_code in (201, 409), r.text
    rows = client.get("/api/v1/shifts?start=2026-07-03&end=2026-07-03", headers=admin_headers).json()
    sid = next(s["id"] for s in rows if s["shift"] == "Day")
    # ...then a numbers-only edit (as the quick-edit modal sends) must NOT wipe them.
    up = client.put(f"/api/v1/shifts/{sid}", headers=role_users["supervisor"]["headers"],
                    json={"work_date": "2026-07-03", "shift": "Day", "qty": 10000,
                          "sched_hours": 8, "downtime_min": 30})
    assert up.status_code == 200, up.text
    body = up.json()
    assert body["qty"] == 10000                       # the edit applied
    assert body["supervisor"] == "Munesh/Asenaca"     # preserved
    assert body["machines"]["HGHY"]["actual_per_hr"] == 1324  # preserved


def test_report_pdf_404_for_missing_shift(client, admin_headers):
    assert client.get("/api/v1/shifts/999999/report", headers=admin_headers).status_code == 404


def test_shift_report_job_noop_when_disabled():
    """The scheduler job must be a safe no-op when the feature is off (default)."""
    from app.services.scheduler import _email_shift_report
    # shift_report_enabled defaults False in the test env → returns without sending/raising.
    _email_shift_report("Day", [0])


def test_build_shift_report_pdf_handles_empty_machines(client, admin_headers):
    """A legacy-style shift with no machines map still renders a PDF."""
    from app.services.report_shift_pdf import build_shift_report_pdf
    from app.models.production import ProductionShift, Shift
    from datetime import date
    s = ProductionShift(work_date=date(2026, 7, 9), shift=Shift.night, qty=5000, machines=None)
    data, fname = build_shift_report_pdf(s)
    assert data[:5] == b"%PDF-"
    assert fname == "shift-report-2026-07-09-night.pdf"
