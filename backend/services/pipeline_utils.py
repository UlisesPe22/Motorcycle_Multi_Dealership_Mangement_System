"""
pipeline_utils.py — Shared utilities for all pipeline services.

Covers image processing, PDF text extraction, string validation,
AI logging, submission/event state transitions, and reusable pipeline
building blocks (reject_and_return, check_confidence, load_pdf_with_text,
validate_string_list, mark_complete).
"""

import io
import os
import cv2
import numpy as np
from PIL import Image
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

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


def cv2_to_pil(cv2_image: np.ndarray) -> Image.Image:
    """Convert OpenCV BGR numpy array to PIL Image."""
    rgb = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


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

    Args:
        raw_image_path: path to the original uploaded scan
        corners:        dict with top_left/top_right/bottom_right/bottom_left
                        in normalised 0-1000 coordinates
        output_path:    where to save the normalised image

    Returns:
        output_path on success

    Raises:
        ValueError if warp fails
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

def extract_clean_pdf_text(pdf_bytes: bytes) -> str:
    """
    Extracts all text from PDF bytes using pdfplumber.
    Strips all whitespace and uppercases for reliable string matching.
    Returns a single clean string — the ground truth from the document.
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
    Returns character-level edit distance between two equal-length strings.
    For strings of different length returns the absolute length difference.
    """
    if len(s1) != len(s2):
        return abs(len(s1) - len(s2))
    return sum(c1 != c2 for c1, c2 in zip(s1, s2))


def validate_and_correct_string(
    gemini_value: str,
    expected_length: int,
    remaining_text: str,
) -> tuple[Optional[str], str, str]:
    """
    Validates a string extracted by Gemini against the PDF ground truth.
    Attempts single-character auto-correction if exact match fails.
    Consumes matched string from pool to prevent false matches on subsequent calls.

    Returns:
        (corrected_value, status, updated_remaining_text)

        status values:
          "exact"      — Gemini was correct, no correction needed
          "corrected"  — single character error found and auto-corrected
          "ambiguous"  — multiple candidates at distance 1, cannot safely correct
          "not_found"  — no candidate within distance 1, string too corrupt
    """
    clean_value = gemini_value.replace(" ", "").upper()

    if clean_value in remaining_text:
        updated = remaining_text.replace(clean_value, "", 1)
        return clean_value, "exact", updated

    candidates = set()
    for i in range(len(remaining_text) - expected_length + 1):
        substring = remaining_text[i:i + expected_length]
        if _levenshtein(clean_value, substring) == 1:
            candidates.add(substring)

    if len(candidates) == 1:
        corrected = candidates.pop()
        updated = remaining_text.replace(corrected, "", 1)
        return corrected, "corrected", updated
    elif len(candidates) > 1:
        return None, "ambiguous", remaining_text
    else:
        return None, "not_found", remaining_text


# ======================================================================== #
# AI logging and submission/event state helpers                             #
# ======================================================================== #

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
# Reusable pipeline building blocks                                         #
# ======================================================================== #

def reject_and_return(
    db: Session,
    submission: Submission,
    event: Event,
    reason: str,
) -> tuple[bool, str]:
    """
    Calls reject_submission(), reject_event(), db.commit(),
    and returns (False, reason).
    Replaces the 4-line block that appears across pipelines.
    """
    reject_submission(db, submission, reason)
    reject_event(db, event, reason)
    db.commit()
    return False, reason


def check_confidence(
    db: Session,
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
    Returns (False, reason) if not.
    """
    log_ai(
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
        return reject_and_return(db, submission, event, reason)
    return True, ""


def load_pdf_with_text(
    db: Session,
    submission: Submission,
    event: Event,
    raw_path: str,
) -> tuple[Optional[bytes], Optional[str], Optional[tuple]]:
    """
    Opens PDF from disk, reads bytes, extracts clean pdfplumber text.
    Returns (pdf_bytes, clean_text, None) on success.
    Returns (None, None, (False, reason)) on failure — caller must return
    the third element immediately if it is not None.

    Example usage:
        pdf_bytes, clean_text, err = load_pdf_with_text(db, submission, event, raw_path)
        if err: return err
    """
    if not raw_path or not os.path.exists(raw_path):
        reason = "Archivo PDF no encontrado en disco."
        return None, None, reject_and_return(db, submission, event, reason)
    try:
        with open(raw_path, "rb") as f:
            pdf_bytes = f.read()
    except Exception as e:
        reason = f"Error al leer el archivo: {e}"
        return None, None, reject_and_return(db, submission, event, reason)
    try:
        clean_text = extract_clean_pdf_text(pdf_bytes)
    except Exception as e:
        reason = f"Error al extraer texto del PDF: {e}"
        return None, None, reject_and_return(db, submission, event, reason)
    return pdf_bytes, clean_text, None


def validate_string_list(
    db: Session,
    submission: Submission,
    event: Event,
    items: list[dict],
    field_key: str,
    field_label: str,
    expected_length: int,
    remaining_text: str,
) -> tuple[Optional[list[str]], Optional[str], Optional[tuple]]:
    """
    Validates and autocorrects a list of strings extracted by Gemini
    against the PDF ground truth text using validate_and_correct_string().
    Consumes matched values from the pool on each iteration.

    field_key   — the dict key to read from each item e.g. "serie", "motor", "modelo"
    field_label — Spanish label for error messages e.g. "serie", "motor", "código"

    Returns (corrected_list, updated_remaining_text, None) on success.
    Returns (None, None, (False, reason)) on any ambiguous or not_found result.

    Example usage:
        series, remaining_text, err = validate_string_list(...)
        if err: return err
    """
    corrected = []
    for i, item in enumerate(items):
        raw_value = item.get(field_key, "")
        corrected_value, status, remaining_text = validate_and_correct_string(
            gemini_value    = raw_value,
            expected_length = expected_length,
            remaining_text  = remaining_text,
        )
        if status == "ambiguous":
            reason = (
                f"Ambigüedad detectada en número de {field_label} "
                f"fila {i + 1}: '{raw_value}' coincide con múltiples "
                f"valores en el documento. Por favor vuelve a subir el PDF."
            )
            return None, None, reject_and_return(db, submission, event, reason)
        if status == "not_found":
            reason = (
                f"Número de {field_label} fila {i + 1}: '{raw_value}' "
                f"no encontrado en el documento. "
                f"Por favor verifica el PDF."
            )
            return None, None, reject_and_return(db, submission, event, reason)
        corrected.append(corrected_value)
    return corrected, remaining_text, None


def _auto_assign_reservations(
    db: Session,
    dealership_id: int,
    incoming_pool: list,
) -> list[dict]:
    """
    Tries to assign active reservations to a pool of newly-incoming motorcycles.
    Processes reservations oldest-first. For each reservation, filters pool by
    model then attempts color preferences in priority order (case-insensitive).
    On a match: sets moto.status=incoming_reserved, moto.reservation_id,
    reservation.status=assigned, flushes. Returns list of result dicts.
    """
    from models.reservation import Reservation, ReservationStatus
    from models.reservation_color import ReservationColor
    from models.motorcycle import MotorcycleStatus

    active_reservations = (
        db.query(Reservation)
        .filter(
            Reservation.dealership_id == dealership_id,
            Reservation.status        == ReservationStatus.active,
        )
        .order_by(Reservation.created_at.asc())
        .all()
    )

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
                "colors":         [rc.color.value for rc in reservation.colors],
                "result":         "NO_MODEL_MATCH",
                "moto_id":        None,
                "color":          None,
            })
            continue

        color_preferences = [rc.color.strip().lower() for rc in reservation.colors]
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
            db.flush()
            results.append({
                "reservation_id": reservation.reservation_id,
                "client":         client_name,
                "model":          model_name,
                "colors":         [rc.color.value for rc in reservation.colors],
                "result":         "ASSIGNED",
                "moto_id":        matched_moto.motorcycle_id,
                "color":          matched_color,
            })
        else:
            results.append({
                "reservation_id": reservation.reservation_id,
                "client":         client_name,
                "model":          model_name,
                "colors":         [rc.color.value for rc in reservation.colors],
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


def mark_complete(
    db: Session,
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
    submission.submitted_at  = datetime.now(timezone.utc)
    event.status             = EventStatus.complete
    event.completed_at       = datetime.now(timezone.utc)
    event.linked_entity_type = entity_type
    db.flush()
    event.linked_entity_id   = entity_id
    db.commit()
