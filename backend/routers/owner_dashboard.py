"""
owner_dashboard.py — read-only reporting endpoints for the Owner panel.

All endpoints are scoped to a single dealership and a [date_from, date_to]
window (inclusive of both calendar days). They follow the same async-session
pattern as vendor_sales.py and perform no auth check (matching that router).
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.manual_status_change import ManualStatusChange
from models.reservation import Reservation, ReservationStatus
from models.sale import Sale, SaleStatus
from models.user import User

router = APIRouter(prefix="/owner-dashboard", tags=["owner_dashboard"])

_IN_PROGRESS_STATES = [SaleStatus.open.value, SaleStatus.verified.value]
_LIVE_RESERVATION_STATES = [ReservationStatus.active, ReservationStatus.assigned]
_SALE_CANCELLED = "sale_cancelled"


def _parse_range(date_from: Optional[str], date_to: Optional[str]):
    """Return (start, end_exclusive) naive datetimes.

    Defaults: first day of the current month → today (inclusive). The end is
    pushed to the next midnight so the whole `date_to` day is covered.
    """
    now = datetime.now()
    start = datetime.fromisoformat(date_from) if date_from else datetime(now.year, now.month, 1)
    if date_to:
        end_day = datetime.fromisoformat(date_to)
    else:
        end_day = datetime(now.year, now.month, now.day)
    end = end_day + timedelta(days=1)
    return start, end


@router.get("/summary")
async def owner_dashboard_summary(
    dealership_id: int = Query(...),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    start, end = _parse_range(date_from, date_to)

    sold_result = await db.execute(
        select(func.count()).select_from(Sale).where(
            Sale.dealership_id == dealership_id,
            Sale.status == SaleStatus.complete.value,
            Sale.created_at >= start,
            Sale.created_at < end,
        )
    )

    reserved_result = await db.execute(
        select(func.count()).select_from(Reservation).where(
            Reservation.dealership_id == dealership_id,
            Reservation.status.in_(_LIVE_RESERVATION_STATES),
            Reservation.created_at >= start,
            Reservation.created_at < end,
        )
    )

    in_progress_result = await db.execute(
        select(func.count()).select_from(Sale).where(
            Sale.dealership_id == dealership_id,
            Sale.status.in_(_IN_PROGRESS_STATES),
            Sale.created_at >= start,
            Sale.created_at < end,
        )
    )

    return {
        "sold":        sold_result.scalar() or 0,
        "reserved":    reserved_result.scalar() or 0,
        "in_progress": in_progress_result.scalar() or 0,
    }


@router.get("/cancelled")
async def owner_dashboard_cancelled(
    dealership_id: int = Query(...),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    start, end = _parse_range(date_from, date_to)

    result = await db.execute(
        select(ManualStatusChange, Sale, User)
        .join(Sale, ManualStatusChange.sale_id == Sale.sale_id)
        .join(User, Sale.vendor_id == User.user_id)
        .where(
            ManualStatusChange.event_type == _SALE_CANCELLED,
            Sale.dealership_id == dealership_id,
            ManualStatusChange.created_at >= start,
            ManualStatusChange.created_at < end,
        )
        .order_by(ManualStatusChange.created_at.desc())
    )

    return [
        {
            "sale_id":       sale.sale_id,
            "motorcycle_id": sale.motorcycle_id,
            "vendor_name":   user.name,
            "cancelled_at":  msc.created_at.isoformat(),
            "reason":        msc.reason,
        }
        for msc, sale, user in result.all()
    ]


@router.get("/vendors")
async def owner_dashboard_vendors(
    dealership_id: int = Query(...),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    start, end = _parse_range(date_from, date_to)

    vendors_result = await db.execute(
        select(User)
        .where(User.role == "vendor", User.dealership_id == dealership_id)
        .order_by(User.name)
    )
    vendors = vendors_result.scalars().all()

    sold_rows = await db.execute(
        select(Sale.vendor_id, func.count()).where(
            Sale.dealership_id == dealership_id,
            Sale.status == SaleStatus.complete.value,
            Sale.created_at >= start,
            Sale.created_at < end,
        ).group_by(Sale.vendor_id)
    )
    sold_by_vendor = {vid: c for vid, c in sold_rows.all()}

    in_progress_rows = await db.execute(
        select(Sale.vendor_id, func.count()).where(
            Sale.dealership_id == dealership_id,
            Sale.status.in_(_IN_PROGRESS_STATES),
            Sale.created_at >= start,
            Sale.created_at < end,
        ).group_by(Sale.vendor_id)
    )
    in_progress_by_vendor = {vid: c for vid, c in in_progress_rows.all()}

    reservation_rows = await db.execute(
        select(Reservation.created_by, func.count()).where(
            Reservation.dealership_id == dealership_id,
            Reservation.status.in_(_LIVE_RESERVATION_STATES),
            Reservation.created_at >= start,
            Reservation.created_at < end,
        ).group_by(Reservation.created_by)
    )
    reservations_by_vendor = {vid: c for vid, c in reservation_rows.all()}

    cancelled_rows = await db.execute(
        select(Sale.vendor_id, func.count())
        .select_from(ManualStatusChange)
        .join(Sale, ManualStatusChange.sale_id == Sale.sale_id)
        .where(
            ManualStatusChange.event_type == _SALE_CANCELLED,
            Sale.dealership_id == dealership_id,
            ManualStatusChange.created_at >= start,
            ManualStatusChange.created_at < end,
        ).group_by(Sale.vendor_id)
    )
    cancelled_by_vendor = {vid: c for vid, c in cancelled_rows.all()}

    return [
        {
            "vendor_id":     v.user_id,
            "vendor_name":   v.name,
            "sold":          sold_by_vendor.get(v.user_id, 0),
            "reservations":  reservations_by_vendor.get(v.user_id, 0),
            "cancelled":     cancelled_by_vendor.get(v.user_id, 0),
            "in_progress":   in_progress_by_vendor.get(v.user_id, 0),
        }
        for v in vendors
    ]
