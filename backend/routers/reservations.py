from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.client import Client
from models.dealership import Dealership
from models.motorcycle_catalog import MotorcycleCatalog
from services.pipeline_reservation import create_reservation

router = APIRouter(prefix="/reservations", tags=["reservations"])


# ======================================================================== #
# GET /reservations/clients                                                  #
# ======================================================================== #

@router.get("/clients")
def get_clients(db: Session = Depends(get_db)):
    clients = db.query(Client).order_by(Client.nombre_completo).all()
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
def get_dealerships(db: Session = Depends(get_db)):
    dealerships = db.query(Dealership).order_by(Dealership.name).all()
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
def get_models(db: Session = Depends(get_db)):
    models = (
        db.query(MotorcycleCatalog)
        .order_by(MotorcycleCatalog.canonical_name.asc(), MotorcycleCatalog.year.desc())
        .all()
    )
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
def create_reservation_endpoint(
    body: ReservationCreate,
    db: Session = Depends(get_db)
):
    return create_reservation(db, body)
