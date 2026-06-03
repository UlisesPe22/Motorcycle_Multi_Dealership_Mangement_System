import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.dealership import Dealership
from models.event import EventName
from models.submission import Submission
from config import HARDCODED_USER_ID
from services.pipeline_utils import create_event, create_submissions_for_event, save_upload_to_disk

router = APIRouter(prefix="/delivery-confirmations", tags=["delivery_confirmations"])

STORAGE_ROOT = os.path.join(
    os.path.dirname(__file__), '..', '..', 'storage', 'submissions', 'raw'
)


# ======================================================================== #
# GET /delivery-confirmations/dealerships                                   #
# ======================================================================== #

@router.get("/dealerships")
async def get_dealerships(db: AsyncSession = Depends(get_db)):
    """Returns all dealerships for the Streamlit dropdown."""
    result = await db.execute(
        select(Dealership).order_by(Dealership.name)
    )
    dealerships = result.scalars().all()
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
    db:              AsyncSession = Depends(get_db),
):
    """
    Dedicated endpoint for delivery confirmation uploads.
    Accepts file + declared_count + dealership_id as form parameters.
    Creates event + submission, saves file, runs delivery pipeline.
    """

    # Validate dealership exists
    result = await db.execute(
        select(Dealership).where(Dealership.dealership_id == dealership_id)
    )
    dealership = result.scalar_one_or_none()

    if not dealership:
        raise HTTPException(
            status_code=404,
            detail=f"Dealership with id {dealership_id} not found."
        )

    # Create event and submission
    event = await create_event(db, EventName.delivery_confirmation.value, HARDCODED_USER_ID)
    submissions = await create_submissions_for_event(
        db, event.event_id, EventName.delivery_confirmation.value
    )
    submission = submissions[0]
    await db.commit()

    # Read file bytes and save to disk
    file_bytes = await file.read()
    submission.raw_file_path = save_upload_to_disk(
        submission.submission_id, file_bytes, STORAGE_ROOT, file.filename or ""
    )
    await db.commit()

    # Run delivery pipeline
    from services.pipeline_delivery import handle_delivery_confirmation

    success, message = await handle_delivery_confirmation(
        db             = db,
        submission     = submission,
        event          = event,
        declared_count = declared_count,
        dealership_id  = dealership_id,
    )

    result = await db.execute(
        select(Submission).where(Submission.submission_id == submission.submission_id)
    )
    updated_submission = result.scalar_one_or_none()

    return {
        "success":       success,
        "message":       message,
        "event_id":      event.event_id,
        "submission_id": submission.submission_id,
        "status":        updated_submission.status.value if updated_submission and updated_submission.status else None,
    }
