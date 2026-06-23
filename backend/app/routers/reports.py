import io
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.user import User
from ..deps import get_current_user
from ..services.report_build import build_report_xlsx
from ..services.report_csv import build_report_csv
from ..services.report_pdf import build_report_pdf
from ..services.report_pptx import build_report_pptx
from ..services.report_monthend import build_monthend_xlsx, build_monthend_pdf

# The plant's emailed "End of Month Report" template (10-section stock/materials
# summary) is selected with period=MonthEnd; everything else is the production-KPI
# report. Matched case-insensitively so "MonthEnd"/"month end" both work.
def _is_month_end(period: str) -> bool:
    return (period or "").strip().lower().replace(" ", "") in ("monthend", "month-end")

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

# Workbook/document construction lives in services/* so the scheduled
# report-email job and these routes build identical files. The route streams the
# bytes; the scheduler attaches them to an email.
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PDF_MIME = "application/pdf"
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
CSV_MIME = "text/csv"


def _stream(data: bytes, fname: str, mime: str) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(data),
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/report.xlsx")
def report_xlsx(
    start: date | None = Query(None),
    end: date | None = Query(None),
    period: str = Query("Production"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if _is_month_end(period):
        data, fname = build_monthend_xlsx(db, start, end)
    else:
        data, fname = build_report_xlsx(db, start, end, period)
    return _stream(data, fname, XLSX_MIME)


@router.get("/report.pdf")
def report_pdf(
    start: date | None = Query(None),
    end: date | None = Query(None),
    period: str = Query("Production"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if _is_month_end(period):
        data, fname = build_monthend_pdf(db, start, end)
    else:
        data, fname = build_report_pdf(db, start, end, period)
    return _stream(data, fname, PDF_MIME)


@router.get("/report.csv")
def report_csv(
    start: date | None = Query(None),
    end: date | None = Query(None),
    period: str = Query("Production"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    # Raw shift-detail rows for spreadsheet analysis (one table, so no month-end
    # variant — that template only makes sense as a formatted workbook).
    data, fname = build_report_csv(db, start, end, period)
    return _stream(data, fname, CSV_MIME)


@router.get("/report.pptx")
def report_pptx(
    start: date | None = Query(None),
    end: date | None = Query(None),
    period: str = Query("Monthly"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    data, fname = build_report_pptx(db, start, end, period)
    return _stream(data, fname, PPTX_MIME)


@router.get("/monthly.xlsx")
def monthly_report(
    start: date | None = Query(None),
    end: date | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    # Back-compat alias for the original endpoint; identical to report.xlsx.
    data, fname = build_report_xlsx(db, start, end, "Production")
    return _stream(data, fname, XLSX_MIME)
