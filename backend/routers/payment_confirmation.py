"""
payment_confirmation.py — client-facing payment confirmation endpoints.

GET  /payments/confirm?token=...                   — client confirms a payment
POST /payments/resend-confirmation/{payment_event_id} — vendor re-sends the email

Confirming a payment flips its PaymentItems to 'confirmed' and recalculates
Sale.amount_verified as the sum of all confirmed, non-financing items across the
sale. This is phase 1 of the two-phase verification system (email); phase 2
(bank statement reconciliation) will reuse the same token row via
verification_source.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from database import get_db
from models.payment_confirmation_token import PaymentConfirmationToken
from models.payment_event import PaymentEvent
from models.payment_item import PaymentItem
from models.payment_method import PaymentMethod
from models.sale import Sale, SaleStatus
from services.token_service import (
    get_payment_token_by_token,
    generate_payment_token,
)
from services.email_service import (
    send_payment_confirmation_email,
    build_moto_display,
)
from services.confirmation_pages import (
    render_payment_confirmed_page,
    render_token_expired_page,
)

router = APIRouter(prefix="/payments", tags=["payment-confirmation"])


async def _financing_method_id(db: AsyncSession) -> int | None:
    result = await db.execute(
        select(PaymentMethod.method_id).where(PaymentMethod.name == "Financiera")
    )
    return result.scalar_one_or_none()


async def _load_event(db: AsyncSession, payment_event_id: int) -> PaymentEvent | None:
    result = await db.execute(
        select(PaymentEvent)
        .options(
            selectinload(PaymentEvent.items).joinedload(PaymentItem.method),
            joinedload(PaymentEvent.sale).joinedload(Sale.client),
            joinedload(PaymentEvent.sale).joinedload(Sale.dealership),
        )
        .where(PaymentEvent.payment_event_id == payment_event_id)
    )
    return result.unique().scalar_one_or_none()


async def _render_confirmed(db: AsyncSession, event: PaymentEvent, financing_id) -> HTMLResponse:
    """Render the success page for an already-loaded (confirmed) event."""
    sale       = event.sale
    dealership = sale.dealership
    client     = sale.client
    moto_display = await build_moto_display(db, sale)

    total_confirmed = sum(
        item.amount
        for item in event.items
        if item.status == "verified" and item.method_id != financing_id
    )
    return HTMLResponse(render_payment_confirmed_page(
        client_name     = client.nombre_completo if client else "—",
        moto_display     = moto_display,
        total_confirmed  = total_confirmed,
        dealership_name  = dealership.name if dealership else "—",
    ))


@router.get("/confirm", response_class=HTMLResponse)
async def confirm_payment(token: str, db: AsyncSession = Depends(get_db)):
    token_row = await get_payment_token_by_token(db, token)
    if not token_row:
        return HTMLResponse(render_token_expired_page(), status_code=404)

    financing_id = await _financing_method_id(db)

    # Idempotent — already confirmed.
    if token_row.status == "verified":
        event = await _load_event(db, token_row.payment_event_id)
        if event is None:
            return HTMLResponse(render_token_expired_page(), status_code=404)
        return await _render_confirmed(db, event, financing_id)

    # Expired (flagged or lapsed).
    if token_row.status == "expired" or token_row.expires_at < datetime.now(timezone.utc):
        token_row.status = "expired"
        await db.commit()
        return HTMLResponse(render_token_expired_page(), status_code=410)

    event = await _load_event(db, token_row.payment_event_id)
    if event is None or event.sale is None:
        return HTMLResponse(render_token_expired_page(), status_code=404)

    sale = event.sale

    # Confirm every item in this event.
    for item in event.items:
        item.status = "verified"

    # Recalculate amount_verified: sum of all confirmed, non-financing items
    # across every payment event of this sale.
    verified_q = (
        select(func.sum(PaymentItem.amount))
        .join(PaymentEvent, PaymentItem.payment_event_id == PaymentEvent.payment_event_id)
        .where(
            PaymentEvent.sale_id == sale.sale_id,
            PaymentItem.status == "verified",
        )
    )
    if financing_id is not None:
        verified_q = verified_q.where(PaymentItem.method_id != financing_id)
    verified_result = await db.execute(verified_q)
    sale.amount_verified = verified_result.scalar() or 0.0

    if sale.amount_verified >= sale.total_price:
        sale.status = SaleStatus.verified.value

    token_row.status       = "verified"
    token_row.confirmed_at = datetime.now(timezone.utc)
    await db.commit()

    moto_display    = await build_moto_display(db, sale)
    total_confirmed = sum(
        item.amount
        for item in event.items
        if item.method_id != financing_id
    )
    return HTMLResponse(render_payment_confirmed_page(
        client_name     = sale.client.nombre_completo if sale.client else "—",
        moto_display     = moto_display,
        total_confirmed  = total_confirmed,
        dealership_name  = sale.dealership.name if sale.dealership else "—",
    ))


@router.post("/resend-confirmation/{payment_event_id}")
async def resend_confirmation(
    payment_event_id: int,
    db: AsyncSession = Depends(get_db),
):
    # Load the existing token row for this event.
    token_result = await db.execute(
        select(PaymentConfirmationToken).where(
            PaymentConfirmationToken.payment_event_id == payment_event_id
        )
    )
    token_row = token_result.scalar_one_or_none()
    if token_row is None:
        raise HTTPException(status_code=404, detail="Token no encontrado")

    if token_row.status == "verified":
        raise HTTPException(status_code=400, detail="Este pago ya fue confirmado")

    # Refresh the token (invalidates the old one) and re-send the email.
    new_token = await generate_payment_token(db, payment_event_id)
    await db.commit()
    await send_payment_confirmation_email(payment_event_id, db, new_token)

    return {"ok": True, "message": "Correo reenviado al cliente"}
