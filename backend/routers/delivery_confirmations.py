import os
import shutil

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from database import get_db
from models.dealership  import Dealership
from models.event       import Event, EventType, EventName, EventStatus
from models.submission  import Submission, SubmissionStatus

router = APIRouter(prefix="/delivery-confirmations", tags=["delivery_confirmations"])

STORAGE_ROOT = os.path.join(
    os.path.dirname(__file__), '..', '..', 'storage', 'submissions', 'raw'
)

HARDCODED_USER_ID = 2


# ======================================================================== #
# GET /delivery-confirmations/dealerships                                   #
# ======================================================================== #

@router.get("/dealerships")
def get_dealerships(db: Session = Depends(get_db)):
    """
    Returns all dealerships for the Streamlit dropdown.
    """
    dealerships = db.query(Dealership).order_by(Dealership.name).all()
    return [
        {
            "dealership_id": d.dealership_id,
            "name":          d.name,
        }
        for d in dealerships
    ]


# ======================================================================== #
# POST /delivery-confirmations/upload                                       #
# ======================================================================== #

@router.post("/upload")
async def upload_delivery(
    file:            UploadFile = File(...),
    declared_count:  int        = Form(...),
    dealership_id:   int        = Form(...),
    db:              Session    = Depends(get_db),
):
    """
    Dedicated endpoint for delivery confirmation uploads.
    Accepts file + declared_count + dealership_id as form parameters.
    Creates event + submission, saves file, runs delivery pipeline.
    Returns pipeline result.
    """

    # ------------------------------------------------------------------ #
    # Validate dealership exists                                          #
    # ------------------------------------------------------------------ #
    dealership = db.query(Dealership).filter(
        Dealership.dealership_id == dealership_id
    ).first()

    if not dealership:
        raise HTTPException(
            status_code=404,
            detail=f"Dealership with id {dealership_id} not found."
        )

    # ------------------------------------------------------------------ #
    # Create event                                                        #
    # ------------------------------------------------------------------ #
    from datetime import datetime, timezone
    from models.event import EventSlotDefinition
    from models.submission import SubmissionStatus
    from models.event import EventStatus

    event_type = db.query(EventType).filter(
        EventType.name == EventName.delivery_confirmation
    ).first()

    if not event_type:
        raise HTTPException(
            status_code=500,
            detail="delivery_confirmation event type not found — run seed.py"
        )

    event = Event(
        event_type_id = event_type.event_type_id,
        initiated_by  = HARDCODED_USER_ID,
        status        = EventStatus.in_progress,
        started_at    = datetime.now(timezone.utc),
    )
    db.add(event)
    db.flush()

    # ------------------------------------------------------------------ #
    # Create submission                                                   #
    # ------------------------------------------------------------------ #
    slot_def = db.query(EventSlotDefinition).filter(
        EventSlotDefinition.event_type_id == event_type.event_type_id,
        EventSlotDefinition.slot_number   == 1,
    ).first()

    submission = Submission(
        event_id    = event.event_id,
        slot_number = slot_def.slot_number,
        slot_name   = slot_def.slot_name,
        status      = SubmissionStatus.pending,
    )
    db.add(submission)
    db.flush()
    db.commit()

    # ------------------------------------------------------------------ #
    # Save file to disk                                                   #
    # ------------------------------------------------------------------ #
    os.makedirs(STORAGE_ROOT, exist_ok=True)
    ext      = os.path.splitext(file.filename)[-1].lower() or ".jpg"
    raw_path = os.path.join(STORAGE_ROOT, f"sub_{submission.submission_id}{ext}")

    with open(raw_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    submission.raw_file_path = raw_path
    submission.status        = SubmissionStatus.processing
    db.commit()

    # ------------------------------------------------------------------ #
    # Run delivery pipeline                                               #
    # ------------------------------------------------------------------ #
    from services.pipeline_delivery import handle_delivery_confirmation

    success, message = handle_delivery_confirmation(
        db             = db,
        submission     = submission,
        event          = event,
        declared_count = declared_count,
        dealership_id  = dealership_id,
    )

    return {
        "success":       success,
        "message":       message,
        "event_id":      event.event_id,
        "submission_id": submission.submission_id,
        "status":        db.query(Submission).filter(
                             Submission.submission_id == submission.submission_id
                         ).first().status.value,
    }