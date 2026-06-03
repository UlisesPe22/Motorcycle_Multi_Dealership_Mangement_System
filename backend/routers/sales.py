import os
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from database import get_db
from config import CONTRACTS_STORAGE_PATH, SALE_LOCK_MINUTES
from models.motorcycle import Motorcycle, MotorcycleStatus
from models.motorcycle_catalog import MotorcycleCatalog
from models.client import Client
from models.dealership import Dealership
from models.contract import Contract, SaleType, PaymentMethod
from models.credit_institution import CreditInstitution
from models.event import Event, EventName, EventStatus
from models.reservation import Reservation, ReservationStatus
from models.user import User
from config import HARDCODED_USER_ID
from services.pipeline_sale import (
    generate_contract_number,
    generate_documents,
    get_moto_price,
)
from services.pipeline_utils import create_event

router = APIRouter(prefix="/sales", tags=["sales"])


# ======================================================================== #
# GET /sales/clients                                                         #
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
            "curp":            c.curp,
            "email":           getattr(c, "email", None) or "",
            "phone":           getattr(c, "phone", None) or "",
        }
        for c in clients
    ]


# ======================================================================== #
# GET /sales/motorcycles                                                     #
# ======================================================================== #

@router.get("/motorcycles")
async def get_motorcycles(client_id: Optional[int] = None,
                          db: AsyncSession = Depends(get_db)):

    # Lazy unlock — release any expired sale locks
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=SALE_LOCK_MINUTES)
    result = await db.execute(
        select(Motorcycle).where(
            Motorcycle.status    == MotorcycleStatus.reserved_for_sale,
            Motorcycle.locked_at <= cutoff,
        )
    )
    expired = result.scalars().all()
    for moto in expired:
        moto.status          = MotorcycleStatus(moto.previous_status or "in_stock")
        moto.previous_status = None
        moto.locked_at       = None
    if expired:
        await db.commit()

    # STEP A — Find client's reserved motorcycle
    reserved_moto_id = None
    if client_id:
        result = await db.execute(
            select(Reservation)
            .options(selectinload(Reservation.motorcycle))
            .where(
                Reservation.client_id == client_id,
                Reservation.status    == ReservationStatus.assigned,
            )
            .order_by(Reservation.created_at.asc())
        )
        reservation = result.scalar_one_or_none()
        if reservation and reservation.motorcycle:
            moto = reservation.motorcycle
            if moto.status == MotorcycleStatus.in_stock_reserved:
                reserved_moto_id = moto.motorcycle_id

    # STEP B — Query available in_stock motorcycles
    result = await db.execute(
        select(Motorcycle)
        .options(
            joinedload(Motorcycle.dealership),
            joinedload(Motorcycle.model),
        )
        .where(Motorcycle.status == MotorcycleStatus.in_stock)
    )
    available = result.unique().scalars().all()

    if reserved_moto_id:
        result = await db.execute(
            select(Motorcycle)
            .options(
                joinedload(Motorcycle.dealership),
                joinedload(Motorcycle.model),
            )
            .where(Motorcycle.motorcycle_id == reserved_moto_id)
        )
        reserved_moto = result.unique().scalar_one_or_none()
        if reserved_moto:
            available = [reserved_moto] + [
                m for m in available
                if m.motorcycle_id != reserved_moto_id
            ]

    # STEP C — Return
    return [
        {
            "motorcycle_id": m.motorcycle_id,
            "model":         m.model.canonical_name,
            "year":          m.model.year,
            "color":         m.color or "",
            "serie":         m.reference_number or "",
            "motor":         m.motor_number or "",
            "dealership":    m.dealership.name,
            "dealership_id": m.dealership.dealership_id,
            "price":         get_moto_price(m.model),
            "pre_selected":  m.motorcycle_id == reserved_moto_id,
            "status":        m.status.value,
        }
        for m in available
    ]


# ======================================================================== #
# GET /sales/credit-institutions                                             #
# ======================================================================== #

@router.get("/credit-institutions")
async def get_credit_institutions(db: AsyncSession = Depends(get_db)):
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
# POST /sales/lock-motorcycle                                                #
# ======================================================================== #

class LockMotorcycleBody(BaseModel):
    motorcycle_id:          int
    previous_motorcycle_id: Optional[int] = None


@router.post("/lock-motorcycle")
async def lock_motorcycle(body: LockMotorcycleBody, db: AsyncSession = Depends(get_db)):
    try:
        # 1. Unlock previous motorcycle if provided
        if body.previous_motorcycle_id:
            result = await db.execute(
                select(Motorcycle)
                .where(
                    Motorcycle.motorcycle_id == body.previous_motorcycle_id,
                    Motorcycle.status        == MotorcycleStatus.reserved_for_sale,
                )
                .with_for_update()
            )
            prev = result.scalar_one_or_none()
            if prev:
                prev.status          = MotorcycleStatus(prev.previous_status or "in_stock")
                prev.previous_status = None
                prev.locked_at       = None
                await db.flush()

        # 2. Lock new motorcycle
        result = await db.execute(
            select(Motorcycle)
            .where(
                Motorcycle.motorcycle_id == body.motorcycle_id,
                Motorcycle.status.in_([
                    MotorcycleStatus.in_stock,
                    MotorcycleStatus.in_stock_reserved,
                ]),
            )
            .with_for_update()
        )
        moto = result.scalar_one_or_none()
        if not moto:
            await db.rollback()
            return {"success": False,
                    "message": "Esta motocicleta ya no está disponible."}

        now                  = datetime.now(timezone.utc).replace(tzinfo=None)
        moto.previous_status = moto.status.value
        moto.status          = MotorcycleStatus.reserved_for_sale
        moto.locked_at       = now
        await db.flush()

        await db.commit()
        return {
            "success":       True,
            "motorcycle_id": body.motorcycle_id,
            "locked_at":     moto.locked_at.isoformat(),
        }

    except Exception as e:
        await db.rollback()
        return {"success": False, "message": str(e)}


# ======================================================================== #
# POST /sales/unlock-motorcycle                                              #
# ======================================================================== #

class UnlockMotorcycleBody(BaseModel):
    motorcycle_id: int


@router.post("/unlock-motorcycle")
async def unlock_motorcycle(body: UnlockMotorcycleBody, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(
            select(Motorcycle).where(
                Motorcycle.motorcycle_id == body.motorcycle_id,
                Motorcycle.status        == MotorcycleStatus.reserved_for_sale,
            )
        )
        moto = result.scalar_one_or_none()
        if not moto:
            return {"success": True}

        moto.status          = MotorcycleStatus(moto.previous_status or "in_stock")
        moto.previous_status = None
        moto.locked_at       = None

        await db.commit()
        return {"success": True}

    except Exception as e:
        await db.rollback()
        return {"success": False, "message": str(e)}


# ======================================================================== #
# POST /sales/create                                                         #
# ======================================================================== #

class SaleCreateBody(BaseModel):
    client_id:              int
    motorcycle_id:          int
    sale_type:              str
    payment_method:         str
    payment_downpayment:    Optional[float] = None
    payment_institution_id: Optional[int]   = None
    payment_bank:           Optional[str]   = None
    reference_name:         Optional[str]   = None
    reference_phone:        Optional[str]   = None
    reference_relation:     Optional[str]   = None
    buyer_colonia:          Optional[str]   = None
    buyer_cp:               Optional[str]   = None
    buyer_municipio:        Optional[str]   = None
    buyer_estado:           Optional[str]   = None


@router.post("/create")
async def create_sale(body: SaleCreateBody, db: AsyncSession = Depends(get_db)):
    try:
        # 1. Validate client
        result = await db.execute(
            select(Client).where(Client.client_id == body.client_id)
        )
        client = result.scalar_one_or_none()
        if not client:
            return {"success": False,
                    "message": f"Cliente con id {body.client_id} no encontrado."}

        # 2. Validate motorcycle is locked for sale (SELECT FOR UPDATE)
        result = await db.execute(
            select(Motorcycle)
            .where(
                Motorcycle.motorcycle_id == body.motorcycle_id,
                Motorcycle.status        == MotorcycleStatus.reserved_for_sale,
            )
            .with_for_update()
        )
        moto = result.scalar_one_or_none()
        if not moto:
            return {"success": False,
                    "message": "Esta motocicleta ya no está disponible. "
                               "Por favor selecciónala nuevamente."}

        # 3. Get dealership
        result = await db.execute(
            select(Dealership).where(Dealership.dealership_id == moto.dealership_id)
        )
        dealership = result.scalar_one()

        # 4. Generate contract number
        contract_number = await generate_contract_number(db, dealership.dealership_id)

        # 5. Create Event row
        now   = datetime.now(timezone.utc).replace(tzinfo=None)
        event = await create_event(db, EventName.sale_validation.value, HARDCODED_USER_ID)

        # 6. Create Contract row
        contract = Contract(
            contract_number        = contract_number,
            sale_event_id          = event.event_id,
            client_id              = body.client_id,
            motorcycle_id          = body.motorcycle_id,
            dealership_id          = dealership.dealership_id,
            employee_id            = HARDCODED_USER_ID,
            sale_type              = SaleType(body.sale_type),
            payment_method         = PaymentMethod(body.payment_method),
            payment_downpayment    = body.payment_downpayment,
            payment_institution_id = body.payment_institution_id,
            payment_bank           = body.payment_bank,
            reference_name         = body.reference_name,
            reference_phone        = body.reference_phone,
            reference_relation     = body.reference_relation,
            buyer_colonia          = body.buyer_colonia,
            buyer_cp               = body.buyer_cp,
            buyer_municipio        = body.buyer_municipio,
            buyer_estado           = body.buyer_estado,
            created_at             = now,
        )
        db.add(contract)
        await db.flush()

        # 7. Reload contract with all relationships for generate_documents
        result = await db.execute(
            select(Contract)
            .options(
                selectinload(Contract.client),
                selectinload(Contract.motorcycle).selectinload(Motorcycle.model),
                selectinload(Contract.dealership),
                selectinload(Contract.employee),
                selectinload(Contract.institution),
            )
            .where(Contract.contract_id == contract.contract_id)
        )
        loaded_contract = result.scalar_one()

        # 8. Generate documents
        await generate_documents(loaded_contract, db)

        # 9. Mark motorcycle sold, clear lock fields
        moto.status          = MotorcycleStatus.sold
        moto.previous_status = None
        moto.locked_at       = None
        await db.flush()

        # 10. Complete event
        event.status             = EventStatus.complete
        event.completed_at       = now
        event.linked_entity_type = "CONTRACT"
        event.linked_entity_id   = contract.contract_id
        await db.flush()

        # 11. Commit
        await db.commit()

        return {
            "success":         True,
            "message":         f"Venta registrada. Contrato {contract_number}.",
            "contract_id":     contract.contract_id,
            "contract_number": contract_number,
            "has_solicitud":   body.sale_type == "credito",
        }

    except Exception as e:
        await db.rollback()
        return {"success": False, "message": str(e)}


# ======================================================================== #
# GET /sales/{contract_id}/download/contrato                                #
# ======================================================================== #

@router.get("/{contract_id}/download/contrato")
async def download_contrato(contract_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Contract).where(Contract.contract_id == contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato no encontrado.")

    path = os.path.join(
        CONTRACTS_STORAGE_PATH,
        f"{contract.contract_number}_contrato.docx"
    )
    if not os.path.exists(path):
        raise HTTPException(status_code=404,
                            detail="Archivo de contrato no encontrado.")

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{contract.contract_number}_contrato.docx",
    )


# ======================================================================== #
# GET /sales/{contract_id}/download/solicitud                               #
# ======================================================================== #

@router.get("/{contract_id}/download/solicitud")
async def download_solicitud(contract_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Contract).where(Contract.contract_id == contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato no encontrado.")

    if contract.sale_type != SaleType.credito:
        raise HTTPException(status_code=404,
                            detail="Este contrato no es de tipo crédito.")

    path = os.path.join(
        CONTRACTS_STORAGE_PATH,
        f"{contract.contract_number}_solicitud.docx"
    )
    if not os.path.exists(path):
        raise HTTPException(status_code=404,
                            detail="Archivo de solicitud no encontrado.")

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{contract.contract_number}_solicitud.docx",
    )
