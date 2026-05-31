from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.event import EventName
from config import HARDCODED_USER_ID
from services.pipeline_utils import create_event as _create_event, create_submissions_for_event

router = APIRouter(prefix="/events", tags=["events"])


@router.post("/")
def create_event(event_type_name: EventName, db: Session = Depends(get_db)):
    """
    Create a new event of any standard type.
    Automatically creates one submission row per slot definition.
    Returns event_id and list of submission slots.
    """
    try:
        event_name = EventName(event_type_name)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de evento inválido: {event_type_name}"
        )

    event = _create_event(db, event_name.value, HARDCODED_USER_ID)
    submissions = create_submissions_for_event(db, event.event_id, event_name.value)
    db.commit()

    return {
        "event_id": event.event_id,
        "event_type": event_name.value,
        "submissions": [
            {
                "submission_id": s.submission_id,
                "slot_name": s.slot_name,
                "slot_number":   s.slot_number,
                "status":        s.status.value if s.status else None,
            }
            for s in submissions
        ]
    }
