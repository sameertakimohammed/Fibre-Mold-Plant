"""CSV export of the shift detail for a date range.

The xlsx/pdf/pptx reports are formatted for reading; this is the raw-rows
companion so the plant can pull shift figures straight into their own
spreadsheets. It reuses collect_report_data() so the rows (and the soft-delete
filter) match every other report and the dashboard KPIs.
"""
import csv
import io
from datetime import date

from sqlalchemy.orm import Session

from .report_data import collect_report_data, report_filename

# (attribute, column header) in the order they appear in the CSV. Mirrors the
# shift model fields operators care about for analysis.
_COLUMNS: list[tuple[str, str]] = [
    ("work_date", "Date"),
    ("shift", "Shift"),
    ("qty", "Total Trays"),
    ("p30s", "30's Small"), ("p30l", "30's Large"), ("p20n", "20's Normal"),
    ("p12n", "12's Normal"), ("p12hf", "12's Half Face"), ("p12ff", "12's Full Face"),
    ("p4cup", "4's Cup"), ("p2cup", "2's Cup"),
    ("hp1", "HP1"), ("hp2", "HP2"), ("hp3", "HP3"),
    ("hp4", "HP4"), ("hp5", "HP5"), ("hp6", "HP6"),
    ("speed", "Speed/hr"),
    ("fuel_open", "Fuel Open L"), ("fuel_close", "Fuel Close L"), ("fuel_use", "Fuel Used L"),
    ("water_meter", "Water m3"),
    ("prod_hours", "Prod Hours"), ("sched_hours", "Sched Hours"),
    ("downtime_min", "Downtime min"),
    ("clean_min", "Cleaning min"), ("mold_min", "Mold min"), ("other_min", "Other min"),
    ("repulped", "Re-pulped"),
    ("carton_bales", "Carton Bales"),
    ("comment", "Comment"),
]


def build_report_csv(db: Session, start: date | None, end: date | None,
                     period_label: str = "Production") -> tuple[bytes, str]:
    """Return (utf-8 csv bytes with BOM, filename) of shift detail for the range.

    A UTF-8 BOM is prepended so Excel opens the file in the correct encoding.
    """
    data = collect_report_data(db, start, end, period_label)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([header for _, header in _COLUMNS])
    for s in data.shifts:
        row = []
        for attr, _ in _COLUMNS:
            val = getattr(s, attr, "")
            # Shift is an enum; emit its string value.
            if attr == "shift":
                val = getattr(val, "value", val)
            elif attr == "work_date":
                val = val.isoformat() if val else ""
            row.append(val)
        writer.writerow(row)

    payload = ("﻿" + buf.getvalue()).encode("utf-8")
    return payload, report_filename("csv", start, end, period_label)
