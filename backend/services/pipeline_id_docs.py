"""
pipeline_id_docs.py — Client registration pipeline (INE document processing).

Phase 1: Identification — Gemini validates document and returns corners
Warp:    Image normalise — OpenCV perspective warp to 1012x638
Phase 2: Extraction — Gemini extracts all text fields
Cross-validation — Pure Python checks MRZ vs front data
Client creation — Writes the final Client record to DB
"""
import os
import re
from datetime import datetime, timezone
from typing import Optional

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from dotenv import load_dotenv
from config import CONFIDENCE_THRESHOLD, STORAGE_ROOT

from models.event       import Event, EventStatus
from models.submission  import Submission, SubmissionStatus
from models.ai_analysis_log import AIAnalysisLog
from models.client      import Client
from schemas.gemini_responses import (
    Phase1Response,
    Phase2FrontResponse,
    Phase2BackResponse,
)
from services.pipeline_utils import (
    warp_and_save,
    load_image_as_pil,
    pil_to_jpeg_bytes,
    log_ai,
    reject_submission,
    reject_event,
    reject_and_return,
)

from services.main_pipeline import (
    get_model,
    call_gemini_image,
)

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))


# ======================================================================== #
# Prompts                                                                   #
# ======================================================================== #

def _phase1_prompt(expected_side: str) -> str:
    side = "FRONT" if expected_side == "id_front" else "BACK"
    return f"""
You are a document validator for a Mexican motorcycle dealership.
Return ONLY a JSON object. No explanation, no markdown, no preamble.

I am expecting the {side} side of a Mexican INE (Credencial para Votar) voter ID card.

Tasks:
1. Confirm exactly ONE INE card is visible.
2. Confirm it is the {side} side.
3. Detect the 4 corners of the card in normalised coordinates (0-1000 scale).

Rules:
- If wrong side, both sides visible, or not an INE: set is_match to false.
- Corners order: top_left, top_right, bottom_right, bottom_left.
- confidence reflects certainty across ALL checks combined.
- user_message must be in Spanish, suitable to show to a dealership employee.

Return exactly:
{{
  "is_match": true or false,
  "detected_side": "front" or "back",
  "corners": {{
    "top_left":     [x, y],
    "top_right":    [x, y],
    "bottom_right": [x, y],
    "bottom_left":  [x, y]
  }},
  "confidence": 0.0 to 1.0,
  "user_message": "mensaje en español"
}}
"""


def _phase2_front_prompt(corners: dict) -> str:
    tl = corners["top_left"]
    tr = corners["top_right"]
    br = corners["bottom_right"]
    bl = corners["bottom_left"]
    return f"""
You are a document data extractor for a Mexican motorcycle dealership.
Return ONLY a JSON object. No explanation, no markdown, no preamble.

This is the FRONT of a Mexican INE.
Card corners in normalised coordinates (0-1000): TL:{tl} TR:{tr} BR:{br} BL:{bl}
Use these corners to focus extraction precisely on the card area.

Extract:
- nombre_completo: full name as printed
- curp: the CURP code (18 characters)
- clave_de_elector: the voter key code
- fecha_nacimiento: date of birth as printed
- domicilio: full address as printed
Rules:
- If a field is not visible return null.
- Do not invent values.
- Each field has its own confidence score.

Return exactly:
{{
  "fields": {{
    "nombre_completo":  {{"value": "...", "confidence": 0.0}},
    "curp":             {{"value": "...", "confidence": 0.0}},
    "clave_de_elector": {{"value": "...", "confidence": 0.0}},
    "fecha_nacimiento": {{"value": "...", "confidence": 0.0}},
    "domicilio":        {{"value": "...", "confidence": 0.0}}
  }},
  "overall_confidence": 0.0
}}
"""


def _phase2_back_prompt(corners: dict) -> str:
    tl = corners["top_left"]
    tr = corners["top_right"]
    br = corners["bottom_right"]
    bl = corners["bottom_left"]
    return f"""
You are a document data extractor for a Mexican motorcycle dealership.
Return ONLY a JSON object. No explanation, no markdown, no preamble.

This is the BACK of a Mexican INE version.
Card corners in normalised coordinates (0-1000): TL:{tl} TR:{tr} BR:{br} BL:{bl}
Use these corners to focus extraction precisely on the card area.

Extract:
- mrz_line_1: first MRZ line exactly as printed
- mrz_line_2: second MRZ line exactly as printed
- mrz_line_3: third MRZ line if present, otherwise null

Rules:
- Copy MRZ lines character by character, do not interpret or correct them.
- Each field has its own confidence score.

Return exactly:
{{
  "fields": {{
    "mrz_line_1":       {{"value": "...", "confidence": 0.0}},
    "mrz_line_2":       {{"value": "...", "confidence": 0.0}},
    "mrz_line_3":       {{"value": "...", "confidence": 0.0}}
  }},
  "overall_confidence": 0.0
}}
"""


# ======================================================================== #
# MRZ cross-validation                                                      #
# ======================================================================== #

def _validate_mrz_check_digit(mrz_line: str, start: int, length: int, check_pos: int) -> bool:
    char_values = {str(i): i for i in range(10)}
    char_values.update({chr(c): c - 55 for c in range(65, 91)})
    char_values["<"] = 0

    field   = mrz_line[start:start + length]
    check   = mrz_line[check_pos]
    weights = [7, 3, 1]

    total = 0
    for i, ch in enumerate(field):
        total += char_values.get(ch, 0) * weights[i % 3]

    return (total % 10) == int(check) if check.isdigit() else False


def _parse_mrz(mrz_line_2: str) -> dict:
    result = {}
    l2 = mrz_line_2.strip().upper().replace(" ", "<")

    if len(l2) >= 7:
        dob_raw = l2[0:6]
        if dob_raw.isdigit():
            result["mrz_dob"]    = dob_raw
            result["mrz_dob_yy"] = dob_raw[0:2]
            result["mrz_dob_mm"] = dob_raw[2:4]
            result["mrz_dob_dd"] = dob_raw[4:6]

    if len(l2) >= 8:
        sex = l2[7]
        if sex in ("M", "F"):
            result["mrz_sex"] = sex

    return result


def _cross_validate(front_fields: dict, back_fields: dict) -> tuple[bool, str]:
    mrz_line_2 = (back_fields.get("mrz_line_2") or {}).get("value") or ""

    if not mrz_line_2:
        return False, (
            "No se pudo leer la zona MRZ completa del reverso del documento. "
        )
    l2 = mrz_line_2.strip().upper().replace(" ", "<")

    if len(l2) != 30:
        return False, (
            f"La línea 2 del MRZ tiene {len(l2)} caracteres en lugar de 30. "
            "El documento puede estar dañado o ser inválido."
        )

    if not _validate_mrz_check_digit(l2, 0, 6, 6):
        return False, (
            "El dígito verificador de la fecha de nacimiento en el MRZ es inválido. "
            "El documento puede estar alterado o dañado."
        )

    parsed    = _parse_mrz(l2)
    fecha_nac = (front_fields.get("fecha_nacimiento") or {}).get("value") or ""
    curp      = (front_fields.get("curp") or {}).get("value") or ""

    mrz_dob = parsed.get("mrz_dob", "")
    if mrz_dob and fecha_nac:
        yy        = int(parsed.get("mrz_dob_yy", "0"))
        mm        = parsed.get("mrz_dob_mm", "")
        dd        = parsed.get("mrz_dob_dd", "")
        full_year = f"19{yy:02d}" if yy > 24 else f"20{yy:02d}"

        digits_front = re.sub(r"\D", "", fecha_nac)

        day_ok   = dd in digits_front
        month_ok = mm in digits_front
        year_ok  = full_year in digits_front

        if not (day_ok and month_ok and year_ok):
            return False, (
                f"La fecha de nacimiento del MRZ ({dd}/{mm}/{full_year}) "
                f"no coincide con la del frente ({fecha_nac}). "
                "El documento puede ser inválido o falsificado."
            )

    return True, "Validación cruzada exitosa."


# ======================================================================== #
# Main pipeline entry point                                                 #
# ======================================================================== #

async def run_phase1(db: AsyncSession, submission: Submission, event: Event) -> tuple[bool, str]:
    """
    Phase 1 — Identification.
    Validates the document, detects version and corners.
    Saves normalised image to disk. Updates submission status.
    """
    model = get_model()

    raw_path = submission.raw_file_path
    if not raw_path or not os.path.exists(raw_path):
        return await reject_and_return(db, submission, event, "Archivo de imagen no encontrado.")

    pil_img   = load_image_as_pil(raw_path)
    img_bytes = pil_to_jpeg_bytes(pil_img)
    prompt    = _phase1_prompt(submission.slot_name.value if hasattr(submission.slot_name, 'value') else submission.slot_name)

    try:
        raw_response, parsed_dict = await call_gemini_image(model, prompt, img_bytes)
    except ValueError as e:
        reason = f"Error al procesar la respuesta de IA: {e}"
        await log_ai(db, submission.submission_id, "identification", str(e), None, None, False)
        return await reject_and_return(db, submission, event, reason)

    try:
        phase1 = Phase1Response(**parsed_dict)
    except ValidationError as e:
        reason = f"Respuesta de IA con formato inválido: {e}"
        await log_ai(db, submission.submission_id, "identification", raw_response, parsed_dict, None, False)
        return await reject_and_return(db, submission, event, reason)

    await log_ai(
        db, submission.submission_id, "identification",
        raw_response, parsed_dict,
        phase1.confidence, phase1.is_match and phase1.confidence >= CONFIDENCE_THRESHOLD
    )

    if not phase1.is_match:
        return await reject_and_return(db, submission, event, phase1.user_message)

    if phase1.confidence < CONFIDENCE_THRESHOLD:
        reason = (
            f"Confianza insuficiente ({phase1.confidence:.0%}). "
            f"{phase1.user_message}"
        )
        return await reject_and_return(db, submission, event, reason)

    normalised_path = os.path.join(
        STORAGE_ROOT, "submissions", "normalised",
        f"norm_{submission.submission_id}.jpg"
    )
    try:
        warp_and_save(raw_path, phase1.corners.model_dump(), normalised_path)
    except Exception as e:
        reason = f"Error al normalizar la imagen: {e}"
        return await reject_and_return(db, submission, event, reason)

    submission.normalised_image_path  = normalised_path
    submission.gemini_detected_side   = phase1.detected_side
    submission.submitted_at           = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.flush()

    return True, phase1.user_message


async def run_phase2(db: AsyncSession, event: Event) -> tuple[bool, str]:
    """
    Phase 2 — Data extraction + cross-validation + client creation.
    """
    result = await db.execute(
        select(Submission).where(Submission.event_id == event.event_id)
    )
    submissions = result.scalars().all()

    model = get_model()

    front_sub = next(
        s for s in submissions
        if (s.slot_name.value if hasattr(s.slot_name, 'value') else s.slot_name) == "id_front"
    )
    back_sub = next(
        s for s in submissions
        if (s.slot_name.value if hasattr(s.slot_name, 'value') else s.slot_name) == "id_back"
    )

    # ------------------------------------------------------------------ #
    # Extract front                                                        #
    # ------------------------------------------------------------------ #
    front_pil   = load_image_as_pil(front_sub.raw_file_path)
    front_bytes = pil_to_jpeg_bytes(front_pil)

    result = await db.execute(
        select(AIAnalysisLog).where(
            AIAnalysisLog.submission_id == front_sub.submission_id,
            AIAnalysisLog.step_name == "identification",
            AIAnalysisLog.success == True,
        )
    )
    front_log = result.scalar_one_or_none()
    front_corners = front_log.parsed_result["corners"] if front_log else None

    front_prompt = _phase2_front_prompt(front_corners)

    try:
        front_raw, front_dict = await call_gemini_image(model, front_prompt, front_bytes)
    except ValueError as e:
        reason = f"Error al extraer datos del frente: {e}"
        return await reject_and_return(db, front_sub, event, reason)

    try:
        front_result = Phase2FrontResponse(**front_dict)
    except ValidationError as e:
        reason = f"Respuesta de IA inválida en extracción del frente: {e}"
        await log_ai(db, front_sub.submission_id, "extraction", front_raw, front_dict, None, False)
        return await reject_and_return(db, front_sub, event, reason)

    await log_ai(
        db, front_sub.submission_id, "extraction",
        front_raw, front_dict,
        front_result.overall_confidence,
        front_result.overall_confidence >= CONFIDENCE_THRESHOLD
    )

    if front_result.overall_confidence < CONFIDENCE_THRESHOLD:
        reason = (
            f"Confianza insuficiente en la extracción del frente "
            f"({front_result.overall_confidence:.0%}). "
            "Por favor, use una imagen más clara."
        )
        return await reject_and_return(db, front_sub, event, reason)

    # ------------------------------------------------------------------ #
    # Extract back                                                         #
    # ------------------------------------------------------------------ #
    back_pil   = load_image_as_pil(back_sub.raw_file_path)
    back_bytes = pil_to_jpeg_bytes(back_pil)

    result = await db.execute(
        select(AIAnalysisLog).where(
            AIAnalysisLog.submission_id == back_sub.submission_id,
            AIAnalysisLog.step_name == "identification",
            AIAnalysisLog.success == True,
        )
    )
    back_log = result.scalar_one_or_none()
    back_corners = back_log.parsed_result["corners"] if back_log else None

    back_prompt = _phase2_back_prompt(back_corners)

    try:
        back_raw, back_dict = await call_gemini_image(model, back_prompt, back_bytes)
    except ValueError as e:
        reason = f"Error al extraer datos del reverso: {e}"
        return await reject_and_return(db, back_sub, event, reason)

    try:
        back_result = Phase2BackResponse(**back_dict)
    except ValidationError as e:
        reason = f"Respuesta de IA inválida en extracción del reverso: {e}"
        await log_ai(db, back_sub.submission_id, "extraction", back_raw, back_dict, None, False)
        return await reject_and_return(db, back_sub, event, reason)

    await log_ai(
        db, back_sub.submission_id, "extraction",
        back_raw, back_dict,
        back_result.overall_confidence,
        back_result.overall_confidence >= CONFIDENCE_THRESHOLD
    )

    if back_result.overall_confidence < CONFIDENCE_THRESHOLD:
        reason = (
            f"Confianza insuficiente en la extracción del reverso "
            f"({back_result.overall_confidence:.0%}). "
            "Por favor, use una imagen más clara."
        )
        return await reject_and_return(db, back_sub, event, reason)

    # ------------------------------------------------------------------ #
    # Cross-validation                                                     #
    # ------------------------------------------------------------------ #
    front_fields = front_result.fields.model_dump()
    back_fields  = back_result.fields.model_dump()

    passed, cv_message = _cross_validate(front_fields, back_fields)
    if not passed:
        for s in submissions:
            await reject_submission(db, s, cv_message)
        await reject_event(db, event, cv_message)
        return False, cv_message

    # ------------------------------------------------------------------ #
    # Create client record                                                 #
    # ------------------------------------------------------------------ #
    def field_val(fields: dict, key: str) -> Optional[str]:
        f = fields.get(key)
        return f["value"] if f and f.get("value") else None

    existing_curp = field_val(front_fields, "curp")
    result = await db.execute(
        select(Client).where(Client.curp == existing_curp)
    )
    existing = result.scalar_one_or_none()

    if existing:
        for s in submissions:
            await reject_submission(db, s, "Cliente ya registrado.")
        await reject_event(db, event, "Cliente ya registrado.")
        await db.commit()
        return False, (
            f"El cliente con CURP {existing_curp} "
            f"ya se encuentra registrado con ID {existing.client_id}."
        )

    client = Client(
        nombre_completo   = field_val(front_fields, "nombre_completo"),
        curp              = field_val(front_fields, "curp"),
        clave_de_elector  = field_val(front_fields, "clave_de_elector"),
        fecha_nacimiento  = field_val(front_fields, "fecha_nacimiento"),
        domicilio         = field_val(front_fields, "domicilio"),
        front_submission_id  = front_sub.submission_id,
        back_submission_id   = back_sub.submission_id,
        event_id             = event.event_id,
        registered_by        = event.initiated_by,
    )
    db.add(client)

    front_sub.status = SubmissionStatus.complete
    back_sub.status  = SubmissionStatus.complete
    event.status     = EventStatus.complete
    event.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    event.linked_entity_type = "CLIENT"

    await db.flush()
    event.linked_entity_id = client.client_id
    await db.commit()

    return True, f"Cliente registrado exitosamente. ID: {client.client_id}"


async def handle_client_registration(
    db: AsyncSession,
    submission: Submission,
    event: Event,
) -> tuple[bool, str]:

    p1_success, p1_message = await run_phase1(db, submission, event)
    if not p1_success:
        await reject_event(db, event, p1_message)
        await db.commit()
        return False, p1_message

    return True, p1_message
