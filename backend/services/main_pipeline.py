import json
from typing import Optional

from google.genai import types
from sqlalchemy.orm import Session

from config import MODEL_NAME

from models.event import Event, EventName
from models.submission import Submission

from services.gemini_client import get_model
from services.pipeline_utils import log_ai, reject_submission, reject_event

# ======================================================================== #
# Re-export shared helpers so existing imports from main_pipeline work      #
# ======================================================================== #
# (pipeline_id_docs, pipeline_purchase, pipeline_order_confirmation, and
#  pipeline_delivery all import these names from services.main_pipeline)
__all__ = [
    "get_model",
    "call_gemini_image",
    "call_gemini_pdf",
    "call_gemini_text",
    "log_ai",
    "reject_submission",
    "reject_event",
]


# ======================================================================== #
# Gemini call wrappers                                                      #
# ======================================================================== #

def call_gemini_image(model, prompt: str, image_bytes: bytes) -> tuple[str, dict]:
    """
    Call Gemini with a prompt and image bytes (JPEG).
    Returns (raw_response_str, parsed_dict).
    Raises ValueError on malformed JSON.
    """
    part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
    response = model.models.generate_content(
        model=MODEL_NAME,
        contents=[prompt, part],
        config={"response_mime_type": "application/json", "temperature": 0.1},
    )

    usage = response.usage_metadata
    print(
        f"[GEMINI TOKENS] input={usage.prompt_token_count} | "
        f"output={usage.candidates_token_count} | "
        f"total={usage.total_token_count}"
    )

    raw = response.text.strip()

    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])

    try:
        return raw, json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned invalid JSON: {e}\nRaw: {raw}")


def call_gemini_text(model, prompt: str, text: str) -> tuple[str, dict]:
    """
    Call Gemini with a prompt and plain text extracted from a PDF.
    Returns (raw_response_str, parsed_dict).
    Raises ValueError on malformed JSON.
    """
    response = model.models.generate_content(
        model=MODEL_NAME,
        contents=[prompt, text],
        config={"response_mime_type": "application/json", "temperature": 0.1},
    )

    usage = response.usage_metadata
    print(
        f"[GEMINI TOKENS] input={usage.prompt_token_count} | "
        f"output={usage.candidates_token_count} | "
        f"total={usage.total_token_count}"
    )

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
    part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    response = model.models.generate_content(
        model=MODEL_NAME,
        contents=[prompt, part],
        config={"response_mime_type": "application/json", "temperature": 0.1},
    )

    usage = response.usage_metadata
    print(
        f"[GEMINI TOKENS] input={usage.prompt_token_count} | "
        f"output={usage.candidates_token_count} | "
        f"total={usage.total_token_count}"
    )

    raw = response.text.strip()

    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])

    try:
        return raw, json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned invalid JSON: {e}\nRaw: {raw}")


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

    if event.event_type == EventName.client_registration.value:
        from services.pipeline_id_docs import handle_client_registration
        return handle_client_registration(db, submission, event)

    elif event.event_type == EventName.purchase_order.value:
        from services.pipeline_purchase import handle_purchase_order
        return handle_purchase_order(db, submission, event)

    elif event.event_type == EventName.order_confirmation.value:
        from services.pipeline_order_confirmation import handle_order_confirmation
        return handle_order_confirmation(db, submission, event)

    elif event.event_type == EventName.delivery_confirmation.value:
        from services.pipeline_delivery import handle_delivery_confirmation
        # declared_count and dealership_id come from the submission metadata
        # these will be passed via a dedicated endpoint — placeholder for now
        return False, "Pipeline de entrega requiere endpoint dedicado."

    else:
        return False, f"No hay pipeline implementado para {event.event_type}"
