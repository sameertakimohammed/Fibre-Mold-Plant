from datetime import date, datetime
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, model_validator
from ..models.production import Shift


# Reusable bounded numeric types. NonNeg* enforce >= 0 so neither the API nor an
# Excel import via the API can write negative quantities/fuel/etc. Matching
# Postgres CHECK constraints (NOT VALID) back these at the DB layer.
NonNegFloat = Annotated[float, Field(ge=0)]
NonNegInt = Annotated[int, Field(ge=0)]
# Hours within a shift can't exceed a day; speed/percent capped to sane maxima.
Hours = Annotated[float, Field(ge=0, le=24)]
Minutes = Annotated[float, Field(ge=0, le=1440)]   # 0..24h expressed in minutes
Speed = Annotated[float, Field(ge=0, le=100000)]   # trays/hr upper sanity bound


class ShiftBase(BaseModel):
    work_date: date
    shift: Shift
    qty: NonNegFloat = 0
    p30s: NonNegFloat = 0
    p30l: NonNegFloat = 0
    p20n: NonNegFloat = 0
    p12n: NonNegFloat = 0
    p12hf: NonNegFloat = 0
    p12ff: NonNegFloat = 0
    p4cup: NonNegFloat = 0
    p2cup: NonNegFloat = 0
    hp1: NonNegFloat = 0
    hp2: NonNegFloat = 0
    hp3: NonNegFloat = 0
    hp4: NonNegFloat = 0
    hp5: NonNegFloat = 0
    hp6: NonNegFloat = 0
    labelling: NonNegFloat = 0
    water_meter: NonNegFloat = 0
    carton_bales: NonNegFloat = 0
    speed: Speed = 0
    fuel_open: NonNegFloat = 0
    fuel_close: NonNegFloat = 0
    fuel_use: NonNegFloat = 0
    prod_hours: Hours = 0
    downtime_min: Minutes = 0
    sched_hours: Hours = 8
    clean_min: Minutes = 0
    mold_min: Minutes = 0
    other_min: Minutes = 0
    repulped: NonNegFloat = 0
    comment: str = ""

    @model_validator(mode="after")
    def _check_consistency(self):
        # Downtime can't exceed the scheduled time (in minutes).
        if self.sched_hours is not None and self.downtime_min is not None:
            if self.downtime_min > self.sched_hours * 60 + 1e-6:
                raise ValueError(
                    "downtime_min cannot exceed scheduled time "
                    f"({self.sched_hours} h = {self.sched_hours * 60:.0f} min)"
                )
        # The clean/mold/other breakdown should not exceed total downtime.
        breakdown = (self.clean_min or 0) + (self.mold_min or 0) + (self.other_min or 0)
        if self.downtime_min is not None and breakdown > self.downtime_min + 1e-6:
            raise ValueError(
                "clean_min + mold_min + other_min cannot exceed downtime_min"
            )
        return self


class ShiftCreate(ShiftBase):
    pass


class ShiftUpdate(ShiftBase):
    pass


class ShiftOut(ShiftBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime


class DeliveryBase(BaseModel):
    work_date: date
    company: str
    tray30: NonNegFloat = 0
    tray12n: NonNegFloat = 0
    tray12ff: NonNegFloat = 0
    pallets: NonNegFloat = 0
    comment: str = ""


class DeliveryOut(DeliveryBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class BaleBase(BaseModel):
    work_date: date
    grn: str = ""
    weight_kg: NonNegFloat = 0
    quantity: NonNegFloat = 0


class BaleOut(BaleBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class FuelDipBase(BaseModel):
    work_date: date
    shift: str
    open_dip: NonNegFloat = 0
    close_dip: NonNegFloat = 0
    actual_usage: NonNegFloat = 0
    received: NonNegFloat = 0
    note: str = ""


class FuelDipOut(FuelDipBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class MonthlyStockBase(BaseModel):
    period: Annotated[str, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]  # YYYY-MM
    diesel_eom: NonNegFloat = 0
    bal_30s: NonNegFloat = 0
    bal_12n: NonNegFloat = 0
    bal_12ff: NonNegFloat = 0
    bal_12nl: NonNegFloat = 0
    pallets_wrapped: NonNegFloat = 0
    bales_used: NonNegFloat = 0
    bales_purchased: NonNegFloat = 0
    labels_used: NonNegFloat = 0


class MonthlyStockOut(MonthlyStockBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
