import logging
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..models.operations import Delivery, BaleReceipt, FuelDip, MonthlyStock
from ..models.user import User, Role
from ..schemas.operations import (
    DeliveryBase, DeliveryOut, BaleBase, BaleOut,
    FuelDipBase, FuelDipOut, MonthlyStockBase, MonthlyStockOut,
)
from ..deps import get_current_user, require_role

logger = logging.getLogger("app")

# See shifts.py — bounds worst-case memory; responses stay plain JSON arrays.
MAX_LIMIT = 1000

router = APIRouter(prefix="/api/v1", tags=["operations"])


# ---- Deliveries ----
@router.get("/deliveries", response_model=list[DeliveryOut])
def list_deliveries(start: date | None = None, end: date | None = None,
                    limit: int = Query(MAX_LIMIT, ge=1, le=MAX_LIMIT),
                    offset: int = Query(0, ge=0),
                    db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    q = db.query(Delivery).filter(Delivery.deleted_at.is_(None))
    if start:
        q = q.filter(Delivery.work_date >= start)
    if end:
        q = q.filter(Delivery.work_date <= end)
    rows = q.order_by(Delivery.work_date).offset(offset).limit(limit).all()
    if len(rows) == limit:
        logger.warning("list_deliveries truncated at limit=%s offset=%s", limit, offset)
    return rows


@router.post("/deliveries", response_model=DeliveryOut, status_code=201)
def create_delivery(body: DeliveryBase, db: Session = Depends(get_db),
                    user: User = Depends(require_role(Role.supervisor))):
    d = Delivery(**body.model_dump(), created_by=user.id)
    db.add(d); db.commit(); db.refresh(d)
    return d


@router.put("/deliveries/{item_id}", response_model=DeliveryOut)
def update_delivery(item_id: int, body: DeliveryBase, db: Session = Depends(get_db),
                    _: User = Depends(require_role(Role.supervisor))):
    d = db.get(Delivery, item_id)
    if not d or d.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Not found")
    for k, v in body.model_dump().items():
        setattr(d, k, v)
    db.commit(); db.refresh(d)
    return d


@router.delete("/deliveries/{item_id}", status_code=204)
def delete_delivery(item_id: int, db: Session = Depends(get_db),
                    user: User = Depends(require_role(Role.supervisor))):
    d = db.get(Delivery, item_id)
    if not d or d.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Not found")
    # Soft delete: stamp instead of db.delete().
    d.deleted_at = datetime.now(timezone.utc)
    d.deleted_by = user.id
    db.commit()


# ---- Bale receipts ----
@router.get("/bales", response_model=list[BaleOut])
def list_bales(start: date | None = None, end: date | None = None,
               limit: int = Query(MAX_LIMIT, ge=1, le=MAX_LIMIT),
               offset: int = Query(0, ge=0),
               db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    q = db.query(BaleReceipt).filter(BaleReceipt.deleted_at.is_(None))
    if start:
        q = q.filter(BaleReceipt.work_date >= start)
    if end:
        q = q.filter(BaleReceipt.work_date <= end)
    rows = q.order_by(BaleReceipt.work_date).offset(offset).limit(limit).all()
    if len(rows) == limit:
        logger.warning("list_bales truncated at limit=%s offset=%s", limit, offset)
    return rows


@router.post("/bales", response_model=BaleOut, status_code=201)
def create_bale(body: BaleBase, db: Session = Depends(get_db),
                user: User = Depends(require_role(Role.supervisor))):
    b = BaleReceipt(**body.model_dump(), created_by=user.id)
    db.add(b); db.commit(); db.refresh(b)
    return b


@router.put("/bales/{item_id}", response_model=BaleOut)
def update_bale(item_id: int, body: BaleBase, db: Session = Depends(get_db),
                _: User = Depends(require_role(Role.supervisor))):
    b = db.get(BaleReceipt, item_id)
    if not b or b.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Not found")
    for k, v in body.model_dump().items():
        setattr(b, k, v)
    db.commit(); db.refresh(b)
    return b


@router.delete("/bales/{item_id}", status_code=204)
def delete_bale(item_id: int, db: Session = Depends(get_db),
                user: User = Depends(require_role(Role.supervisor))):
    b = db.get(BaleReceipt, item_id)
    if not b or b.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Not found")
    b.deleted_at = datetime.now(timezone.utc)
    b.deleted_by = user.id
    db.commit()


# ---- Fuel dips ----
@router.get("/fuel-dips", response_model=list[FuelDipOut])
def list_fuel_dips(start: date | None = None, end: date | None = None,
                   limit: int = Query(MAX_LIMIT, ge=1, le=MAX_LIMIT),
                   offset: int = Query(0, ge=0),
                   db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    q = db.query(FuelDip).filter(FuelDip.deleted_at.is_(None))
    if start:
        q = q.filter(FuelDip.work_date >= start)
    if end:
        q = q.filter(FuelDip.work_date <= end)
    rows = q.order_by(FuelDip.work_date).offset(offset).limit(limit).all()
    if len(rows) == limit:
        logger.warning("list_fuel_dips truncated at limit=%s offset=%s", limit, offset)
    return rows


@router.post("/fuel-dips", response_model=FuelDipOut, status_code=201)
def create_fuel_dip(body: FuelDipBase, db: Session = Depends(get_db),
                    user: User = Depends(require_role(Role.supervisor))):
    f = FuelDip(**body.model_dump(), created_by=user.id)
    db.add(f); db.commit(); db.refresh(f)
    return f


@router.put("/fuel-dips/{item_id}", response_model=FuelDipOut)
def update_fuel_dip(item_id: int, body: FuelDipBase, db: Session = Depends(get_db),
                    _: User = Depends(require_role(Role.supervisor))):
    f = db.get(FuelDip, item_id)
    if not f or f.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Not found")
    for k, v in body.model_dump().items():
        setattr(f, k, v)
    db.commit(); db.refresh(f)
    return f


@router.delete("/fuel-dips/{item_id}", status_code=204)
def delete_fuel_dip(item_id: int, db: Session = Depends(get_db),
                    user: User = Depends(require_role(Role.supervisor))):
    f = db.get(FuelDip, item_id)
    if not f or f.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Not found")
    f.deleted_at = datetime.now(timezone.utc)
    f.deleted_by = user.id
    db.commit()


# ---- Monthly stock ----
@router.get("/monthly-stock", response_model=list[MonthlyStockOut])
def list_stock(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return (db.query(MonthlyStock)
            .filter(MonthlyStock.deleted_at.is_(None))
            .order_by(MonthlyStock.period)
            .all())


@router.put("/monthly-stock/{period}", response_model=MonthlyStockOut)
def upsert_stock(period: str, body: MonthlyStockBase, db: Session = Depends(get_db),
                 _: User = Depends(require_role(Role.supervisor))):
    # `period` is uniquely constrained, so match WITHOUT the soft-delete filter:
    # a soft-deleted period still occupies the unique slot, so we revive+update it
    # (clearing deleted_at) rather than inserting a colliding new row.
    row = db.query(MonthlyStock).filter(MonthlyStock.period == period).first()
    if row:
        for k, v in body.model_dump().items():
            setattr(row, k, v)
        row.deleted_at = None
        row.deleted_by = None
    else:
        row = MonthlyStock(**body.model_dump())
        db.add(row)
    db.commit(); db.refresh(row)
    return row


@router.delete("/monthly-stock/{period}", status_code=204)
def delete_stock(period: str, db: Session = Depends(get_db),
                 user: User = Depends(require_role(Role.manager))):
    row = (db.query(MonthlyStock)
           .filter(MonthlyStock.period == period,
                   MonthlyStock.deleted_at.is_(None))
           .first())
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    # Soft delete: list_stock filters deleted_at IS NULL; a later upsert for the
    # same period revives this row (see upsert_stock).
    row.deleted_at = datetime.now(timezone.utc)
    row.deleted_by = user.id
    db.commit()
