from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from database import get_db
from models.client import Client
from models.reservation import Reservation, ReservationStatus
from models.sale import Sale, SaleStatus

router = APIRouter(prefix="/inventory-management", tags=["inventory_management"])


# ======================================================================== #
# Request schemas                                                            #
# ======================================================================== #

class CancelActivityRequest(BaseModel):
    sale_id:        Optional[int] = None
    reservation_id: Optional[int] = None
    reason:         str


class RejectMotoRequest(BaseModel):
    motorcycle_id: int
    reason:        str


class TransferClientRequest(BaseModel):
    from_client_id: int
    to_client_id:   int
    sale_id:        Optional[int] = None
    reservation_id: Optional[int] = None
    reason:         str


# ======================================================================== #
# GET /inventory-management/clients-with-activity                            #
# ======================================================================== #

@router.get("/clients-with-activity")
async def clients_with_activity(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Client)
        .where(
            or_(
                Client.client_id.in_(
                    select(Sale.client_id).where(Sale.status.in_(["open", "verified"]))
                ),
                Client.client_id.in_(
                    select(Reservation.client_id).where(
                        Reservation.status.in_([ReservationStatus.active, ReservationStatus.assigned])
                    )
                ),
            )
        )
        .order_by(Client.nombre_completo.asc())
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
# GET /inventory-management/client-activity/{client_id}                     #
# ======================================================================== #

@router.get("/client-activity/{client_id}")
async def client_activity(client_id: int, db: AsyncSession = Depends(get_db)):
    from services.pipeline_inventory_management import get_client_activity
    return await get_client_activity(db, client_id)


# ======================================================================== #
# GET /inventory-management/clients-with-sales                               #
# ======================================================================== #

@router.get("/clients-with-sales")
async def clients_with_sales(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Client)
        .where(
            Client.client_id.in_(
                select(Sale.client_id).distinct()
            )
        )
        .order_by(Client.nombre_completo.asc())
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
# GET /inventory-management/moto-by-identifier                               #
# ======================================================================== #

@router.get("/moto-by-identifier")
async def moto_by_identifier(
    motor: Optional[str] = Query(default=None),
    serie: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not motor and not serie:
        raise HTTPException(status_code=400, detail="Se requiere motor o serie.")
    from services.pipeline_inventory_management import get_moto_by_identifier
    return await get_moto_by_identifier(db, motor, serie)


# ======================================================================== #
# POST /inventory-management/cancel-activity                                 #
# ======================================================================== #

@router.post("/cancel-activity")
async def cancel_activity(body: CancelActivityRequest, db: AsyncSession = Depends(get_db)):
    from services.pipeline_inventory_management import handle_cancel_activity
    return await handle_cancel_activity(db, body)


# ======================================================================== #
# POST /inventory-management/reject-moto                                     #
# ======================================================================== #

@router.post("/reject-moto")
async def reject_moto(body: RejectMotoRequest, db: AsyncSession = Depends(get_db)):
    from services.pipeline_inventory_management import handle_reject_moto
    return await handle_reject_moto(db, body)


# ======================================================================== #
# POST /inventory-management/transfer-client                                 #
# ======================================================================== #

@router.post("/transfer-client")
async def transfer_client(body: TransferClientRequest, db: AsyncSession = Depends(get_db)):
    from services.pipeline_inventory_management import handle_transfer_client
    return await handle_transfer_client(db, body)
