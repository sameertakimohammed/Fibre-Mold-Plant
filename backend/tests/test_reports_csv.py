"""CSV export: the raw shift-detail download streams text/csv with a header row
and one line per shift in the range."""
import itertools

_counter = itertools.count(1)


def _date():
    n = next(_counter)
    return f"2022-{(n % 12) + 1:02d}-{(n % 27) + 1:02d}"


def test_report_csv_streams_shift_rows(client, admin_headers):
    d = _date()
    created = client.post("/api/v1/shifts", headers=admin_headers,
                          json={"work_date": d, "shift": "Day", "qty": 1234})
    assert created.status_code == 201, created.text

    r = client.get("/api/v1/reports/report.csv", headers=admin_headers,
                   params={"start": d, "end": d})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers.get("content-disposition", "")

    text = r.content.decode("utf-8-sig")  # tolerate the Excel BOM
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert lines, "CSV had no rows"
    header = lines[0]
    assert "Date" in header and "Total Trays" in header
    # The shift we created (qty 1234) should appear in a data row.
    assert any("1234" in ln for ln in lines[1:]), text


def test_report_csv_requires_auth(client):
    r = client.get("/api/v1/reports/report.csv")
    assert r.status_code == 401, r.text
