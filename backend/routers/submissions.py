import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

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
    db: Session = Depends(get_db),
):
    """
    Receive a file upload for a specific submission slot.
    Accepts images (INE scans) and PDFs (purchase orders, etc).
    Saves the file to storage/submissions/raw/ and triggers the pipeline.
    Returns pipeline result with success flag and message.
    """
    submission = db.query(Submission).filter(
        Submission.submission_id == submission_id
    ).first()

    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    # Save raw file to disk
    submission.raw_file_path = save_upload_to_disk(
        submission_id, file, STORAGE_ROOT, file.filename or ""
    )
    db.commit()

    # Run pipeline
    success, message = process_upload(db, submission_id)

    return {
        "success":       success,
        "message":       message,
        "submission_id": submission_id,
        "status":        db.query(Submission).filter(
                             Submission.submission_id == submission_id
                         ).first().status.value,
    }