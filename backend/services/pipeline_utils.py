"""
pipeline_utils.py — Shared utilities for all pipeline services.

Covers image processing, PDF text extraction, string validation,
AI logging, submission/event state transitions, and reusable pipeline
building blocks (reject_and_return, check_confidence, mark_complete).
"""

import io
import os
import re
import cv2
import numpy as np
from PIL import Image
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from config import MODEL_NAME, CONFIDENCE_THRESHOLD
from models.event import Event, EventStatus
from models.submission import Submission, SubmissionStatus
from models.ai_analysis_log import AIAnalysisLog

# ======================================================================== #
# Image processing                                                          #
# ======================================================================== #

CANONICAL_WIDTH  = 1012
CANONICAL_HEIGHT = 638


def pil_to_cv2(pil_image: Image.Image) -> np.ndarray:
    """Convert PIL Image to OpenCV BGR numpy array."""
    rgb = np.array(pil_image.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def load_image_as_pil(path: str) -> Image.Image:
    """
    Load image from disk and force convert to standard RGB.
    Handles MPO, CMYK, palette and other exotic formats.
    """
    img = Image.open(path)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def pil_to_jpeg_bytes(image: Image.Image) -> bytes:
    """
    Re-encode PIL image to standard JPEG bytes.
    Used when sending images to Gemini to avoid MPO/format errors.
    """
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG")
    buffer.seek(0)
    return buffer.read()


def normalise_corners(corners: dict, image_width: int, image_height: int) -> np.ndarray:
    """
    Convert Gemini's normalised 0-1000 corners to actual pixel coordinates.

    Gemini returns corners in a 0-1000 scale regardless of image resolution.
    We scale back to the actual image dimensions before warping.

    Returns numpy array of shape (4, 2) float32 in order:
        top_left, top_right, bottom_right, bottom_left
    """
    scale_x = image_width  / 1000.0
    scale_y = image_height / 1000.0

    tl = corners["top_left"]
    tr = corners["top_right"]
    br = corners["bottom_right"]
    bl = corners["bottom_left"]

    return np.array([
        [tl[0] * scale_x, tl[1] * scale_y],
        [tr[0] * scale_x, tr[1] * scale_y],
        [br[0] * scale_x, br[1] * scale_y],
        [bl[0] * scale_x, bl[1] * scale_y],
    ], dtype=np.float32)


def warp_and_save(
    raw_image_path: str,
    corners: dict,
    output_path: str,
) -> str:
    """
    Load raw image, apply perspective warp using Gemini corners,
    resize to canonical 1012x638, save to output_path.
    """
    pil_img = load_image_as_pil(raw_image_path)
    cv2_img = pil_to_cv2(pil_img)
    h, w = cv2_img.shape[:2]

    src_pts = normalise_corners(corners, w, h)

    dst_pts = np.array([
        [0,                   0                  ],
        [CANONICAL_WIDTH - 1, 0                  ],
        [CANONICAL_WIDTH - 1, CANONICAL_HEIGHT - 1],
        [0,                   CANONICAL_HEIGHT - 1],
    ], dtype=np.float32)

    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    warped = cv2.warpPerspective(cv2_img, M, (CANONICAL_WIDTH, CANONICAL_HEIGHT))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cv2.imwrite(output_path, warped)

    return output_path


# ======================================================================== #
# PDF text extraction and string validation                                 #
# ======================================================================== #

def extract_raw_pdf_text(pdf_bytes: bytes) -> str:
    """
    Extracts all text from PDF bytes using pdfplumber, preserving spaces
    and line breaks so Gemini can read the document as structured text.
    """
    import pdfplumber

    pages = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n".join(pages)


def extract_clean_pdf_text(pdf_bytes: bytes) -> str:
    """
    Extracts all text from PDF bytes using pdfplumber.
    Strips all whitespace and uppercases for reliable string matching.
    """
    import pdfplumber

    full_text = ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text

    return full_text.replace(" ", "").replace("\n", "").replace("\r", "").upper()


def _levenshtein(s1: str, s2: str) -> int:
    """
    Full Levenshtein distance — handles strings of unequal length.
    For equal-length strings this reduces to Hamming distance.
    """
    if s1 == s2:
        return 0
    if len(s1) == 0:
        return len(s2)
    if len(s2) == 0:
        return len(s1)
    if abs(len(s1) - len(s2)) > 2:
        return 999
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(
                prev[j + 1] + 1,
                curr[j] + 1,
                prev[j] + (0 if c1 == c2 else 1)
            ))
        prev = curr
    return prev[-1]


# ======================================================================== #
# Structural regex validators                                               #
# ======================================================================== #

def is_valid_modelo_code(code: str) -> bool:
    cleaned = code.strip().upper()
    return (
        len(cleaned) == 12
        and bool(re.match(r'^[A-Z0-9\-]{8}[0-9]{2}DI$', cleaned))
    )


def is_valid_cantidad(cantidad) -> bool:
    return isinstance(cantidad, int) and 1 <= cantidad <= 99


def is_valid_serie(serie: str) -> bool:
    return bool(re.match(r'^[A-Z0-9]{17}$', serie.strip().upper()))


def is_valid_motor(motor: str) -> bool:
    return bool(re.match(r'^[A-Z0-9]{11}$', motor.strip().upper()))


# ======================================================================== #
# AI logging and submission/event state helpers                             #
# ======================================================================== #

async def log_ai(
    db: AsyncSession,
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
    await db.flush()
    return log


async def reject_submission(db: AsyncSession, submission: Submission, reason: str):
    submission.status = SubmissionStatus.rejected
    submission.rejection_reason = reason
    await db.flush()


async def reject_event(db: AsyncSession, event: Event, reason: str):
    event.status = EventStatus.rejected
    event.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.flush()


# ======================================================================== #
# Reusable pipeline building blocks                                         #
# ======================================================================== #

async def reject_and_return(
    db: AsyncSession,
    submission: Submission,
    event: Event,
    reason: str,
) -> tuple[bool, str]:
    """
    Calls reject_submission(), reject_event(), db.commit(),
    and returns (False, reason).
    """
    await reject_submission(db, submission, reason)
    await reject_event(db, event, reason)
    await db.commit()
    return False, reason


async def check_confidence(
    db: AsyncSession,
    submission: Submission,
    event: Event,
    confidence: Optional[float],
    step_name: str,
    raw_response: str,
    parsed_result: Optional[dict],
) -> tuple[bool, str]:
    """
    Logs the AI call result and checks confidence against CONFIDENCE_THRESHOLD.
    If confidence is None or below threshold, calls reject_and_return.
    Returns (True, "") if confidence is acceptable.
    """
    await log_ai(
        db,
        submission.submission_id,
        step_name,
        raw_response,
        parsed_result,
        confidence,
        confidence is not None and confidence >= CONFIDENCE_THRESHOLD,
    )
    if confidence is None or confidence < CONFIDENCE_THRESHOLD:
        reason = (
            f"Confianza insuficiente ({confidence}). "
            f"Por favor sube un archivo más claro."
        )
        return await reject_and_return(db, submission, event, reason)
    return True, ""


async def _auto_assign_reservations(
    db: AsyncSession,
    dealership_id: int,
    incoming_pool: list,
) -> list[dict]:
    """
    Tries to assign active reservations to a pool of newly-incoming motorcycles.
    Processes reservations oldest-first. For each reservation, filters pool by
    model then attempts color preferences in priority order (case-insensitive).
    """
    from models.reservation import Reservation, ReservationStatus
    from models.reservation_color import ReservationColor
    from models.motorcycle import MotorcycleStatus

    result = await db.execute(
        select(Reservation)
        .options(
            selectinload(Reservation.client),
            selectinload(Reservation.colors).selectinload(ReservationColor.color),
            selectinload(Reservation.model),
        )
        .where(
            Reservation.dealership_id == dealership_id,
            Reservation.status == ReservationStatus.active,
        )
        .order_by(Reservation.created_at.asc())
    )
    active_reservations = result.scalars().all()

    assigned_moto_ids = set()
    results = []

    for reservation in active_reservations:
        model_pool = [
            m for m in incoming_pool
            if m.model_id == reservation.model_id
            and m.motorcycle_id not in assigned_moto_ids
        ]

        if not model_pool:
            client_name = reservation.client.nombre_completo if reservation.client else "?"
            results.append({
                "reservation_id": reservation.reservation_id,
                "client":         client_name,
                "model":          reservation.model.canonical_name if reservation.model else "?",
                "colors":         [rc.color.name for rc in reservation.colors],
                "result":         "NO_MODEL_MATCH",
                "moto_id":        None,
                "color":          None,
            })
            continue

        color_preferences = [rc.color.name.lower() for rc in reservation.colors]
        matched_moto = None
        matched_color = None

        for preferred_color in color_preferences:
            for moto in model_pool:
                if moto.color and moto.color.lower() == preferred_color:
                    matched_moto  = moto
                    matched_color = moto.color
                    break
            if matched_moto:
                break

        client_name = reservation.client.nombre_completo if reservation.client else "?"
        model_name  = reservation.model.canonical_name  if reservation.model  else "?"

        if matched_moto:
            matched_moto.status         = MotorcycleStatus.incoming_reserved
            matched_moto.reservation_id = reservation.reservation_id
            reservation.status          = ReservationStatus.assigned
            assigned_moto_ids.add(matched_moto.motorcycle_id)
            await db.flush()
            results.append({
                "reservation_id": reservation.reservation_id,
                "client":         client_name,
                "model":          model_name,
                "colors":         [rc.color.name for rc in reservation.colors],
                "result":         "ASSIGNED",
                "moto_id":        matched_moto.motorcycle_id,
                "color":          matched_color,
            })
        else:
            results.append({
                "reservation_id": reservation.reservation_id,
                "client":         client_name,
                "model":          model_name,
                "colors":         [rc.color.name for rc in reservation.colors],
                "result":         "NO_COLOR_MATCH",
                "moto_id":        None,
                "color":          None,
            })

    return results


def _print_reservation_assignment_results(results: list[dict]) -> None:
    if not results:
        return
    width = 72
    print(f"\n{'=' * width}")
    print(f"  RESERVATION AUTO-ASSIGNMENT RESULTS")
    print(f"{'=' * width}")
    for r in results:
        icon   = "* " if r["result"] == "ASSIGNED" else "x "
        colors = ", ".join(r["colors"]) if r["colors"] else "sin preferencia"
        print(f"\n  {icon}Reservacion #{r['reservation_id']} — {r['client']}")
        print(f"    Modelo:   {r['model']}")
        print(f"    Colores:  {colors}")
        if r["result"] == "ASSIGNED":
            print(f"    Resultado: ASIGNADA -> moto #{r['moto_id']} ({r['color']})")
        else:
            print(f"    Resultado: {r['result']}")
    print(f"\n{'=' * width}\n")


async def mark_complete(
    db: AsyncSession,
    submission: Submission,
    event: Event,
    entity_type: str,
    entity_id: int,
) -> None:
    """
    Marks submission and event as complete, sets linked entity,
    and calls db.commit().
    """
    submission.status        = SubmissionStatus.complete
    submission.submitted_at  = datetime.now(timezone.utc).replace(tzinfo=None)
    event.status             = EventStatus.complete
    event.completed_at       = datetime.now(timezone.utc).replace(tzinfo=None)
    event.linked_entity_type = entity_type
    await db.flush()
    event.linked_entity_id   = entity_id
    await db.commit()


# ======================================================================== #
# Router-level utilities                                                    #
# ======================================================================== #

async def create_event(db: AsyncSession, event_type: str, user_id: int) -> Event:
    """Creates and flushes a new Event row with status in_progress."""
    event = Event(
        event_type   = event_type,
        initiated_by = user_id,
        status       = EventStatus.in_progress,
        started_at   = datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(event)
    await db.flush()
    return event


async def create_submissions_for_event(
    db: AsyncSession,
    event_id: int,
    event_type_name: str,
) -> list:
    """
    Creates Submission rows for all slots defined in EVENT_SLOT_DEFINITIONS
    for the given event type. Returns list of created Submission objects.
    """
    from models.event import SlotName
    from config import EVENT_SLOT_DEFINITIONS

    slots = EVENT_SLOT_DEFINITIONS.get(event_type_name, [])
    submissions = []
    for slot_name_val, slot_number in slots:
        sub = Submission(
            event_id    = event_id,
            slot_number = slot_number,
            slot_name   = SlotName(slot_name_val),
        )
        db.add(sub)
        submissions.append(sub)
    await db.flush()
    return submissions


def save_upload_to_disk(
    submission_id: int,
    file_bytes: bytes,
    storage_root: str,
    original_filename: str,
) -> str:
    """
    Saves uploaded file bytes to disk under storage_root/sub_<id><ext>.
    Creates the directory if needed. Returns the full path.
    Callers must pass already-read bytes (use await file.read() first).
    """
    os.makedirs(storage_root, exist_ok=True)
    ext      = os.path.splitext(original_filename)[-1].lower() or ".jpg"
    raw_path = os.path.join(storage_root, f"sub_{submission_id}{ext}")
    with open(raw_path, "wb") as f:
        f.write(file_bytes)
    return raw_path
