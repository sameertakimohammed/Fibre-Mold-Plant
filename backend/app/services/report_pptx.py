"""PowerPoint (.pptx) report builder (python-pptx).

A management-facing deck — intended for the monthly report. Three 16:9 slides:
title, headline KPI tiles, and a production + deliveries summary. Figures come
from collect_report_data() — the same source as the xlsx and pdf builders.

build_report_pptx(db, start, end[, period_label]) -> (pptx_bytes, filename)
"""
import io
from datetime import date

from sqlalchemy.orm import Session
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

from .report_data import collect_report_data, report_filename

AMBER = RGBColor(0xF5, 0xA6, 0x23)
INK = RGBColor(0x14, 0x19, 0x20)      # near-black slide background
PANEL = RGBColor(0x1E, 0x26, 0x30)    # tile fill
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
MUTE = RGBColor(0x9A, 0xA4, 0xB2)
GREEN = RGBColor(0x36, 0xB3, 0x7E)

SW, SH = Inches(13.333), Inches(7.5)


def _fmt(n) -> str:
    if isinstance(n, float) and not n.is_integer():
        return f"{n:,.1f}"
    return f"{int(round(n)):,}"


def _bg(slide, color=INK):
    # Added first on every slide, so it sits behind all later shapes.
    r = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
    r.fill.solid(); r.fill.fore_color.rgb = color
    r.line.fill.background()
    r.shadow.inherit = False
    return r


def _text(slide, left, top, width, height, runs, align=PP_ALIGN.LEFT,
          anchor=MSO_ANCHOR.TOP):
    """runs: list of (text, size, bold, color)."""
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for i, (text, size, bold, color) in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        run = p.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.name = "Calibri"
        run.font.color.rgb = color
    return tb


def _accent_bar(slide, left, top, width=Inches(2.2), color=AMBER):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, Pt(5))
    bar.fill.solid(); bar.fill.fore_color.rgb = color
    bar.line.fill.background(); bar.shadow.inherit = False
    return bar


def _tile(slide, left, top, w, h, value, label, accent=AMBER):
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, w, h)
    box.fill.solid(); box.fill.fore_color.rgb = PANEL
    box.line.color.rgb = PANEL; box.line.width = Pt(0.5)
    box.shadow.inherit = False
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.12); tf.margin_right = Inches(0.12)
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = value
    r.font.size = Pt(30); r.font.bold = True; r.font.name = "Calibri"; r.font.color.rgb = WHITE
    p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
    r2 = p2.add_run(); r2.text = label
    r2.font.size = Pt(11); r2.font.name = "Calibri"; r2.font.color.rgb = MUTE
    # thin accent on top edge
    _accent_bar(slide, left + Inches(0.15), top + Inches(0.12),
                width=w - Inches(0.3), color=accent)
    return box


def _title_slide(prs, data):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _bg(s)
    _accent_bar(s, Inches(0.9), Inches(2.55), width=Inches(2.4))
    _text(s, Inches(0.85), Inches(2.7), Inches(11.5), Inches(1.2),
          [("Fibre Mold Plant", 44, True, WHITE)])
    _text(s, Inches(0.9), Inches(3.7), Inches(11.5), Inches(0.7),
          [(f"{data.period_label} Production Report", 24, False, AMBER)])
    _text(s, Inches(0.9), Inches(4.4), Inches(11.5), Inches(0.6),
          [(f"Period: {data.span}", 16, False, MUTE)])
    _text(s, Inches(0.9), Inches(6.7), Inches(11.5), Inches(0.5),
          [("Golden Manufacturers · Recycling Department", 12, False, MUTE)])
    return s


def _kpi_slide(prs, data):
    m = data.metrics
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _bg(s)
    _text(s, Inches(0.85), Inches(0.5), Inches(11.5), Inches(0.7),
          [("Performance Summary", 26, True, WHITE)])
    _text(s, Inches(0.9), Inches(1.15), Inches(11.5), Inches(0.4),
          [(data.span, 13, False, MUTE)])

    tiles = [
        (_fmt(m["total_qty"]), "Total trays", AMBER),
        (_fmt(m["avg_per_day"]), "Avg trays / day", GREEN),
        (f'{_fmt(m["fuel_eff"])}', "Fuel L / 1k trays", AMBER),
        (f'{_fmt(m["downtime_pct"])}%', "Downtime of sched.", RGBColor(0xE5, 0x6A, 0x4E)),
        (f'{_fmt(m["repulp_rate"])}%', "Re-pulp rate", RGBColor(0x9B, 0x7E, 0xDE)),
        (_fmt(m["active_days"]), "Active days", GREEN),
    ]
    cols, gap, lm, top = 3, Inches(0.4), Inches(0.85), Inches(1.9)
    tw = (SW - lm * 2 - gap * (cols - 1)) / cols
    th = Inches(1.85)
    for i, (v, l, acc) in enumerate(tiles):
        rr, cc = divmod(i, cols)
        left = lm + cc * (tw + gap)
        topp = top + rr * (th + Inches(0.35))
        _tile(s, left, topp, tw, th, v, l, acc)
    return s


def _summary_slide(prs, data):
    m = data.metrics
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _bg(s)
    _text(s, Inches(0.85), Inches(0.5), Inches(11.5), Inches(0.7),
          [("Production & Deliveries", 26, True, WHITE)])

    rows = [
        ("Total trays produced", _fmt(m["total_qty"])),
        ("Active production days", _fmt(m["active_days"])),
        ("Average trays / day", _fmt(m["avg_per_day"])),
        ("Total diesel burned (L)", _fmt(m["total_fuel"])),
        ("Fuel efficiency (L / 1k trays)", _fmt(m["fuel_eff"])),
        ("Total downtime (hrs)", _fmt(m["total_downtime_hrs"])),
        ("Downtime rate (% of scheduled)", f'{_fmt(m["downtime_pct"])}%'),
        ("Trays re-pulped", f'{_fmt(m["total_repulped"])} ({_fmt(m["repulp_rate"])}%)'),
        ("30's delivered", _fmt(m["tray30"])),
        ("12's delivered", _fmt(m["tray12"])),
        ("Pallets shipped", _fmt(m["pallets"])),
        ("Deliveries recorded", _fmt(m["delivery_count"])),
    ]
    tbl_shape = s.shapes.add_table(len(rows) + 1, 2,
                                   Inches(0.85), Inches(1.4),
                                   Inches(11.6), Inches(5.4))
    table = tbl_shape.table
    table.columns[0].width = Inches(8.2)
    table.columns[1].width = Inches(3.4)

    def _set(cell, text, *, bold=False, size=13, color=WHITE, align=PP_ALIGN.LEFT, fill=PANEL):
        cell.fill.solid(); cell.fill.fore_color.rgb = fill
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        cell.margin_top = Pt(2); cell.margin_bottom = Pt(2)
        tf = cell.text_frame; tf.word_wrap = True
        p = tf.paragraphs[0]; p.alignment = align
        r = p.add_run(); r.text = text
        r.font.size = Pt(size); r.font.bold = bold; r.font.name = "Calibri"; r.font.color.rgb = color

    _set(table.cell(0, 0), "Metric", bold=True, color=INK, fill=AMBER)
    _set(table.cell(0, 1), "Value", bold=True, color=INK, align=PP_ALIGN.RIGHT, fill=AMBER)
    for i, (k, v) in enumerate(rows, 1):
        fill = INK if i % 2 else PANEL
        _set(table.cell(i, 0), k, fill=fill)
        _set(table.cell(i, 1), v, bold=True, align=PP_ALIGN.RIGHT, fill=fill)
    return s


def build_report_pptx(
    db: Session,
    start: date | None = None,
    end: date | None = None,
    period_label: str = "Monthly",
) -> tuple[bytes, str]:
    data = collect_report_data(db, start, end, period_label)

    prs = Presentation()
    prs.slide_width = SW
    prs.slide_height = SH

    _title_slide(prs, data)
    _kpi_slide(prs, data)
    _summary_slide(prs, data)

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.getvalue(), report_filename("pptx", start, end, period_label)
