from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database import get_db
from models.client import Client
from models.dealership import Dealership
from models.motorcycle_catalog import MotorcycleCatalog
from models.motorcycle_catalog_color import MotorcycleCatalogColor
from services.pipeline_reservation import create_reservation

router = APIRouter(prefix="/reservations", tags=["reservations"])


# ======================================================================== #
# GET /reservations/clients                                                  #
# ======================================================================== #

@router.get("/clients")
async def get_clients(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Client).order_by(Client.nombre_completo)
    )
    clients = result.scalars().all()
    return [
        {
            "client_id":       c.client_id,
            "nombre_completo": c.nombre_completo,
            "curp":            c.curp,
        }
        for c in clients
    ]


# ======================================================================== #
# GET /reservations/dealerships                                              #
# ======================================================================== #

@router.get("/dealerships")
async def get_dealerships(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Dealership).order_by(Dealership.name)
    )
    dealerships = result.scalars().all()
    return [
        {
            "dealership_id": d.dealership_id,
            "name":          d.name,
        }
        for d in dealerships
    ]


# ======================================================================== #
# GET /reservations/models                                                   #
# ======================================================================== #

@router.get("/models")
async def get_models(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MotorcycleCatalog)
        .options(
            selectinload(MotorcycleCatalog.available_colors)
            .selectinload(MotorcycleCatalogColor.color)
        )
        .order_by(MotorcycleCatalog.canonical_name.asc(), MotorcycleCatalog.year.desc())
    )
    models = result.scalars().all()
    return [
        {
            "model_id":       m.model_id,
            "canonical_name": m.canonical_name,
            "year":           m.year,
            "colors":         [ac.color.name for ac in m.available_colors],
        }
        for m in models
    ]


# ======================================================================== #
# POST /reservations/create                                                  #
# ======================================================================== #

class ReservationCreate(BaseModel):
    client_id:      int
    model_id:       int
    dealership_id:  int
    colors:         List[str]
    deposit_amount: float


@router.post("/create")
async def create_reservation_endpoint(
    body: ReservationCreate,
    db: AsyncSession = Depends(get_db)
):
    return await create_reservation(db, body)
