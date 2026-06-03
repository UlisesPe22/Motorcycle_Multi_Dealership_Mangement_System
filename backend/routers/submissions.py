import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.submission import Submission
from services.main_pipeline import process_upload
from services.pipeline_utils import save_upload_to_disk

router = APIRouter(prefix="/submissions", tags=["submissions"])

STORAGE_ROOT = os.path.join(
    os.path.dirname(__file__), '..', '..', 'storage', 'submissions', 'raw'
)


@router.post("/{submission_id}/upload")
async def upload_document(
    submission_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Receive a file upload for a specific submission slot.
    Accepts images (INE scans) and PDFs (purchase orders, etc).
    Saves the file to storage/submissions/raw/ and triggers the pipeline.
    Returns pipeline result with success flag and message.
    """
    result = await db.execute(
        select(Submission).where(Submission.submission_id == submission_id)
    )
    submission = result.scalar_one_or_none()

    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    # Read file bytes and save to disk
    file_bytes = await file.read()
    submission.raw_file_path = save_upload_to_disk(
        submission_id, file_bytes, STORAGE_ROOT, file.filename or ""
    )
    await db.commit()

    # Run pipeline
    success, message = await process_upload(db, submission_id)

    result = await db.execute(
        select(Submission).where(Submission.submission_id == submission_id)
    )
    updated_submission = result.scalar_one_or_none()

    return {
        "success":       success,
        "message":       message,
        "submission_id": submission_id,
        "status":        updated_submission.status.value if updated_submission and updated_submission.status else None,
    }
