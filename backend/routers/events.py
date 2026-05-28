from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from database import get_db
from models.event import Event, EventName, EventStatus, SlotName
from models.submission import Submission
from config import EVENT_SLOT_DEFINITIONS

router = APIRouter(prefix="/events", tags=["events"])

HARDCODED_USER_ID = 1


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

    event = Event(
        event_type   = event_name.value,
        initiated_by = HARDCODED_USER_ID,
        status       = EventStatus.in_progress,
        started_at   = datetime.now(timezone.utc),
    )
    db.add(event)
    db.flush()

    submissions = []
    slots = EVENT_SLOT_DEFINITIONS.get(event_name.value, [])
    for slot_name_val, slot_number in slots:
        sub = Submission(
            event_id    = event.event_id,
            slot_number = slot_number,
            slot_name   = SlotName(slot_name_val),
        )
        db.add(sub)
        submissions.append(sub)

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
