from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from database import get_db
from models.event import Event, EventType, EventName, EventStatus, EventSlotDefinition
from models.submission import Submission, SubmissionStatus

router = APIRouter(prefix="/events", tags=["events"])

HARDCODED_USER_ID = 1


@router.post("/")
def create_event(event_type_name: EventName, db: Session = Depends(get_db)):
    """
    Create a new event of any standard type.
    Automatically creates one submission row per slot definition.
    Returns event_id and list of submission slots.
    """
    event_type = db.query(EventType).filter(
        EventType.name == event_type_name
    ).first()

    if not event_type:
        raise HTTPException(status_code=500, detail="event_type not found — run seed.py")

    event = Event(
        event_type_id=event_type.event_type_id,
        initiated_by=HARDCODED_USER_ID,
        status=EventStatus.in_progress,
        started_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.flush()

    submissions = []
    for slot_def in event_type.slot_definitions:
        sub = Submission(
            event_id=event.event_id,
            slot_number=slot_def.slot_number,
            slot_name=slot_def.slot_name,
            status=SubmissionStatus.pending,
        )
        db.add(sub)
        submissions.append(sub)

    db.commit()

    return {
        "event_id": event.event_id,
        "event_type": event_type_name.value,
        "submissions": [
            {
                "submission_id": s.submission_id,
                "slot_name":     s.slot_name.value,
                "slot_number":   s.slot_number,
                "status":        s.status.value,
            }
            for s in submissions
        ]
    }