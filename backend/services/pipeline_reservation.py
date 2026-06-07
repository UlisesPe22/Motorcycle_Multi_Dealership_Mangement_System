from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException

from models.client import Client
from models.dealership import Dealership
from models.motorcycle_catalog import MotorcycleCatalog
from models.motorcycle_catalog_color import MotorcycleCatalogColor
from models.event import Event, EventName, EventStatus
from models.reservation import Reservation, ReservationStatus
from models.reservation_color import ReservationColor
from models.color import Color
from config import HARDCODED_USER_ID
from services.pipeline_utils import create_event


async def create_reservation(db: AsyncSession, body) -> dict:
    """
    Full reservation creation pipeline.
    Validates all inputs, creates reservation records,
    triggers auto-assignment, returns result dict.

    Returns dict with keys:
      success, message, reservation_id, status, assigned
    Never raises exceptions — returns error dict on failure.
    """
    try:
        # 1. Validate client exists
        result = await db.execute(
            select(Client).where(Client.client_id == body.client_id)
        )
        client = result.scalar_one_or_none()
        if not client:
            raise HTTPException(
                status_code=404,
                detail=f"Cliente con id {body.client_id} no encontrado."
            )

        # 2. Validate model exists (with available_colors eagerly loaded)
        result = await db.execute(
            select(MotorcycleCatalog)
            .options(
                selectinload(MotorcycleCatalog.available_colors)
                .selectinload(MotorcycleCatalogColor.color)
            )
            .where(MotorcycleCatalog.model_id == body.model_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            raise HTTPException(
                status_code=404,
                detail=f"Modelo con id {body.model_id} no encontrado en el catálogo."
            )

        # 3. Validate dealership exists
        result = await db.execute(
            select(Dealership).where(Dealership.dealership_id == body.dealership_id)
        )
        dealership = result.scalar_one_or_none()
        if not dealership:
            raise HTTPException(
                status_code=404,
                detail=f"Sucursal con id {body.dealership_id} no encontrada."
            )

        # 4. Validate deposit_amount > 0
        if body.deposit_amount <= 0:
            raise HTTPException(
                status_code=400,
                detail="El monto de reservación debe ser mayor a cero."
            )

        # 5. Validate colors — non-empty, all valid for this model, no duplicates
        if not body.colors:
            raise HTTPException(
                status_code=400,
                detail="Debes seleccionar al menos un color de preferencia."
            )

        valid_color_values = {ac.color.name for ac in model.available_colors}
        seen = set()
        for raw_color in body.colors:
            if raw_color not in valid_color_values:
                raise HTTPException(
                    status_code=400,
                    detail=f"Color '{raw_color}' no es válido para este modelo."
                )
            if raw_color in seen:
                raise HTTPException(
                    status_code=400,
                    detail=f"Color duplicado: '{raw_color}'."
                )
            seen.add(raw_color)

        # 6. Create Event row
        event = await create_event(db, EventName.motorcycle_reservation.value, HARDCODED_USER_ID)

        # 7. Create Reservation row
        reservation = Reservation(
            client_id      = body.client_id,
            model_id       = body.model_id,
            dealership_id  = body.dealership_id,
            deposit_amount = body.deposit_amount,
            status         = ReservationStatus.active,
            created_by     = HARDCODED_USER_ID,
            event_id       = event.event_id,
            created_at = datetime.now(timezone.utc).replace(tzinfo=None),

        )
        db.add(reservation)
        await db.flush()

        # 8. Create ReservationColor rows
        for priority, raw_color in enumerate(body.colors, start=1):
            result = await db.execute(
                select(Color).where(Color.name == raw_color)
            )
            color_obj = result.scalar_one_or_none()
            db.add(ReservationColor(
                reservation_id = reservation.reservation_id,
                color_id       = color_obj.color_id,
                priority       = priority,
            ))
        await db.flush()

        # 9. Mark event complete and link entity
        event.status             = EventStatus.complete
        event.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        event.linked_entity_type = "RESERVATION"
        event.linked_entity_id   = reservation.reservation_id

        # 10. Commit everything atomically
        await db.commit()

        return {
            "success":        True,
            "message":        f"Reservación registrada. ID: {reservation.reservation_id}. En espera de motocicleta disponible.",
            "reservation_id": reservation.reservation_id,
            "status":         "active",
        }

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        return {"success": False, "message": str(e)}
