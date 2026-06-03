import json
from typing import Optional

from google.genai import types
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import MODEL_NAME

from models.event import Event, EventName
from models.submission import Submission

from services.gemini_client import get_model
from services.pipeline_utils import log_ai

__all__ = [
    "get_model",
    "call_gemini_image",
    "call_gemini_pdf",
    "call_gemini_text",
    "log_ai",
]


# ======================================================================== #
# Gemini call wrappers — async                                              #
# ======================================================================== #

async def call_gemini_image(model, prompt: str, image_bytes: bytes) -> tuple[str, dict]:
    """
    Call Gemini with a prompt and image bytes (JPEG).
    Returns (raw_response_str, parsed_dict).
    Raises ValueError on malformed JSON.
    """
    part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
    response = await model.aio.models.generate_content(
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


async def call_gemini_text(model, prompt: str, text: str) -> tuple[str, dict]:
    """
    Call Gemini with a prompt and plain text extracted from a PDF.
    Returns (raw_response_str, parsed_dict).
    Raises ValueError on malformed JSON.
    """
    response = await model.aio.models.generate_content(
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


async def call_gemini_pdf(model, prompt: str, pdf_bytes: bytes) -> tuple[str, dict]:
    """
    Call Gemini with a prompt and PDF bytes.
    Returns (raw_response_str, parsed_dict).
    Raises ValueError on malformed JSON.
    """
    part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    response = await model.aio.models.generate_content(
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

async def process_upload(db: AsyncSession, submission_id: int) -> tuple[bool, str]:
    """
    Called by the FastAPI router after a file is saved to disk.
    Determines event type and routes to the correct pipeline.
    Returns (success: bool, message: str)
    """
    result = await db.execute(
        select(Submission).where(Submission.submission_id == submission_id)
    )
    submission = result.scalar_one_or_none()

    if not submission:
        return False, "Submission no encontrada."

    result = await db.execute(
        select(Event).where(Event.event_id == submission.event_id)
    )
    event = result.scalar_one_or_none()

    if event.event_type == EventName.client_registration.value:
        from services.pipeline_id_docs import handle_client_registration
        return await handle_client_registration(db, submission, event)

    elif event.event_type == EventName.purchase_order.value:
        from services.pipeline_purchase import handle_purchase_order
        return await handle_purchase_order(db, submission, event)

    elif event.event_type == EventName.order_confirmation.value:
        from services.pipeline_order_confirmation import handle_order_confirmation
        return await handle_order_confirmation(db, submission, event)

    elif event.event_type == EventName.delivery_confirmation.value:
        from services.pipeline_delivery import handle_delivery_confirmation
        return False, "Pipeline de entrega requiere endpoint dedicado."

    else:
        return False, f"No hay pipeline implementado para {event.event_type}"
