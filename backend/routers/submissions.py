import os
import shutil

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from database import get_db
from models.submission import Submission, SubmissionStatus
from services.main_pipeline import process_upload

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

    if submission.status not in (SubmissionStatus.pending, SubmissionStatus.rejected):
        raise HTTPException(
            status_code=400,
            detail=f"Submission is in status '{submission.status.value}' and cannot accept uploads"
        )

    # Save raw file to disk
    os.makedirs(STORAGE_ROOT, exist_ok=True)
    ext      = os.path.splitext(file.filename)[-1].lower() or ".jpg"
    raw_path = os.path.join(STORAGE_ROOT, f"sub_{submission_id}{ext}")

    with open(raw_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Update submission with file path and mark as processing
    submission.raw_file_path = raw_path
    submission.status        = SubmissionStatus.processing
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