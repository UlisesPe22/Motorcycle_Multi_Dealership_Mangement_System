from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from config import HARDCODED_USER_ID, MAX_PAYMENT_ITEMS_PER_EVENT, DISCOUNTS_ACTIVE
from models.color import Color
from models.motorcycle import Motorcycle, MotorcycleStatus
from models.motorcycle_catalog import MotorcycleCatalog
from models.payment_event import PaymentEvent
from models.payment_item import PaymentItem
from models.payment_method import PaymentMethod
from models.reservation import Reservation, ReservationStatus
from models.reservation_color import ReservationColor
from models.sale import Sale, SaleStatus
from services.token_service import generate_payment_token
from services.email_service import send_payment_confirmation_email


async def handle_payment_declaration(db: AsyncSession, body) -> dict:
    # 1. Validate payment_items count
    if len(body.payment_items) == 0:
        raise HTTPException(status_code=400, detail="Se requiere al menos un ítem de pago.")
    if len(body.payment_items) > MAX_PAYMENT_ITEMS_PER_EVENT:
        raise HTTPException(
            status_code=400,
            detail=f"Máximo {MAX_PAYMENT_ITEMS_PER_EVENT} ítems de pago por evento.",
        )

    # 2. Get total_price snapshot
    if body.motorcycle_id:
        result = await db.execute(
            select(Motorcycle)
            .options(joinedload(Motorcycle.model))
            .where(Motorcycle.motorcycle_id == body.motorcycle_id)
        )
        moto = result.unique().scalar_one_or_none()
        if not moto:
            raise HTTPException(status_code=404, detail="Motocicleta no encontrada.")
        catalog = moto.model
        total_price = catalog.discount_price if DISCOUNTS_ACTIVE else catalog.full_price
    elif body.model_id:
        result = await db.execute(
            select(MotorcycleCatalog).where(MotorcycleCatalog.model_id == body.model_id)
        )
        catalog = result.scalar_one_or_none()
        if not catalog:
            raise HTTPException(status_code=404, detail="Modelo no encontrado.")
        total_price = catalog.discount_price if DISCOUNTS_ACTIVE else catalog.full_price
    else:
        raise HTTPException(status_code=400, detail="Se requiere motorcycle_id o model_id.")

    # 3. Get or create Sale
    if body.motorcycle_id:
        # First: try to find existing sale by motorcycle_id
        result = await db.execute(
            select(Sale).where(
                Sale.motorcycle_id == body.motorcycle_id,
                Sale.status        == SaleStatus.open.value,
            ).limit(1)
        )
        sale = result.scalar_one_or_none()

        # Second: if not found, check if this client has an open
        # reservation Sale (motorcycle_id=NULL) — bridge the gap
        if not sale:
            result = await db.execute(
                select(Sale).where(
                    Sale.client_id     == body.client_id,
                    Sale.motorcycle_id == None,  # noqa: E711
                    Sale.status        == SaleStatus.open.value,
                ).limit(1)
            )
            sale = result.scalar_one_or_none()
            if sale:
                # Assign the motorcycle to this existing reservation sale
                sale.motorcycle_id = body.motorcycle_id
                sale.total_price   = total_price
                await db.flush()

        # Third: no existing sale at all — create new
        if not sale:
            sale = Sale(
                motorcycle_id   = body.motorcycle_id,
                client_id       = body.client_id,
                vendor_id       = HARDCODED_USER_ID,
                dealership_id   = body.dealership_id,
                total_price     = total_price,
                amount_verified = 0.0,
                status          = SaleStatus.open.value,
            )
            db.add(sale)
            await db.flush()

    else:
        # Reservation case — find or create the client's open
        # reservation Sale (motorcycle_id=NULL).
        result = await db.execute(
            select(Sale).where(
                Sale.client_id     == body.client_id,
                Sale.motorcycle_id == None,  # noqa: E711
                Sale.status        == SaleStatus.open.value,
            ).limit(1)
        )
        sale = result.scalar_one_or_none()
        if not sale:
            sale = Sale(
                motorcycle_id   = None,
                client_id       = body.client_id,
                vendor_id       = HARDCODED_USER_ID,
                dealership_id   = body.dealership_id,
                total_price     = total_price,
                amount_verified = 0.0,
                status          = SaleStatus.open.value,
            )
            db.add(sale)
            await db.flush()

    # 4. Enforce one event per type per sale
    result = await db.execute(
        select(PaymentEvent).where(
            PaymentEvent.sale_id    == sale.sale_id,
            PaymentEvent.event_type == body.payment_type,
        ).limit(1)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Ya existe un evento de este tipo para esta venta.",
        )

    # 5. Create PaymentEvent
    payment_sum = sum(item.amount for item in body.payment_items)
    payment_event = PaymentEvent(
        sale_id         = sale.sale_id,
        event_type      = body.payment_type,
        status          = "pending",
        expected_amount = payment_sum,
        created_by      = HARDCODED_USER_ID,
    )
    db.add(payment_event)
    await db.flush()

    # 6. Create PaymentItems
    for item in body.payment_items:
        db.add(PaymentItem(
            payment_event_id = payment_event.payment_event_id,
            amount           = item.amount,
            method_id        = item.method_id,
            status           = "open",
        ))
    await db.flush()

    # 6b. If al_contado or enganche → mark motorcycle as sale_in_progress
    if body.payment_type in ["al_contado", "enganche"] and body.motorcycle_id:
        result = await db.execute(
            select(Motorcycle).where(Motorcycle.motorcycle_id == body.motorcycle_id)
        )
        moto = result.scalar_one_or_none()
        if moto and moto.status in [
            MotorcycleStatus.reserved_for_sale,
            MotorcycleStatus.in_stock_reserved,
        ]:
            moto.status          = MotorcycleStatus.sale_in_progress
            moto.locked_at       = None
            moto.locked_by       = None
            moto.previous_status = None
        elif moto and moto.status == MotorcycleStatus.sale_in_progress:
            raise HTTPException(
                status_code=409,
                detail="Esta motocicleta ya tiene una declaración de pago en progreso.",
            )

    # 7. If enganche → auto-create financing PaymentEvent
    if body.payment_type == "enganche":
        # Check if this sale already has a reservation payment event
        existing_reservation_sum = 0.0
        result = await db.execute(
            select(PaymentEvent).where(
                PaymentEvent.sale_id    == sale.sale_id,
                PaymentEvent.event_type == "reservation",
            ).limit(1)
        )
        reservation_event = result.scalar_one_or_none()
        if reservation_event:
            result2 = await db.execute(
                select(func.sum(PaymentItem.amount)).where(
                    PaymentItem.payment_event_id == reservation_event.payment_event_id
                )
            )
            existing_reservation_sum = result2.scalar() or 0.0

        financing_amount = total_price - payment_sum - existing_reservation_sum

        result = await db.execute(
            select(PaymentMethod).where(PaymentMethod.name == "Financiera")
        )
        financiera_method = result.scalar_one_or_none()
        if not financiera_method:
            financiera_method = PaymentMethod(name="Financiera")
            db.add(financiera_method)
            await db.flush()

        financing_event = PaymentEvent(
            sale_id         = sale.sale_id,
            event_type      = "financing",
            status          = "pending",
            expected_amount = financing_amount,
            created_by      = HARDCODED_USER_ID,
        )
        db.add(financing_event)
        await db.flush()

        db.add(PaymentItem(
            payment_event_id = financing_event.payment_event_id,
            amount           = financing_amount,
            method_id        = financiera_method.method_id,
            financiera_id    = body.financiera_id,
            status           = "open",
        ))
        await db.flush()

    # 8. If reservation → check no in-stock unit exists, then create Reservation record
    if body.payment_type == "reservation":
        existing = await db.execute(
            select(Motorcycle).where(
                Motorcycle.model_id       == body.model_id,
                Motorcycle.dealership_id  == body.dealership_id,
                Motorcycle.status         == MotorcycleStatus.in_stock,
                Motorcycle.reservation_id == None,
            ).limit(1)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Ya existe una motocicleta de este modelo disponible en stock. No es necesario hacer una reservación.",
            )

        reservation = Reservation(
            client_id      = body.client_id,
            model_id       = body.model_id,
            dealership_id  = body.dealership_id,
            deposit_amount = payment_sum,
            status         = ReservationStatus.active,
            created_by     = HARDCODED_USER_ID,
            event_id       = None,
        )
        db.add(reservation)
        await db.flush()

        if body.colors:
            for idx, color_name in enumerate(body.colors):
                result = await db.execute(
                    select(Color).where(Color.name == color_name)
                )
                color = result.scalar_one_or_none()
                if color:
                    db.add(ReservationColor(
                        reservation_id = reservation.reservation_id,
                        color_id       = color.color_id,
                        priority       = idx + 1,
                    ))
            await db.flush()

    # 9. Commit
    await db.commit()

    # 10. Fire the client payment-confirmation email. This is best-effort:
    #     an SMTP failure must never break the payment declaration response.
    try:
        token = await generate_payment_token(db, payment_event.payment_event_id)
        await db.commit()
        await send_payment_confirmation_email(payment_event.payment_event_id, db, token)
    except Exception as e:
        print(
            f"[email] payment confirmation email failed for event "
            f"{payment_event.payment_event_id}: {e}"
        )

    return {
        "success":          True,
        "sale_id":          sale.sale_id,
        "payment_event_id": payment_event.payment_event_id,
        "message":          "Pago declarado exitosamente.",
    }
