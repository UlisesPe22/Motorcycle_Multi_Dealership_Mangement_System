from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.user import User, UserRole
from models.dealership import Dealership
from models.event import Event, EventType, EventName, EventStatus

router = APIRouter(prefix="/registrar", tags=["registrar"])

HARDCODED_USER_ID = 2


# ======================================================================== #
# Schemas                                                                   #
# ======================================================================== #

class VendedorCreate(BaseModel):
    name:          str
    phone:         str
    dealership_id: int


# ======================================================================== #
# Endpoints                                                                 #
# ======================================================================== #

@router.get("/dealerships")
def get_dealerships(db: Session = Depends(get_db)):
    """Returns all dealerships ordered by name for the dealership dropdown."""
    dealerships = (
        db.query(Dealership)
        .order_by(Dealership.name.asc())
        .all()
    )
    return [
        {"dealership_id": d.dealership_id, "name": d.name}
        for d in dealerships
    ]


@router.post("/vendedor")
def create_vendedor(body: VendedorCreate, db: Session = Depends(get_db)):
    """Registers a new employee user and records the event."""
    try:
        # 1. Validate name
        if not body.name.strip():
            return {"success": False, "message": "El nombre es requerido."}

        # 2. Validate phone
        if not body.phone.strip():
            return {"success": False, "message": "El teléfono es requerido."}

        # 3. Validate dealership exists
        dealership = db.query(Dealership).filter(
            Dealership.dealership_id == body.dealership_id
        ).first()
        if not dealership:
            return {"success": False, "message": "Sucursal no encontrada."}

        # 4. Look up EventType for registrar_vendedor
        event_type = db.query(EventType).filter(
            EventType.name == EventName.registrar_vendedor
        ).first()
        if not event_type:
            return {"success": False, "message": "Event type not found — run seed.py"}

        # 5. Create Event row
        event = Event(
            event_type_id = event_type.event_type_id,
            initiated_by  = HARDCODED_USER_ID,
            status        = EventStatus.in_progress,
            started_at    = datetime.now(timezone.utc),
        )
        db.add(event)
        db.flush()

        # 6. Create User row
        user = User(
            name          = body.name.strip(),
            phone         = body.phone.strip(),
            role          = UserRole.employee,
            dealership_id = body.dealership_id,
            created_by    = HARDCODED_USER_ID,
            created_at    = datetime.now(timezone.utc),
        )
        db.add(user)
        db.flush()

        # 7. Mark event complete and link entity
        event.status             = EventStatus.complete
        event.completed_at       = datetime.now(timezone.utc)
        event.linked_entity_type = "USER"
        event.linked_entity_id   = user.user_id
        db.flush()

        # 8. Commit
        db.commit()

        # 9. Return success
        return {
            "success": True,
            "message": f"Vendedor {user.name} registrado correctamente.",
            "user_id": user.user_id,
        }

    except Exception as e:
        db.rollback()
        return {"success": False, "message": str(e)}
