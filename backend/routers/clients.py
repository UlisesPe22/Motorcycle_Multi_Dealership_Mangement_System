"""
routers/clients.py — FastAPI router for client data.

POST /clients/register  — full INE registration (both sides in one call)
GET  /clients           — list all registered clients
GET  /clients/{id}      — get one client with full detail
"""

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from config import STORAGE_ROOT, HARDCODED_USER_ID
from database import get_db
from models.client import Client
from models.unconfirmed_client import UnconfirmedClient
from models.event import EventName, SlotName
from models.submission import Submission
from services.pipeline_id_docs import handle_client_registration, run_phase2
from services.pipeline_utils import create_event, save_upload_to_disk
from services.token_service import get_unconfirmed_client_by_token
from services.email_service import send_client_activation_email
from services.confirmation_pages import (
    render_client_activated_page,
    render_token_expired_page,
)

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("/register")
async def register_client(
    front_file: UploadFile = File(...),
    back_file:  UploadFile = File(...),
    email: str = Form(...),
    phone: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Full INE client registration in a single call.
    Accepts both card sides, runs Phase 1 on each, then Phase 2.
    Returns client_id and event_id on success.
    """
    raw_dir = os.path.join(STORAGE_ROOT, "submissions", "raw")

    # Create event
    event = await create_event(db, EventName.client_registration.value, HARDCODED_USER_ID)

    # Create and save front submission
    front_sub = Submission(
        event_id    = event.event_id,
        slot_number = 1,
        slot_name   = SlotName.id_front,
    )
    db.add(front_sub)
    await db.flush()

    front_bytes = await front_file.read()
    front_sub.raw_file_path = save_upload_to_disk(
        front_sub.submission_id, front_bytes, raw_dir, front_file.filename or ""
    )
    await db.flush()

    # Phase 1 — front
    success_front, message_front = await handle_client_registration(db, front_sub, event)
    if not success_front:
        return {"success": False, "message": message_front}

    # Create and save back submission
    back_sub = Submission(
        event_id    = event.event_id,
        slot_number = 2,
        slot_name   = SlotName.id_back,
    )
    db.add(back_sub)
    await db.flush()

    back_bytes = await back_file.read()
    back_sub.raw_file_path = save_upload_to_disk(
        back_sub.submission_id, back_bytes, raw_dir, back_file.filename or ""
    )
    await db.flush()

    # Phase 1 — back
    success_back, message_back = await handle_client_registration(db, back_sub, event)
    if not success_back:
        return {"success": False, "message": message_back}

    clean_email = email.strip().lower()
    clean_phone = phone.strip()

    # Phase 2 — extraction + cross-validation + staging into unconfirmed_clients
    success_p2, message_p2 = await run_phase2(db, event, clean_email, clean_phone)
    if not success_p2:
        return {"success": False, "message": message_p2}

    # Fetch the staged client and send the activation email.
    result = await db.execute(
        select(UnconfirmedClient).where(UnconfirmedClient.event_id == event.event_id)
    )
    pending = result.scalar_one_or_none()
    if not pending:
        return {"success": False, "message": "Error al registrar datos del cliente."}

    activation_email_sent = True
    try:
        await send_client_activation_email(pending, pending.confirmation_token)
    except Exception as e:  # never fail the registration over an SMTP error
        activation_email_sent = False
        print(f"[email] activation email failed for pending_client {pending.pending_client_id}: {e}")

    return {
        "success":               True,
        "message":               message_p2,
        "client_id":             pending.pending_client_id,
        "event_id":              event.event_id,
        "activation_email_sent": activation_email_sent,
    }


@router.get("/activate", response_class=HTMLResponse)
async def activate_client(token: str, db: AsyncSession = Depends(get_db)):
    """
    Client clicks the activation link from their email. On success the staged
    record is copied into the real clients table and becomes usable. Idempotent:
    re-clicking an already-activated link shows the success page again.
    """
    pending = await get_unconfirmed_client_by_token(db, token)
    if not pending:
        return HTMLResponse(render_token_expired_page(), status_code=404)

    # Already activated — show success page idempotently.
    if pending.status == "confirmed":
        return HTMLResponse(render_client_activated_page(pending.nombre_completo))

    # Expired (flagged or lapsed).
    if pending.status == "expired" or pending.token_expires_at < datetime.now(timezone.utc):
        pending.status = "expired"
        await db.commit()
        return HTMLResponse(render_token_expired_page(), status_code=410)

    # Duplicate check against the real clients table (different session / race).
    dup = await db.execute(
        select(Client).where(
            (Client.curp == pending.curp) | (Client.email == pending.email)
        )
    )
    if dup.scalars().first():
        pending.status = "expired"
        await db.commit()
        return HTMLResponse(render_token_expired_page(), status_code=409)

    new_client = Client(
        nombre_completo     = pending.nombre_completo,
        curp                = pending.curp,
        clave_de_elector    = pending.clave_de_elector,
        fecha_nacimiento    = pending.fecha_nacimiento,
        domicilio           = pending.domicilio,
        email               = pending.email,
        phone               = pending.phone,
        front_submission_id = pending.front_submission_id,
        back_submission_id  = pending.back_submission_id,
        event_id            = pending.event_id,
        registered_by       = pending.registered_by,
        registered_at       = pending.registered_at,
    )
    db.add(new_client)
    pending.status = "confirmed"
    await db.commit()

    return HTMLResponse(render_client_activated_page(pending.nombre_completo))


@router.get("/")
async def list_clients(db: AsyncSession = Depends(get_db)):
    """Return all registered clients with their submission image paths."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.front_submission),
            selectinload(Client.back_submission),
        )
        .order_by(Client.registered_at.desc())
    )
    clients = result.scalars().all()
    return [
        {
            "client_id":          c.client_id,
            "nombre_completo":    c.nombre_completo,
            "curp":               c.curp,
            "clave_de_elector":   c.clave_de_elector,
            "fecha_nacimiento":   c.fecha_nacimiento,
            "domicilio":          c.domicilio,
            "registered_at":      c.registered_at.isoformat() if c.registered_at else None,
            "front_image_path":   c.front_submission.normalised_image_path,
            "back_image_path":    c.back_submission.normalised_image_path,
        }
        for c in clients
    ]


@router.get("/{client_id}")
async def get_client(client_id: int, db: AsyncSession = Depends(get_db)):
    """Return one client by ID."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.front_submission),
            selectinload(Client.back_submission),
        )
        .where(Client.client_id == client_id)
    )
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    return {
        "client_id":          c.client_id,
        "nombre_completo":    c.nombre_completo,
        "curp":               c.curp,
        "clave_de_elector":   c.clave_de_elector,
        "fecha_nacimiento":   c.fecha_nacimiento,
        "domicilio":          c.domicilio,
        "registered_at":      c.registered_at.isoformat() if c.registered_at else None,
        "front_image_path":   c.front_submission.normalised_image_path,
        "back_image_path":    c.back_submission.normalised_image_path,
    }


@router.get("/image/{client_id}/{side}")
async def get_client_image(client_id: int, side: str, db: AsyncSession = Depends(get_db)):
    """
    Serve the normalised card image for a client.
    side must be 'front' or 'back'.
    """
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.front_submission),
            selectinload(Client.back_submission),
        )
        .where(Client.client_id == client_id)
    )
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")

    if side == "front":
        path = c.front_submission.normalised_image_path
    elif side == "back":
        path = c.back_submission.normalised_image_path
    else:
        raise HTTPException(status_code=400, detail="side must be 'front' or 'back'")

    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Image file not found on disk")

    return FileResponse(path, media_type="image/jpeg")
