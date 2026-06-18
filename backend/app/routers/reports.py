import io
from datetime import date
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.user import User
from ..deps import get_current_user
from ..services.report_build import build_report_xlsx

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/monthly.xlsx")
def monthly_report(
    start: date | None = Query(None),
    end: date | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    # Workbook construction lives in services/report_build so the scheduled
    # report-email job builds the identical file. No behaviour change here.
    data, fname = build_report_xlsx(db, start, end)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
