from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.user import User, UserRole
from models.dealership import Dealership
from models.event import EventName, EventStatus
from config import HARDCODED_USER_ID
from services.pipeline_utils import create_event

router = APIRouter(prefix="/registrar", tags=["registrar"])


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
async def get_dealerships(db: AsyncSession = Depends(get_db)):
    """Returns all dealerships ordered by name for the dealership dropdown."""
    result = await db.execute(
        select(Dealership).order_by(Dealership.name.asc())
    )
    dealerships = result.scalars().all()
    return [
        {"dealership_id": d.dealership_id, "name": d.name}
        for d in dealerships
    ]


@router.post("/vendedor")
async def create_vendedor(body: VendedorCreate, db: AsyncSession = Depends(get_db)):
    """Registers a new employee user and records the event."""
    try:
        # 1. Validate name
        if not body.name.strip():
            return {"success": False, "message": "El nombre es requerido."}

        # 2. Validate phone
        if not body.phone.strip():
            return {"success": False, "message": "El teléfono es requerido."}

        # 3. Validate dealership exists
        result = await db.execute(
            select(Dealership).where(Dealership.dealership_id == body.dealership_id)
        )
        dealership = result.scalar_one_or_none()
        if not dealership:
            return {"success": False, "message": "Sucursal no encontrada."}

        # 4. Create Event row
        event = await create_event(db, EventName.registrar_vendedor.value, HARDCODED_USER_ID)

        # 5. Create User row
        user = User(
            name          = body.name.strip(),
            phone         = body.phone.strip(),
            role          = UserRole.employee,
            dealership_id = body.dealership_id,
            created_by    = HARDCODED_USER_ID,
            created_at    = datetime.now(timezone.utc),
        )
        db.add(user)
        await db.flush()

        # 6. Mark event complete and link entity
        event.status             = EventStatus.complete
        event.completed_at       = datetime.now(timezone.utc)
        event.linked_entity_type = "USER"
        event.linked_entity_id   = user.user_id
        await db.flush()

        # 7. Commit
        await db.commit()

        return {
            "success": True,
            "message": f"Vendedor {user.name} registrado correctamente.",
            "user_id": user.user_id,
        }

    except Exception as e:
        await db.rollback()
        return {"success": False, "message": str(e)}
