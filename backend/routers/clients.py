"""
routers/clients.py — FastAPI router for client data.

POST /clients/register  — full INE registration (both sides in one call)
GET  /clients           — list all registered clients
GET  /clients/{id}      — get one client with full detail
"""

import os
import shutil
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from config import STORAGE_ROOT
from database import get_db
from models.client import Client
from models.event import Event, EventName, EventStatus, SlotName
from models.submission import Submission
from services.pipeline_id_docs import handle_client_registration, run_phase2

router = APIRouter(prefix="/clients", tags=["clients"])

HARDCODED_USER_ID = 1


@router.post("/register")
async def register_client(
    front_file: UploadFile = File(...),
    back_file:  UploadFile = File(...),
    email: str = Form(...),
    phone: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Full INE client registration in a single call.
    Accepts both card sides, runs Phase 1 on each, then Phase 2.
    Returns client_id and event_id on success.
    """
    raw_dir = os.path.join(STORAGE_ROOT, "submissions", "raw")
    os.makedirs(raw_dir, exist_ok=True)

    # Create event
    event = Event(
        event_type   = EventName.client_registration.value,
        initiated_by = HARDCODED_USER_ID,
        status       = EventStatus.in_progress,
        started_at   = datetime.now(timezone.utc),
    )
    db.add(event)
    db.flush()

    # Create and save front submission
    front_sub = Submission(
        event_id    = event.event_id,
        slot_number = 1,
        slot_name   = SlotName.id_front,
    )
    db.add(front_sub)
    db.flush()

    front_ext  = os.path.splitext(front_file.filename or "")[-1].lower() or ".jpg"
    front_path = os.path.join(raw_dir, f"sub_{front_sub.submission_id}{front_ext}")
    with open(front_path, "wb") as f:
        shutil.copyfileobj(front_file.file, f)
    front_sub.raw_file_path = front_path
    db.flush()

    # Phase 1 — front
    success_front, message_front = handle_client_registration(db, front_sub, event)
    if not success_front:
        return {"success": False, "message": message_front}

    # Create and save back submission
    back_sub = Submission(
        event_id    = event.event_id,
        slot_number = 2,
        slot_name   = SlotName.id_back,
    )
    db.add(back_sub)
    db.flush()

    back_ext  = os.path.splitext(back_file.filename or "")[-1].lower() or ".jpg"
    back_path = os.path.join(raw_dir, f"sub_{back_sub.submission_id}{back_ext}")
    with open(back_path, "wb") as f:
        shutil.copyfileobj(back_file.file, f)
    back_sub.raw_file_path = back_path
    db.flush()

    # Phase 1 — back
    success_back, message_back = handle_client_registration(db, back_sub, event)
    if not success_back:
        return {"success": False, "message": message_back}

    # Phase 2 — extraction + cross-validation + client creation
    success_p2, message_p2 = run_phase2(db, event)
    if not success_p2:
        return {"success": False, "message": message_p2}

    # Attach contact data to the newly created client
    client = db.query(Client).filter(
        Client.event_id == event.event_id
    ).first()
    if client:
        client.email = email.strip().lower()
        client.phone = phone.strip()
        db.commit()
    else:
        return {"success": False, "message": "Error al guardar datos de contacto."}

    return {
        "success":   True,
        "message":   message_p2,
        "client_id": client.client_id,
        "event_id":  event.event_id,
    }


@router.get("/")
def list_clients(db: Session = Depends(get_db)):
    """Return all registered clients with their submission image paths."""
    clients = db.query(Client).order_by(Client.registered_at.desc()).all()
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
def get_client(client_id: int, db: Session = Depends(get_db)):
    """Return one client by ID."""
    c = db.query(Client).filter(Client.client_id == client_id).first()
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
def get_client_image(client_id: int, side: str, db: Session = Depends(get_db)):
    """
    Serve the normalised card image for a client.
    side must be 'front' or 'back'..
    """
    c = db.query(Client).filter(Client.client_id == client_id).first()
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