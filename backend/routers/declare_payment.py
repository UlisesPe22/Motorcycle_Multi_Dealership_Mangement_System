from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload, selectinload

from database import get_db
from config import DISCOUNTS_ACTIVE
from models.client import Client
from models.credit_institution import CreditInstitution
from models.dealership import Dealership
from models.motorcycle import Motorcycle, MotorcycleStatus
from models.motorcycle_catalog import MotorcycleCatalog
from models.motorcycle_catalog_color import MotorcycleCatalogColor
from models.payment_event import PaymentEvent
from models.payment_item import PaymentItem
from models.payment_method import PaymentMethod
from models.reservation import Reservation, ReservationStatus
from models.sale import Sale

router = APIRouter(prefix="/declare-payment", tags=["declare-payment"])


# ======================================================================== #
# GET /declare-payment/clients                                               #
# ======================================================================== #

@router.get("/clients")
async def get_clients(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Client).order_by(Client.nombre_completo.asc())
    )
    clients = result.scalars().all()
    return [
        {
            "client_id":       c.client_id,
            "nombre_completo": c.nombre_completo,
            "rfc":             c.curp,
        }
        for c in clients
    ]


# ======================================================================== #
# GET /declare-payment/dealerships                                           #
# ======================================================================== #

@router.get("/dealerships")
async def get_dealerships(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Dealership).order_by(Dealership.name.asc())
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
# GET /declare-payment/models                                                #
# ======================================================================== #

@router.get("/models")
async def get_models(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MotorcycleCatalog)
        .options(
            selectinload(MotorcycleCatalog.available_colors)
            .selectinload(MotorcycleCatalogColor.color)
        )
        .order_by(MotorcycleCatalog.canonical_name.asc())
    )
    models = result.scalars().all()
    return [
        {
            "model_id":       m.model_id,
            "canonical_name": m.canonical_name,
            "year":           m.year,
            "price":          m.discount_price if DISCOUNTS_ACTIVE else m.full_price,
            "colors":         [mc.color.name for mc in m.available_colors],
        }
        for m in models
    ]


# ======================================================================== #
# GET /declare-payment/motorcycles                                           #
# ======================================================================== #

async def _get_reservation_deposit(
    db: AsyncSession,
    client_id: int,
    model_id: int,
    motorcycle_id: int = None,
) -> float:
    # Try by motorcycle_id first (seeded or assigned sales)
    if motorcycle_id:
        result = await db.execute(
            select(func.sum(PaymentItem.amount))
            .join(PaymentEvent, PaymentItem.payment_event_id == PaymentEvent.payment_event_id)
            .join(Sale, PaymentEvent.sale_id == Sale.sale_id)
            .where(
                PaymentEvent.event_type == "reservation",
                Sale.motorcycle_id      == motorcycle_id,
                Sale.status             == "open",
            )
        )
        total = result.scalar() or 0.0
        if total > 0:
            return total

    # Fallback — find reservation deposit for this client + model regardless
    # of whether a motorcycle has been assigned to the sale yet.
    result = await db.execute(
        select(func.sum(PaymentItem.amount))
        .join(PaymentEvent, PaymentItem.payment_event_id == PaymentEvent.payment_event_id)
        .join(Sale, PaymentEvent.sale_id == Sale.sale_id)
        .join(Reservation, Reservation.client_id == Sale.client_id)
        .where(
            PaymentEvent.event_type == "reservation",
            Sale.client_id          == client_id,
            Sale.status             == "open",
            Reservation.model_id    == model_id,
            Reservation.status.in_([
                ReservationStatus.active,
                ReservationStatus.assigned,
            ]),
        )
    )
    return result.scalar() or 0.0


@router.get("/motorcycles")
async def get_motorcycles(
    dealership_id: int = Query(...),
    client_id:     int = Query(...),
    payment_type:  str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    if payment_type == "reservation":
        return []

    if payment_type not in ("al_contado", "enganche"):
        return []

    # In-stock motos at the dealership
    result = await db.execute(
        select(Motorcycle)
        .options(joinedload(Motorcycle.model))
        .where(
            Motorcycle.dealership_id == dealership_id,
            Motorcycle.status        == MotorcycleStatus.in_stock,
        )
    )
    in_stock = result.unique().scalars().all()

    # In-stock-reserved motos at the dealership belonging to this client
    result2 = await db.execute(
        select(Motorcycle)
        .options(joinedload(Motorcycle.model))
        .join(Reservation, Motorcycle.reservation_id == Reservation.reservation_id)
        .where(
            Motorcycle.dealership_id == dealership_id,
            Motorcycle.status        == MotorcycleStatus.in_stock_reserved,
            Reservation.client_id    == client_id,
            Reservation.status       == ReservationStatus.assigned,
        )
    )
    reserved = result2.unique().scalars().all()
    reserved_ids = {m.motorcycle_id for m in reserved}

    combined = list(reserved) + [m for m in in_stock if m.motorcycle_id not in reserved_ids]

    result_list = []
    for m in combined:
        result_list.append({
            "motorcycle_id":       m.motorcycle_id,
            "model_name":          m.model.canonical_name,
            "color":               m.color or "",
            "reference_number":    m.reference_number or "",
            "status":              m.status.value,
            "price":               m.model.discount_price if DISCOUNTS_ACTIVE else m.model.full_price,
            "reservation_deposit": await _get_reservation_deposit(db, client_id, m.model_id, m.motorcycle_id),
        })
    return result_list


# ======================================================================== #
# GET /declare-payment/payment-methods                                       #
# ======================================================================== #

@router.get("/payment-methods")
async def get_payment_methods(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PaymentMethod)
        .where(PaymentMethod.name != "Financiera")
        .order_by(PaymentMethod.name.asc())
    )
    methods = result.scalars().all()
    return [
        {
            "method_id": m.method_id,
            "name":      m.name,
        }
        for m in methods
    ]


# ======================================================================== #
# GET /declare-payment/financieras                                           #
# ======================================================================== #

@router.get("/financieras")
async def get_financieras(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CreditInstitution).order_by(CreditInstitution.name.asc())
    )
    institutions = result.scalars().all()
    return [
        {
            "credit_institution_id": i.credit_institution_id,
            "name":                  i.name,
        }
        for i in institutions
    ]


# ======================================================================== #
# POST /declare-payment/submit                                               #
# ======================================================================== #

class PaymentItemInput(BaseModel):
    method_id: int
    amount:    float


class DeclarePaymentRequest(BaseModel):
    payment_type:  str
    dealership_id: int
    client_id:     int
    motorcycle_id: Optional[int]       = None
    model_id:      Optional[int]       = None
    colors:        Optional[List[str]] = None
    payment_items: List[PaymentItemInput]
    financiera_id: Optional[int]       = None


@router.post("/submit")
async def submit_payment(body: DeclarePaymentRequest, db: AsyncSession = Depends(get_db)):
    from services.pipeline_payment_declaration import handle_payment_declaration
    return await handle_payment_declaration(db, body)
