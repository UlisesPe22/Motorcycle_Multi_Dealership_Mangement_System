from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException
from models.client import Client
from models.dealership import Dealership
from models.motorcycle_catalog import MotorcycleCatalog
from models.motorcycle import Motorcycle, MotorcycleStatus
from models.event import Event, EventName, EventStatus
from models.reservation import Reservation, ReservationStatus
from models.reservation_color import ReservationColor
from models.color import Color
from config import HARDCODED_USER_ID
from services.pipeline_utils import (
    _auto_assign_reservations,
    _print_reservation_assignment_results,
    create_event,
)


def create_reservation(db: Session, body) -> dict:
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
        client = db.query(Client).filter(Client.client_id == body.client_id).first()
        if not client:
            raise HTTPException(
                status_code=404,
                detail=f"Cliente con id {body.client_id} no encontrado."
            )

        # 2. Validate model exists
        model = db.query(MotorcycleCatalog).filter(
            MotorcycleCatalog.model_id == body.model_id
        ).first()
        if not model:
            raise HTTPException(
                status_code=404,
                detail=f"Modelo con id {body.model_id} no encontrado en el catálogo."
            )

        # 3. Validate dealership exists
        dealership = db.query(Dealership).filter(
            Dealership.dealership_id == body.dealership_id
        ).first()
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
        event = create_event(db, EventName.motorcycle_reservation.value, HARDCODED_USER_ID)

        # 7. Create Reservation row
        reservation = Reservation(
            client_id      = body.client_id,
            model_id       = body.model_id,
            dealership_id  = body.dealership_id,
            deposit_amount = body.deposit_amount,
            status         = ReservationStatus.active,
            created_by     = HARDCODED_USER_ID,
            event_id       = event.event_id,
            created_at     = datetime.now(timezone.utc),
        )
        db.add(reservation)
        db.flush()

        # 8. Create ReservationColor rows (priority = index, first = highest priority)
        for priority, raw_color in enumerate(body.colors, start=1):
            color_obj = db.query(Color).filter(Color.name == raw_color).first()
            db.add(ReservationColor(
                reservation_id = reservation.reservation_id,
                color_id       = color_obj.color_id,
                priority       = priority,
            ))
        db.flush()

        # 9. Mark event complete and link entity
        event.status             = EventStatus.complete
        event.completed_at       = datetime.now(timezone.utc)
        event.linked_entity_type = "RESERVATION"
        event.linked_entity_id   = reservation.reservation_id

        # 10. Trigger A — auto-assign against incoming unassigned pool
        # Query only incoming motos for this dealership that are not
        # yet assigned to any reservation. The model matching and color
        # priority logic is handled inside _auto_assign_reservations().
        incoming_pool = db.query(Motorcycle).filter(
            Motorcycle.dealership_id  == body.dealership_id,
            Motorcycle.status         == MotorcycleStatus.incoming,
            Motorcycle.reservation_id == None,
        ).all()

        assigned = False
        if incoming_pool:
            assignment_results = _auto_assign_reservations(
                db, body.dealership_id, incoming_pool
            )
            _print_reservation_assignment_results(assignment_results)
            assigned = any(
                r["result"] == "ASSIGNED" and
                r["reservation_id"] == reservation.reservation_id
                for r in assignment_results
            )

        # 11. Commit everything atomically
        db.commit()

        status_label = "assigned" if assigned else "active"
        message = f"Reservación registrada. ID: {reservation.reservation_id}."
        if assigned:
            message += " Motocicleta incoming asignada automáticamente."
        else:
            message += " En espera de motocicleta disponible."

        return {
            "success":        True,
            "message":        message,
            "reservation_id": reservation.reservation_id,
            "status":         status_label,
            "assigned":       assigned,
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        return {"success": False, "message": str(e)}
