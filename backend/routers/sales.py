import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from database import get_db
from config import CONTRACTS_STORAGE_PATH
from models.motorcycle import Motorcycle, MotorcycleStatus
from models.motorcycle_catalog import MotorcycleCatalog
from models.client import Client
from models.dealership import Dealership
from models.contract import Contract, SaleType, PaymentMethod
from models.credit_institution import CreditInstitution
from models.event import Event, EventName, EventStatus
from models.reservation import Reservation, ReservationStatus
from models.user import User
from services.pipeline_sale import (
    generate_contract_number,
    generate_documents,
    get_moto_price,
)

router = APIRouter(prefix="/sales", tags=["sales"])

HARDCODED_USER_ID = 2


# ======================================================================== #
# GET /sales/clients                                                         #
# ======================================================================== #

@router.get("/clients")
def get_clients(db: Session = Depends(get_db)):
    clients = db.query(Client).order_by(Client.nombre_completo.asc()).all()
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
def get_motorcycles(client_id: Optional[int] = None,
                    db: Session = Depends(get_db)):

    # STEP A — Find client's reserved motorcycle
    reserved_moto_id = None
    if client_id:
        reservation = (
            db.query(Reservation)
            .filter(
                Reservation.client_id == client_id,
                Reservation.status    == ReservationStatus.assigned,
            )
            .order_by(Reservation.created_at.asc())
            .first()
        )
        if reservation and reservation.motorcycle:
            moto = reservation.motorcycle
            if moto.status == MotorcycleStatus.in_stock_reserved:
                reserved_moto_id = moto.motorcycle_id

    # STEP B — Query available in_stock motorcycles
    available = (
        db.query(Motorcycle)
        .options(
            joinedload(Motorcycle.dealership),
            joinedload(Motorcycle.model),
        )
        .filter(Motorcycle.status == MotorcycleStatus.in_stock)
        .all()
    )

    if reserved_moto_id:
        reserved_moto = (
            db.query(Motorcycle)
            .options(
                joinedload(Motorcycle.dealership),
                joinedload(Motorcycle.model),
            )
            .filter(Motorcycle.motorcycle_id == reserved_moto_id)
            .first()
        )
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
def get_credit_institutions(db: Session = Depends(get_db)):
    institutions = (
        db.query(CreditInstitution)
        .order_by(CreditInstitution.name.asc())
        .all()
    )
    return [
        {
            "credit_institution_id": i.credit_institution_id,
            "name":                  i.name,
        }
        for i in institutions
    ]


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
def create_sale(body: SaleCreateBody, db: Session = Depends(get_db)):
    try:
        # 1. Validate client
        client = db.query(Client).filter(
            Client.client_id == body.client_id
        ).first()
        if not client:
            return {"success": False,
                    "message": f"Cliente con id {body.client_id} no encontrado."}

        # 2. Validate motorcycle is available
        moto = (
            db.query(Motorcycle)
            .options(
                joinedload(Motorcycle.dealership),
                joinedload(Motorcycle.model),
            )
            .filter(
                Motorcycle.motorcycle_id == body.motorcycle_id,
                Motorcycle.status.in_([
                    MotorcycleStatus.in_stock,
                    MotorcycleStatus.in_stock_reserved,
                ]),
            )
            .first()
        )
        if not moto:
            return {"success": False,
                    "message": "Esta motocicleta no está disponible."}

        # 3. Get dealership
        dealership = moto.dealership

        # 4. Generate contract number
        contract_number = generate_contract_number(
            db, dealership.dealership_id)

        # 5. Create Event row
        now = datetime.now(timezone.utc)
        event = Event(
            event_type   = EventName.sale_validation.value,
            initiated_by = HARDCODED_USER_ID,
            status       = EventStatus.in_progress,
            started_at   = now,
        )
        db.add(event)
        db.flush()

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
        db.flush()

        # 7. Generate documents
        generate_documents(contract, db)

        # 8. Mark motorcycle sold
        moto.status = MotorcycleStatus.sold
        db.flush()

        # 9. Complete event
        event.status             = EventStatus.complete
        event.completed_at       = now
        event.linked_entity_type = "CONTRACT"
        event.linked_entity_id   = contract.contract_id
        db.flush()

        # 10. Commit
        db.commit()

        return {
            "success":         True,
            "message":         f"Venta registrada. Contrato {contract_number}.",
            "contract_id":     contract.contract_id,
            "contract_number": contract_number,
            "has_solicitud":   body.sale_type == "credito",
        }

    except Exception as e:
        db.rollback()
        return {"success": False, "message": str(e)}


# ======================================================================== #
# GET /sales/{contract_id}/download/contrato                                #
# ======================================================================== #

@router.get("/{contract_id}/download/contrato")
def download_contrato(contract_id: int, db: Session = Depends(get_db)):
    contract = db.query(Contract).filter(
        Contract.contract_id == contract_id
    ).first()
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
def download_solicitud(contract_id: int, db: Session = Depends(get_db)):
    contract = db.query(Contract).filter(
        Contract.contract_id == contract_id
    ).first()
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
