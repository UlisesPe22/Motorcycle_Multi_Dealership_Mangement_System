import os
import json
from datetime import datetime, timezone
from typing import Optional

import google.generativeai as genai
from sqlalchemy.orm import Session

from config import MODEL_NAME, CONFIDENCE_THRESHOLD
from models.event import Event, EventType, EventName, EventStatus
from models.submission import Submission, SubmissionStatus
from models.ai_analysis_log import AIAnalysisLog

# ======================================================================== #
# Shared utilities                                                          #
# ======================================================================== #

def get_model():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not found in .env")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name=MODEL_NAME,
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.1,
        }
    )


def call_gemini_image(model, prompt: str, image_bytes: bytes) -> tuple[str, dict]:
    """
    Call Gemini with a prompt and image bytes (JPEG).
    Returns (raw_response_str, parsed_dict).
    Raises ValueError on malformed JSON.
    """
    image_part = {"mime_type": "image/jpeg", "data": image_bytes}
    response = model.generate_content([prompt, image_part])
    raw = response.text.strip()

    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])

    try:
        return raw, json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned invalid JSON: {e}\nRaw: {raw}")


def call_gemini_pdf(model, prompt: str, pdf_bytes: bytes) -> tuple[str, dict]:
    """
    Call Gemini with a prompt and PDF bytes.
    Returns (raw_response_str, parsed_dict).
    Raises ValueError on malformed JSON.
    """
    pdf_part = {"mime_type": "application/pdf", "data": pdf_bytes}
    response = model.generate_content([prompt, pdf_part])
    raw = response.text.strip()

    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])

    try:
        return raw, json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned invalid JSON: {e}\nRaw: {raw}")


def log_ai(
    db: Session,
    submission_id: int,
    step_name: str,
    raw_response: str,
    parsed_result: Optional[dict],
    confidence: Optional[float],
    success: bool,
):
    """Write one row to ai_analysis_log."""
    log = AIAnalysisLog(
        submission_id=submission_id,
        step_name=step_name,
        model_version=MODEL_NAME,
        raw_response=raw_response,
        parsed_result=parsed_result,
        confidence=confidence,
        success=success,
    )
    db.add(log)
    db.flush()
    return log


def reject_submission(db: Session, submission: Submission, reason: str):
    submission.status = SubmissionStatus.rejected
    submission.rejection_reason = reason
    db.flush()


def reject_event(db: Session, event: Event, reason: str):
    event.status = EventStatus.rejected
    event.completed_at = datetime.now(timezone.utc)
    db.flush()


# ======================================================================== #
# Main entry point — routes to correct pipeline by event type              #
# ======================================================================== #

def process_upload(db: Session, submission_id: int) -> tuple[bool, str]:
    """
    Called by the FastAPI router after a file is saved to disk.
    Determines event type and routes to the correct pipeline.
    Returns (success: bool, message: str)
    """
    submission = db.query(Submission).filter(
        Submission.submission_id == submission_id
    ).first()

    if not submission:
        return False, "Submission no encontrada."

    event = db.query(Event).filter(
        Event.event_id == submission.event_id
    ).first()

    event_type = db.query(EventType).filter(
        EventType.event_type_id == event.event_type_id
    ).first()

    if event_type.name == EventName.client_registration:
        from services.pipeline_id_docs import handle_client_registration
        return handle_client_registration(db, submission, event)

    elif event_type.name == EventName.purchase_order:
        from services.pipeline_purchase import handle_purchase_order
        return handle_purchase_order(db, submission, event)
    elif event_type.name == EventName.order_confirmation:
        from services.pipeline_order_confirmation import handle_order_confirmation
        return handle_order_confirmation(db, submission, event)
    elif event_type.name == EventName.delivery_confirmation:
        from services.pipeline_delivery import handle_delivery_confirmation
    # declared_count and dealership_id come from the submission metadata
    # these will be passed via a dedicated endpoint — placeholder for now
        return False, "Pipeline de entrega requiere endpoint dedicado."
    else:
        return False, f"No hay pipeline implementado para {event_type.name.value}"