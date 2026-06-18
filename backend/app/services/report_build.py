"""Reusable monthly/period report builder.

The openpyxl workbook construction used to live inline in routers/reports.py.
It is refactored here so BOTH the /api/reports/monthly.xlsx route AND the
scheduled report-email job build the identical workbook. The route streams the
bytes; the scheduler attaches them to an email.

build_report_xlsx(db, start, end) -> (xlsx_bytes, filename)
"""
import io
from datetime import date

from sqlalchemy.orm import Session
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from ..models.production import ProductionShift
from ..models.operations import Delivery

AMBER = "F5A623"
INK = "1A1205"
HEAD_FILL = PatternFill("solid", fgColor="222A33")
HEAD_FONT = Font(bold=True, color="FFFFFF", name="Arial", size=10)
TITLE_FONT = Font(bold=True, size=15, name="Arial")
LABEL_FONT = Font(bold=True, name="Arial", size=10)
THIN = Side(style="thin", color="D0D5DD")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _autofit(ws):
    for col in ws.columns:
        width = max((len(str(c.value)) for c in col if c.value is not None), default=8)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(width + 2, 10), 40)


def _header_row(ws, row, headers):
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=i, value=h)
        c.fill = HEAD_FILL; c.font = HEAD_FONT
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = BORDER


def build_report_xlsx(
    db: Session,
    start: date | None = None,
    end: date | None = None,
) -> tuple[bytes, str]:
    """Build the production report workbook for the given date range.

    Returns (xlsx_bytes, filename). Soft-deleted rows are excluded so the report
    matches the dashboard KPIs.
    """
    q = db.query(ProductionShift).filter(ProductionShift.deleted_at.is_(None))
    if start:
        q = q.filter(ProductionShift.work_date >= start)
    if end:
        q = q.filter(ProductionShift.work_date <= end)
    shifts = q.order_by(ProductionShift.work_date, ProductionShift.shift).all()

    dq = db.query(Delivery).filter(Delivery.deleted_at.is_(None))
    if start:
        dq = dq.filter(Delivery.work_date >= start)
    if end:
        dq = dq.filter(Delivery.work_date <= end)
    deliveries = dq.order_by(Delivery.work_date).all()

    tot_qty = sum(s.qty for s in shifts)
    tot_fuel = sum(s.fuel_use for s in shifts)
    tot_down = sum(s.downtime_min for s in shifts)
    tot_sched = sum(s.sched_hours for s in shifts) or 0
    tot_repulp = sum(s.repulped for s in shifts)
    active = len({s.work_date for s in shifts if s.qty > 0})
    span = f"{start} to {end}" if start and end else "All time"

    wb = Workbook()

    # ---- Summary sheet ----
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "Fibre Mold Plant — Production Report"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = f"Golden Manufacturers · Period: {span}"
    ws["A2"].font = Font(italic=True, color="667085", name="Arial", size=10)

    rows = [
        ("Total trays produced", round(tot_qty), "#,##0"),
        ("Active production days", active, "0"),
        ("Average trays / day", round(tot_qty / active) if active else 0, "#,##0"),
        ("Total diesel burned (L)", round(tot_fuel), "#,##0"),
        ("Fuel efficiency (L / 1k trays)", round(tot_fuel / tot_qty * 1000, 1) if tot_qty else 0, "#,##0.0"),
        ("Total downtime (hrs)", round(tot_down / 60, 1), "#,##0.0"),
        ("Downtime rate (% of scheduled)", round(tot_down / 60 / tot_sched * 100, 1) if tot_sched else 0, "#,##0.0"),
        ("Trays re-pulped", round(tot_repulp), "#,##0"),
        ("30's delivered", round(sum(d.tray30 for d in deliveries)), "#,##0"),
        ("12's delivered", round(sum(d.tray12n + d.tray12ff for d in deliveries)), "#,##0"),
        ("Pallets shipped", round(sum(d.pallets for d in deliveries)), "#,##0"),
    ]
    r = 4
    for label, val, nfmt in rows:
        ws.cell(row=r, column=1, value=label).font = LABEL_FONT
        c = ws.cell(row=r, column=2, value=val)
        c.number_format = nfmt
        c.alignment = Alignment(horizontal="right")
        r += 1
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 16

    # ---- Shift detail sheet ----
    sd = wb.create_sheet("Shift Detail")
    headers = ["Date", "Shift", "Trays", "Speed", "Prod Hrs", "Sched Hrs",
               "Fuel Used (L)", "Downtime (min)", "Re-pulped", "Comment"]
    _header_row(sd, 1, headers)
    for i, s in enumerate(shifts, 2):
        vals = [s.work_date.isoformat(), s.shift.value, s.qty, s.speed, s.prod_hours,
                s.sched_hours, s.fuel_use, s.downtime_min, s.repulped, s.comment or ""]
        for j, v in enumerate(vals, 1):
            c = sd.cell(row=i, column=j, value=v)
            if isinstance(v, (int, float)):
                c.number_format = "#,##0.#"
            c.border = BORDER
    sd.freeze_panes = "A2"
    _autofit(sd)

    # ---- Deliveries sheet ----
    dl = wb.create_sheet("Deliveries")
    dheaders = ["Date", "Customer", "30's", "12's Normal", "12's Full Face", "Pallets", "Comment"]
    _header_row(dl, 1, dheaders)
    for i, d in enumerate(deliveries, 2):
        vals = [d.work_date.isoformat(), d.company, d.tray30, d.tray12n, d.tray12ff, d.pallets, d.comment or ""]
        for j, v in enumerate(vals, 1):
            c = dl.cell(row=i, column=j, value=v)
            if isinstance(v, (int, float)):
                c.number_format = "#,##0.#"
            c.border = BORDER
    dl.freeze_panes = "A2"
    _autofit(dl)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname = f"fmp-report-{start or 'all'}-{end or ''}.xlsx".replace(" ", "")
    return buf.getvalue(), fname
