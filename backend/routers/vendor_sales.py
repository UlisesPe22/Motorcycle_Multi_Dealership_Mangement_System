from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract
from sqlalchemy.orm import joinedload, selectinload

from database import get_db
from config import HARDCODED_USER_ID
from models.motorcycle import Motorcycle
from models.payment_confirmation_token import PaymentConfirmationToken
from models.payment_event import PaymentEvent
from models.reservation import Reservation, ReservationStatus
from models.sale import Sale, SaleStatus
from models.user import User

router = APIRouter(prefix="/vendor-sales", tags=["vendor_sales"])

_PAYMENT_TYPE_LABEL = {
    "reservation": "reserva",
    "al_contado":  "al contado",
    "enganche":    "enganche",
}


@router.get("/summary")
async def vendor_sales_summary(db: AsyncSession = Depends(get_db)):
    user_result = await db.execute(
        select(User).where(User.user_id == HARDCODED_USER_ID)
    )
    user = user_result.scalar_one_or_none()
    vendor_name = user.name if user else "—"

    in_progress_result = await db.execute(
        select(func.count()).select_from(Sale).where(
            Sale.vendor_id == HARDCODED_USER_ID,
            Sale.status.in_([SaleStatus.open.value, SaleStatus.verified.value]),
        )
    )
    sales_in_progress = in_progress_result.scalar() or 0

    now = datetime.now(timezone.utc)
    completed_result = await db.execute(
        select(func.count()).select_from(Sale).where(
            Sale.vendor_id == HARDCODED_USER_ID,
            Sale.status == SaleStatus.complete.value,
            extract("year",  Sale.created_at) == now.year,
            extract("month", Sale.created_at) == now.month,
        )
    )
    completed_this_month = completed_result.scalar() or 0

    return {
        "vendor_name":          vendor_name,
        "sales_in_progress":    sales_in_progress,
        "completed_this_month": completed_this_month,
    }


@router.get("/active")
async def vendor_sales_active(
    search: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Sale)
        .options(
            joinedload(Sale.client),
            joinedload(Sale.motorcycle).joinedload(Motorcycle.model),
            selectinload(Sale.events).selectinload(PaymentEvent.items),
        )
        .where(
            Sale.vendor_id == HARDCODED_USER_ID,
            Sale.status.in_([SaleStatus.open.value, SaleStatus.verified.value]),
        )
        .order_by(Sale.created_at.desc())
    )
    sales = result.unique().scalars().all()

    # Load confirmation-token status for every payment event in these sales,
    # so the UI can surface a "resend confirmation email" affordance.
    all_event_ids = [ev.payment_event_id for sale in sales for ev in sale.events]
    token_by_event: dict[int, PaymentConfirmationToken] = {}
    if all_event_ids:
        tok_result = await db.execute(
            select(PaymentConfirmationToken).where(
                PaymentConfirmationToken.payment_event_id.in_(all_event_ids)
            )
        )
        token_by_event = {t.payment_event_id: t for t in tok_result.scalars().all()}

    now = datetime.now(timezone.utc)

    def confirmation_status(payment_event_id: int):
        tok = token_by_event.get(payment_event_id)
        if tok is None:
            return None
        if tok.status == "verified":
            return "verified"
        if tok.status == "expired" or tok.expires_at < now:
            return "expired"
        return "pending"

    output = []
    for sale in sales:
        model_name    = None
        year          = None
        color         = None
        reservation_id = None
        motorcycle_id  = sale.motorcycle_id

        if sale.motorcycle and sale.motorcycle.model:
            model_name = sale.motorcycle.model.canonical_name
            year       = sale.motorcycle.model.year
            color      = sale.motorcycle.color
            if sale.motorcycle.reservation_id:
                reservation_id = sale.motorcycle.reservation_id

        # For reservation-only sales (no motorcycle yet), pull model from reservation
        if motorcycle_id is None:
            res_result = await db.execute(
                select(Reservation)
                .options(joinedload(Reservation.model))
                .where(
                    Reservation.client_id == sale.client_id,
                    Reservation.status.in_([
                        ReservationStatus.active,
                        ReservationStatus.assigned,
                    ]),
                )
                .order_by(Reservation.created_at.desc())
                .limit(1)
            )
            reservation = res_result.scalar_one_or_none()
            if reservation:
                reservation_id = reservation.reservation_id
                if reservation.model:
                    model_name = reservation.model.canonical_name
                    year       = reservation.model.year

            # No resolvable model yet for this reservation-only sale.
            if model_name is None:
                model_name = "Reserva — modelo pendiente"

        client_name = sale.client.nombre_completo if sale.client else "—"

        non_financing_events = [ev for ev in sale.events if ev.event_type != "financing"]
        payment_types = " / ".join(
            _PAYMENT_TYPE_LABEL.get(ev.event_type, ev.event_type)
            for ev in non_financing_events
        ) or "—"

        all_items      = [item for ev in sale.events for item in ev.items]
        non_financing_items = [item for ev in non_financing_events for item in ev.items]
        total_count    = len(all_items)
        verified_count = sum(1 for item in non_financing_items if item.status == "verified")

        payment_events = [
            {
                "payment_event_id":    ev.payment_event_id,
                "event_type":          ev.event_type,
                "confirmation_status": confirmation_status(ev.payment_event_id),
            }
            for ev in sale.events
        ]
        expired_payment_event_ids = [
            pe["payment_event_id"]
            for pe in payment_events
            if pe["confirmation_status"] == "expired"
        ]

        row = {
            "sale_id":           sale.sale_id,
            "model_name":        model_name or "—",
            "year":              year or "—",
            "color":             color or "—",
            "client_name":       client_name,
            "payment_types":     payment_types,
            "verified_count":    verified_count,
            "total_count":       total_count,
            "amount_verified":   sale.amount_verified,
            "total_price":       sale.total_price,
            "sale_status":       sale.status,
            "contract_unlocked": sale.status == SaleStatus.verified.value,
            "motorcycle_id":     motorcycle_id,
            "reservation_id":    reservation_id,
            "payment_events":            payment_events,
            "expired_payment_event_ids": expired_payment_event_ids,
            "has_expired_confirmation":  len(expired_payment_event_ids) > 0,
        }

        if search:
            q = search.lower()
            if q not in client_name.lower() and q not in (model_name or "").lower():
                continue

        output.append(row)

    return output
