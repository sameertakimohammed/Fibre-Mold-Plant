"""Per-shift report PDF (reportlab Platypus) — a digital twin of the Team
Leader's paper "Recycling Production Report" sheet.

build_shift_report_pdf(shift) -> (pdf_bytes, filename)

Quantities come from the typed shift columns (qty -> HGHY former, hp1..hp6 ->
HT1..HT6, labelling -> Label Applicator); the extra per-machine attributes
(hours, targets, operators, product detail) come from shift.machines.
"""
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether,
)

from ..models.production import ProductionShift

AMBER = colors.HexColor("#F5A623")
INK = colors.HexColor("#1A1205")
DARK = colors.HexColor("#222A33")
MUTE = colors.HexColor("#667085")
LINE = colors.HexColor("#D0D5DD")
ZEBRA = colors.HexColor("#F7F8FA")

# (code, display label, the typed shift column holding that machine's quantity)
MACHINES = [
    ("HGHY", "HGHY (Former)", "qty"),
    ("HT1", "HT1", "hp1"), ("HT2", "HT2", "hp2"), ("HT3", "HT3", "hp3"),
    ("HT4", "HT4", "hp4"), ("HT5", "HT5", "hp5"), ("HT6", "HT6", "hp6"),
    ("LABEL", "Label Applicator", "labelling"),
]

SHIFT_WINDOW = {"Day": "7:30am – 3:30pm", "Afternoon": "3:30pm – 11:30pm", "Night": "11:30pm – 7:30am"}


def _fmt(n) -> str:
    try:
        n = float(n or 0)
    except (TypeError, ValueError):
        return str(n)
    if not n.is_integer():
        return f"{n:,.1f}"
    return f"{int(round(n)):,}"


def _styles():
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=ss["Title"], fontName="Helvetica-Bold",
                                fontSize=18, textColor=colors.white, leading=22),
        "sub": ParagraphStyle("s", parent=ss["Normal"], fontName="Helvetica",
                              fontSize=10, textColor=colors.white, leading=14),
        "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold",
                             fontSize=11, textColor=INK, spaceBefore=10, spaceAfter=4),
        "cell": ParagraphStyle("c", parent=ss["Normal"], fontName="Helvetica", fontSize=8, leading=10),
        "cellc": ParagraphStyle("cc", parent=ss["Normal"], fontName="Helvetica", fontSize=8,
                                leading=10, alignment=TA_CENTER),
        "head": ParagraphStyle("hd", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=8,
                               leading=10, textColor=colors.white, alignment=TA_CENTER),
        "foot": ParagraphStyle("f", parent=ss["Normal"], fontName="Helvetica",
                               fontSize=7.5, textColor=MUTE, alignment=TA_CENTER),
        "note": ParagraphStyle("n", parent=ss["Normal"], fontName="Helvetica", fontSize=9, leading=13),
    }


def _header(shift, st, content_w):
    window = SHIFT_WINDOW.get(shift.shift.value, "")
    inner = [
        [Paragraph("Recycling Production Report", st["title"])],
        [Paragraph(
            f"Golden Manufacturers · Egg Plant Production &nbsp;|&nbsp; "
            f"{shift.work_date.strftime('%d/%m/%Y')} &nbsp;·&nbsp; {shift.shift.value} Shift"
            f"{' (' + window + ')' if window else ''}", st["sub"])],
    ]
    t = Table(inner, colWidths=[content_w])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), AMBER),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (0, 0), 10), ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
    ]))
    return t


def _meta(shift, st, content_w):
    staff = f"{shift.staff_count or 0} staff"
    if shift.casual_count:
        staff += f" + {shift.casual_count} casuals"
    rows = [[
        Paragraph(f"<b>Shift Supervisor:</b> {shift.supervisor or '—'}", st["cell"]),
        Paragraph(f"<b>No. of Staff:</b> {staff}", st["cell"]),
        Paragraph(f"<b>Absenteeism:</b> {shift.absenteeism or '—'}", st["cell"]),
    ]]
    t = Table(rows, colWidths=[content_w * 0.4, content_w * 0.3, content_w * 0.3])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ZEBRA), ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _machine_table(shift, st, content_w):
    machines = shift.machines or {}
    headers = ["Machine", "Paid Hrs", "Run Hrs", "Target /hr", "Actual /hr",
               "Production Qty", "Operator(s)", "Product Detail"]
    body = [[Paragraph(h, st["head"]) for h in headers]]
    for code, label, qty_field in MACHINES:
        d = machines.get(code) or {}
        qty = getattr(shift, qty_field, 0) or 0
        body.append([
            Paragraph(f"<b>{label}</b>", st["cell"]),
            Paragraph(_fmt(d.get("paid_hours")), st["cellc"]),
            Paragraph(_fmt(d.get("run_hours")), st["cellc"]),
            Paragraph(_fmt(d.get("target_per_hr")), st["cellc"]),
            Paragraph(_fmt(d.get("actual_per_hr")), st["cellc"]),
            Paragraph(_fmt(qty), st["cellc"]),
            Paragraph(d.get("operators") or "—", st["cell"]),
            Paragraph(d.get("product_detail") or "—", st["cell"]),
        ])
    widths = [w * content_w for w in (0.13, 0.07, 0.07, 0.09, 0.09, 0.11, 0.27, 0.17)]
    t = Table(body, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _kv_block(title, value, st, content_w):
    """A labelled free-text block (Comments / Stock / Deliveries)."""
    body = [[Paragraph(f"<b>{title}</b>", st["cell"])],
            [Paragraph((value or "—").replace("\n", "<br/>"), st["note"])]]
    t = Table(body, colWidths=[content_w])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ZEBRA), ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def _summary_row(shift, st, content_w):
    """Diesel / fuel dips / downtime / water — the figures already in the shift."""
    diesel = _fmt(shift.fuel_use)
    dips = ""
    if shift.fuel_open or shift.fuel_close:
        dips = f" (open {_fmt(shift.fuel_open)} → close {_fmt(shift.fuel_close)} L)"
    cells = [
        Paragraph(f"<b>Diesel Usage:</b> {diesel} L{dips}", st["cell"]),
        Paragraph(f"<b>Downtime:</b> {_fmt(shift.downtime_min)} min", st["cell"]),
        Paragraph(f"<b>Water Reading:</b> {_fmt(shift.water_meter)} m³", st["cell"]),
        Paragraph(f"<b>Bales:</b> {_fmt(shift.carton_bales)}", st["cell"]),
    ]
    t = Table([cells], colWidths=[content_w * 0.34, content_w * 0.22, content_w * 0.24, content_w * 0.20])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ZEBRA), ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def shift_report_filename(shift) -> str:
    return f"shift-report-{shift.work_date.isoformat()}-{shift.shift.value.lower()}.pdf"


def build_shift_report_pdf(shift: ProductionShift) -> tuple[bytes, str]:
    st = _styles()
    page = landscape(A4)
    content_w = page[0] - 30 * mm
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=page,
        leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
        title=f"Shift Report {shift.work_date} {shift.shift.value}",
        author="Golden Manufacturers",
    )
    flow = [
        _header(shift, st, content_w),
        Spacer(1, 8),
        _meta(shift, st, content_w),
        Spacer(1, 8),
        KeepTogether([Paragraph("Machine Production", st["h2"]), _machine_table(shift, st, content_w)]),
        Spacer(1, 8),
        _summary_row(shift, st, content_w),
        Spacer(1, 8),
        _kv_block("Comments", shift.comment, st, content_w),
        Spacer(1, 6),
        _kv_block("Products in Stock", shift.stock_notes, st, content_w),
        Spacer(1, 6),
        _kv_block("Deliveries", shift.delivery_notes, st, content_w),
        Spacer(1, 12),
        Paragraph("Generated automatically by the Fibre Mold Plant dashboard at shift end.", st["foot"]),
    ]
    doc.build(flow)
    buf.seek(0)
    return buf.getvalue(), shift_report_filename(shift)
