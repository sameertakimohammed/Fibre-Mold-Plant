"""PDF report builder (reportlab Platypus).

A printable, presentation-ready production report: branded header, headline KPI
cards, full KPI table, then shift-detail and deliveries tables that flow across
pages. Figures come from collect_report_data() — the same source as the xlsx and
pptx builders.

build_report_pdf(db, start, end[, period_label]) -> (pdf_bytes, filename)
"""
import io
from datetime import date
from xml.sax.saxutils import escape

from sqlalchemy.orm import Session
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether,
)

from .report_data import collect_report_data, report_filename

AMBER = colors.HexColor("#F5A623")
INK = colors.HexColor("#1A1205")
DARK = colors.HexColor("#222A33")
MUTE = colors.HexColor("#667085")
LINE = colors.HexColor("#D0D5DD")
ZEBRA = colors.HexColor("#F7F8FA")


def _fmt(n) -> str:
    """Thousands-separated; keep one decimal only when the value isn't whole."""
    if isinstance(n, float) and not n.is_integer():
        return f"{n:,.1f}"
    return f"{int(round(n)):,}"


def _styles():
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=ss["Title"], fontName="Helvetica-Bold",
                                 fontSize=20, textColor=colors.white, leading=24),
        "sub": ParagraphStyle("s", parent=ss["Normal"], fontName="Helvetica",
                              fontSize=10, textColor=colors.white, leading=14),
        "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold",
                             fontSize=12, textColor=INK, spaceBefore=14, spaceAfter=6),
        "kval": ParagraphStyle("kv", parent=ss["Normal"], fontName="Helvetica-Bold",
                               fontSize=17, textColor=INK, alignment=TA_CENTER, leading=20),
        "klabel": ParagraphStyle("kl", parent=ss["Normal"], fontName="Helvetica",
                                fontSize=7.5, textColor=MUTE, alignment=TA_CENTER, leading=10),
        "cell": ParagraphStyle("c", parent=ss["Normal"], fontName="Helvetica", fontSize=8, leading=10),
        "foot": ParagraphStyle("f", parent=ss["Normal"], fontName="Helvetica",
                              fontSize=7.5, textColor=MUTE, alignment=TA_CENTER),
    }


def _header(title, span, st):
    """Full-width amber title band."""
    inner = [
        [Paragraph(f"Fibre Mold Plant — {title} Report", st["title"])],
        [Paragraph(f"Golden Manufacturers · Recycling Department &nbsp;|&nbsp; Period: {span}", st["sub"])],
    ]
    t = Table(inner, colWidths=[170 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), AMBER),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (0, 0), 12),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 12),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
    ]))
    return t


def _kpi_cards(m, st):
    """A row of headline metric cards."""
    cards = [
        (_fmt(m["total_qty"]), "TOTAL TRAYS"),
        (_fmt(m["avg_per_day"]), "AVG / DAY"),
        (f'{_fmt(m["fuel_eff"])}', "FUEL L / 1K TRAYS"),
        (f'{_fmt(m["downtime_pct"])}%', "DOWNTIME"),
        (f'{_fmt(m["repulp_rate"])}%', "RE-PULP RATE"),
    ]
    cells = [[Paragraph(v, st["kval"]) for v, _ in cards],
             [Paragraph(l, st["klabel"]) for _, l in cards]]
    w = 170 * mm / len(cards)
    t = Table(cells, colWidths=[w] * len(cards))
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ZEBRA),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.white),
        ("LINEABOVE", (0, 0), (-1, 0), 2, AMBER),
        ("TOPPADDING", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _kpi_table(m, st):
    rows = [
        ("Total trays produced", _fmt(m["total_qty"])),
        ("Active production days", _fmt(m["active_days"])),
        ("Average trays / day", _fmt(m["avg_per_day"])),
        ("Total diesel burned (L)", _fmt(m["total_fuel"])),
        ("Fuel efficiency (L / 1k trays)", _fmt(m["fuel_eff"])),
        ("Total downtime (hrs)", _fmt(m["total_downtime_hrs"])),
        ("Downtime rate (% of scheduled)", f'{_fmt(m["downtime_pct"])}%'),
        ("Trays re-pulped", _fmt(m["total_repulped"])),
        ("Re-pulp rate (%)", f'{_fmt(m["repulp_rate"])}%'),
        ("30's delivered", _fmt(m["tray30"])),
        ("12's delivered", _fmt(m["tray12"])),
        ("Pallets shipped", _fmt(m["pallets"])),
    ]
    data = [[Paragraph(k, st["cell"]),
             Paragraph(f'<b>{v}</b>', ParagraphStyle("rv", parent=st["cell"], alignment=TA_RIGHT))]
            for k, v in rows]
    t = Table(data, colWidths=[120 * mm, 50 * mm])
    t.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, ZEBRA]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def _data_table(headers, rows, col_widths, st):
    head = [Paragraph(f'<font color="white"><b>{escape(str(h))}</b></font>', st["cell"]) for h in headers]
    body = [head]
    for r in rows:
        body.append([Paragraph(escape(str(c)), st["cell"]) for c in r])
    t = Table(body, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def build_report_pdf(
    db: Session,
    start: date | None = None,
    end: date | None = None,
    period_label: str = "Production",
) -> tuple[bytes, str]:
    data = collect_report_data(db, start, end, period_label)
    m = data.metrics
    st = _styles()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"Fibre Mold Plant {data.period_label} Report", author="Golden Manufacturers",
    )

    flow = [
        _header(data.period_label, data.span, st),
        Spacer(1, 10),
        KeepTogether([Paragraph("Key Performance", st["h2"]), _kpi_cards(m, st)]),
        Spacer(1, 8),
        _kpi_table(m, st),
    ]

    # Shift detail
    flow.append(Paragraph(f"Shift Detail ({m['shift_count']} shifts)", st["h2"]))
    if data.shifts:
        rows = [[s.work_date.isoformat(), s.shift.value, _fmt(s.qty), _fmt(s.speed),
                 _fmt(s.prod_hours), _fmt(s.fuel_use), _fmt(s.downtime_min), _fmt(s.repulped)]
                for s in data.shifts]
        flow.append(_data_table(
            ["Date", "Shift", "Trays", "Speed", "Prod Hrs", "Fuel (L)", "Down (min)", "Re-pulp"],
            rows, [24 * mm, 20 * mm, 24 * mm, 18 * mm, 20 * mm, 22 * mm, 22 * mm, 20 * mm], st))
    else:
        flow.append(Paragraph("No production shifts in this period.", st["cell"]))

    # Deliveries
    flow.append(Paragraph(f"Deliveries ({m['delivery_count']})", st["h2"]))
    if data.deliveries:
        rows = [[d.work_date.isoformat(), (d.company or "")[:40], _fmt(d.tray30),
                 _fmt(d.tray12n), _fmt(d.tray12ff), _fmt(d.pallets)]
                for d in data.deliveries]
        flow.append(_data_table(
            ["Date", "Customer", "30's", "12's Normal", "12's FF", "Pallets"],
            rows, [24 * mm, 56 * mm, 22 * mm, 24 * mm, 22 * mm, 22 * mm], st))
    else:
        flow.append(Paragraph("No deliveries in this period.", st["cell"]))

    flow.append(Spacer(1, 14))
    flow.append(Paragraph(
        "Generated by the Fibre Mold Plant dashboard · figures exclude voided entries.",
        st["foot"]))

    doc.build(flow)
    buf.seek(0)
    return buf.getvalue(), report_filename("pdf", start, end, period_label)
