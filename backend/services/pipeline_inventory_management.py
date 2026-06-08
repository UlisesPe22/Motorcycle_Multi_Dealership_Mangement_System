from typing import Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import joinedload, selectinload

from config import HARDCODED_USER_ID
from models.motorcycle import Motorcycle, MotorcycleStatus
from models.reservation import Reservation, ReservationStatus
from models.sale import Sale
from models.payment_event import PaymentEvent
from models.payment_item import PaymentItem
from models.manual_status_change import ManualStatusChange
from models.client_transfer_log import ClientTransferLog


async def get_client_activity(db: AsyncSession, client_id: int) -> dict:
    # Reservations: active or assigned
    res_result = await db.execute(
        select(Reservation)
        .options(
            joinedload(Reservation.model),
            joinedload(Reservation.dealership),
            joinedload(Reservation.motorcycle).joinedload(Motorcycle.model),
        )
        .where(
            Reservation.client_id == client_id,
            Reservation.status.in_([ReservationStatus.active, ReservationStatus.assigned]),
        )
        .order_by(Reservation.created_at.desc())
    )
    reservations = res_result.unique().scalars().all()

    # Sales: open
    sale_result = await db.execute(
        select(Sale)
        .options(
            joinedload(Sale.motorcycle).options(
                joinedload(Motorcycle.model),
                joinedload(Motorcycle.dealership),
            ),
            joinedload(Sale.dealership),
            selectinload(Sale.events).selectinload(PaymentEvent.items).selectinload(PaymentItem.method),
        )
        .where(
            Sale.client_id == client_id,
            Sale.status == "open",
        )
        .order_by(Sale.created_at.desc())
    )
    sales = sale_result.unique().scalars().all()

    reservation_list = []
    for r in reservations:
        moto_details = None
        motorcycle_id = None
        if r.motorcycle:
            motorcycle_id = r.motorcycle.motorcycle_id
            moto_details = {
                "motorcycle_id": r.motorcycle.motorcycle_id,
                "model_name":    r.motorcycle.model.canonical_name if r.motorcycle.model else None,
                "year":          r.motorcycle.model.year if r.motorcycle.model else None,
                "color":         r.motorcycle.color,
                "serie":         r.motorcycle.reference_number,
                "motor":         r.motorcycle.motor_number,
                "status":        r.motorcycle.status.value,
            }
        reservation_list.append({
            "reservation_id":  r.reservation_id,
            "model_name":      r.model.canonical_name,
            "year":            r.model.year,
            "deposit_amount":  r.deposit_amount,
            "status":          r.status.value,
            "dealership_name": r.dealership.name,
            "motorcycle_id":   motorcycle_id,
            "motorcycle":      moto_details,
        })

    sale_list = []
    for s in sales:
        moto_details = None
        if s.motorcycle:
            moto_details = {
                "motorcycle_id": s.motorcycle.motorcycle_id,
                "model_name":    s.motorcycle.model.canonical_name if s.motorcycle.model else None,
                "year":          s.motorcycle.model.year if s.motorcycle.model else None,
                "color":         s.motorcycle.color,
                "serie":         s.motorcycle.reference_number,
                "motor":         s.motorcycle.motor_number,
                "dealership_name": s.motorcycle.dealership.name if s.motorcycle.dealership else None,
            }

        events_list = []
        for ev in s.events:
            items_list = [
                {
                    "payment_item_id": item.payment_item_id,
                    "amount":          item.amount,
                    "method_name":     item.method.name if item.method else None,
                    "status":          item.status,
                }
                for item in ev.items
            ]
            events_list.append({
                "payment_event_id": ev.payment_event_id,
                "event_type":       ev.event_type,
                "status":           ev.status,
                "expected_amount":  ev.expected_amount,
                "items":            items_list,
            })

        sale_list.append({
            "sale_id":          s.sale_id,
            "motorcycle":       moto_details,
            "total_price":      s.total_price,
            "amount_verified":  s.amount_verified,
            "status":           s.status,
            "dealership_name":  s.dealership.name if s.dealership else None,
            "events":           events_list,
        })

    return {
        "client_id":    client_id,
        "reservations": reservation_list,
        "sales":        sale_list,
    }


async def handle_cancel_activity(db: AsyncSession, body) -> dict:
    if body.sale_id is None and body.reservation_id is None:
        raise HTTPException(status_code=400, detail="Se requiere sale_id o reservation_id.")

    # ── Cancel reservation only ──────────────────────────────────────────────
    if body.sale_id is None:
        res_result = await db.execute(
            select(Reservation).where(Reservation.reservation_id == body.reservation_id)
        )
        reservation = res_result.scalar_one_or_none()
        if not reservation:
            raise HTTPException(status_code=404, detail="Reservación no encontrada.")

        reservation.status = ReservationStatus.cancelled

        # If a motorcycle has this reservation linked and is in_stock_reserved, free it
        moto_result = await db.execute(
            select(Motorcycle).where(Motorcycle.reservation_id == body.reservation_id)
        )
        moto = moto_result.scalar_one_or_none()
        if moto and moto.status == MotorcycleStatus.in_stock_reserved:
            moto.status = MotorcycleStatus.in_stock
            moto.reservation_id = None

        db.add(ManualStatusChange(
            event_type=     "reservation_cancelled",
            reservation_id= body.reservation_id,
            reason=         body.reason,
            performed_by=   HARDCODED_USER_ID,
        ))

        await db.commit()
        return {"success": True, "message": "Reservación cancelada.", "total_refund": 0.0}

    # ── Cancel sale ──────────────────────────────────────────────────────────
    sale_result = await db.execute(
        select(Sale)
        .options(
            selectinload(Sale.events).selectinload(PaymentEvent.items),
            joinedload(Sale.motorcycle),
        )
        .where(Sale.sale_id == body.sale_id)
    )
    sale = sale_result.unique().scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=404, detail="Venta no encontrada.")

    sale.status = "cancelled"

    total_refund = 0.0
    for ev in sale.events:
        if ev.event_type == "financing":
            continue
        ev.status = "refunded"
        for item in ev.items:
            item.status = "refunded"
            total_refund += item.amount

    # Handle motorcycle
    if sale.motorcycle_id:
        moto_result = await db.execute(
            select(Motorcycle).where(Motorcycle.motorcycle_id == sale.motorcycle_id)
        )
        moto = moto_result.scalar_one_or_none()
        if moto:
            # If moto has a linked reservation, cancel it
            if moto.reservation_id:
                linked_res_result = await db.execute(
                    select(Reservation).where(Reservation.reservation_id == moto.reservation_id)
                )
                linked_res = linked_res_result.scalar_one_or_none()
                if linked_res:
                    linked_res.status = ReservationStatus.cancelled
                moto.reservation_id = None

            moto.status          = MotorcycleStatus.in_stock
            moto.locked_at       = None
            moto.locked_by       = None
            moto.previous_status = None

    # Cancel separately-provided reservation if any
    if body.reservation_id:
        extra_res_result = await db.execute(
            select(Reservation).where(Reservation.reservation_id == body.reservation_id)
        )
        extra_res = extra_res_result.scalar_one_or_none()
        if extra_res:
            extra_res.status = ReservationStatus.cancelled

    db.add(ManualStatusChange(
        event_type=   "sale_cancelled",
        sale_id=      body.sale_id,
        reason=       body.reason,
        performed_by= HARDCODED_USER_ID,
    ))

    await db.commit()
    return {
        "success":      True,
        "message":      f"Venta cancelada. Monto a reembolsar: ${total_refund:.2f}",
        "total_refund": total_refund,
    }


async def handle_reject_moto(db: AsyncSession, body) -> dict:
    result = await db.execute(
        select(Motorcycle).where(Motorcycle.motorcycle_id == body.motorcycle_id)
    )
    moto = result.scalar_one_or_none()
    if not moto:
        raise HTTPException(status_code=404, detail="Motocicleta no encontrada.")

    if moto.status not in [MotorcycleStatus.in_stock, MotorcycleStatus.in_stock_reserved]:
        raise HTTPException(
            status_code=400,
            detail=f"La motocicleta tiene estado '{moto.status.value}' y no puede ser rechazada.",
        )

    if moto.status == MotorcycleStatus.in_stock_reserved and moto.reservation_id:
        res_result = await db.execute(
            select(Reservation).where(Reservation.reservation_id == moto.reservation_id)
        )
        reservation = res_result.scalar_one_or_none()
        if reservation:
            reservation.status = ReservationStatus.active
        moto.reservation_id = None

    moto.status          = MotorcycleStatus.rejected
    moto.locked_at       = None
    moto.locked_by       = None
    moto.previous_status = None

    db.add(ManualStatusChange(
        event_type=    "moto_rejected",
        motorcycle_id= body.motorcycle_id,
        reason=        body.reason,
        performed_by=  HARDCODED_USER_ID,
    ))

    await db.commit()
    return {"success": True, "message": "Motocicleta marcada como rechazada."}


async def handle_transfer_client(db: AsyncSession, body) -> dict:
    if body.from_client_id == body.to_client_id:
        raise HTTPException(
            status_code=400,
            detail="El cliente origen y destino no pueden ser el mismo.",
        )

    if body.sale_id:
        sale_result = await db.execute(
            select(Sale).where(Sale.sale_id == body.sale_id)
        )
        sale = sale_result.scalar_one_or_none()
        if not sale:
            raise HTTPException(status_code=404, detail="Venta no encontrada.")
        sale.client_id = body.to_client_id

        if sale.motorcycle_id:
            moto_result = await db.execute(
                select(Motorcycle).where(Motorcycle.motorcycle_id == sale.motorcycle_id)
            )
            moto = moto_result.scalar_one_or_none()
            if moto and moto.reservation_id:
                res_result = await db.execute(
                    select(Reservation).where(Reservation.reservation_id == moto.reservation_id)
                )
                linked_res = res_result.scalar_one_or_none()
                if linked_res:
                    linked_res.client_id = body.to_client_id

    if body.reservation_id:
        res_result = await db.execute(
            select(Reservation).where(Reservation.reservation_id == body.reservation_id)
        )
        reservation = res_result.scalar_one_or_none()
        if not reservation:
            raise HTTPException(status_code=404, detail="Reservación no encontrada.")
        reservation.client_id = body.to_client_id

    db.add(ClientTransferLog(
        sale_id=        body.sale_id,
        reservation_id= body.reservation_id,
        from_client_id= body.from_client_id,
        to_client_id=   body.to_client_id,
        reason=         body.reason,
        performed_by=   HARDCODED_USER_ID,
    ))

    await db.commit()
    return {"success": True, "message": "Datos de pago transferidos correctamente."}


async def get_moto_by_identifier(
    db: AsyncSession,
    motor: Optional[str],
    serie: Optional[str],
) -> list:
    conditions = []
    if motor:
        conditions.append(Motorcycle.motor_number == motor)
    if serie:
        conditions.append(Motorcycle.reference_number == serie)

    result = await db.execute(
        select(Motorcycle)
        .options(
            joinedload(Motorcycle.model),
            joinedload(Motorcycle.dealership),
        )
        .where(
            or_(*conditions),
            Motorcycle.status.in_([MotorcycleStatus.in_stock, MotorcycleStatus.in_stock_reserved]),
        )
    )
    motos = result.unique().scalars().all()

    return [
        {
            "motorcycle_id": m.motorcycle_id,
            "model_name":    m.model.canonical_name,
            "year":          m.model.year,
            "color":         m.color,
            "serie":         m.reference_number,
            "motor":         m.motor_number,
            "dealership":    m.dealership.name,
            "dealership_id": m.dealership.dealership_id,
            "status":        m.status.value,
            "reservation_id": m.reservation_id,
        }
        for m in motos
    ]
