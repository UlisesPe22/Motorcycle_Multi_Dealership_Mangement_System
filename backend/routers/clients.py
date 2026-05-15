"""
routers/clients.py — FastAPI router for client data.

GET /clients        — list all registered clients
GET /clients/{id}   — get one client with full detail
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os

from database import get_db
from models.client import Client

router = APIRouter(prefix="/clients", tags=["clients"])


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
    side must be 'front' or 'back'.
    Used by Streamlit to display the card images.
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