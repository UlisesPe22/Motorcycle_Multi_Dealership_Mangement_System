from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.motorcycle import Motorcycle
from models.motorcycle_catalog import MotorcycleCatalog
from models.dealership import Dealership

router = APIRouter(prefix="/motorcycles", tags=["motorcycles"])


@router.get("/")
async def list_motorcycles(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Motorcycle, MotorcycleCatalog, Dealership)
        .outerjoin(MotorcycleCatalog, Motorcycle.model_id == MotorcycleCatalog.model_id)
        .outerjoin(Dealership, Motorcycle.dealership_id == Dealership.dealership_id)
        .order_by(Motorcycle.created_at.desc())
    )
    rows = result.all()
    return [
        {
            "motorcycle_id": m.motorcycle_id,
            "model":         cat.canonical_name if cat else None,
            "year":          cat.year           if cat else None,
            "color":         m.color,
            "status":        m.status.value,
            "dealership":    d.name             if d else None,
            "motor":         m.motor_number,
            "serie":         m.reference_number,
        }
        for m, cat, d in rows
    ]
