from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from database import get_db
from config import HARDCODED_USER_ID, MAX_PAYMENT_ITEMS_PER_EVENT, DISCOUNTS_ACTIVE
from models.client import Client
from models.color import Color
from models.credit_institution import CreditInstitution
from models.dealership import Dealership
from models.motorcycle import Motorcycle, MotorcycleStatus
from models.motorcycle_catalog import MotorcycleCatalog
from models.motorcycle_catalog_color import MotorcycleCatalogColor
from models.payment_event import PaymentEvent
from models.payment_item import PaymentItem
from models.payment_method import PaymentMethod
from models.reservation import Reservation, ReservationStatus
from models.reservation_color import ReservationColor
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

    return [
        {
            "motorcycle_id":    m.motorcycle_id,
            "model_name":       m.model.canonical_name,
            "color":            m.color or "",
            "reference_number": m.reference_number or "",
            "status":           m.status.value,
            "price":            m.model.discount_price if DISCOUNTS_ACTIVE else m.model.full_price,
        }
        for m in combined
    ]


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
        result = await db.execute(
            select(Sale).where(
                Sale.motorcycle_id == body.motorcycle_id,
                Sale.status        == "open",
            )
        )
        sale = result.scalar_one_or_none()
    else:
        result = await db.execute(
            select(Sale).where(
                Sale.client_id    == body.client_id,
                Sale.motorcycle_id == None,  # noqa: E711
                Sale.status       == "open",
            )
        )
        sale = result.scalar_one_or_none()

    if not sale:
        sale = Sale(
            motorcycle_id   = body.motorcycle_id,
            client_id       = body.client_id,
            vendor_id       = HARDCODED_USER_ID,
            dealership_id   = body.dealership_id,
            total_price     = total_price,
            amount_verified = 0.0,
            status          = "open",
        )
        db.add(sale)
        await db.flush()

    # 4. Enforce one event per type per sale
    result = await db.execute(
        select(PaymentEvent).where(
            PaymentEvent.sale_id    == sale.sale_id,
            PaymentEvent.event_type == body.payment_type,
        )
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
            status           = "pending",
        ))
    await db.flush()

    # 7. If enganche → auto-create financing PaymentEvent
    if body.payment_type == "enganche":
        financing_amount = total_price - payment_sum

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
            status           = "pending",
        ))
        await db.flush()

    # 8. If reservation → create Reservation record (no Event row)
    if body.payment_type == "reservation":
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

    return {
        "success":          True,
        "sale_id":          sale.sale_id,
        "payment_event_id": payment_event.payment_event_id,
        "message":          "Pago declarado exitosamente.",
    }
