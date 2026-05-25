import os
import io
from typing import Optional

from sqlalchemy.orm import Session
from pypdf import PdfReader, PdfWriter

from config import SERIE_LENGTH, MOTOR_LENGTH
from models.event import Event
from models.submission import Submission
from models.motorcycle import Motorcycle, MotorcycleStatus
from services.main_pipeline import (
    get_model,
    call_gemini_pdf,
    call_gemini_image,
    log_ai,
)
from services.pipeline_utils import (
    load_image_as_pil,
    pil_to_jpeg_bytes,
    _hamming,
    reject_and_return,
    check_confidence,
    mark_complete,
)

# ======================================================================== #
# Constants                                                                 #
# ======================================================================== #

NOT_PURCHASED_SENTINEL_MODEL_ID = 9999

# ======================================================================== #
# Prompts                                                                   #
# ======================================================================== #

TABLE_DETECTION_PROMPT = """
You are analyzing a scanned document image of a motorcycle delivery form.
Return ONLY a valid JSON object. No explanation, no markdown, no text outside the JSON.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DOCUMENT STRUCTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This document has three distinct visual regions:

REGION 1 — HEADER BLOCK (top of page):
Contains metadata fields such as: distributor name, client name, operator name,
vehicle series number, license plate, transport company, total number of motorcycles,
folio number, departure date, arrival date. This region has NO table structure.

REGION 2 — MOTORCYCLE DATA TABLE (middle of page):
A structured table with a darker shaded header row containing these column names:
NO., MODELO(S)/VERSION(ES), AÑO, NO.MOTOR, NO.SERIE, ESTADO ESTÉTICO,
KIT ACCESORIOS, UGO LLAVES, POLIZA, NO.FACTURA, OBSERVACIONES.
Below the header row are numbered data rows (1, 2, 3...) each containing
one motorcycle entry. This is the region you must locate.

REGION 3 — FOOTER BLOCK (bottom of page):
Contains signature boxes, stamps, handwritten notes, dates, company logos,
and printed legal text. This region must be completely excluded.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR TASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Locate REGION 2 — the motorcycle data table — and return its bounding coordinates.

RULES FOR LOCATING THE TABLE:
1. The table STARTS at the top edge of the darker shaded header row containing
   the column names listed above. The column names must be fully visible and
   included within your coordinates — do not crop them out.
2. The table ENDS at the bottom edge of the last numbered data row.
   Ignore any blank space, handwritten notes, stamps, or signature boxes
   that appear below the last data row.
3. Add a margin of approximately 15 units (on the 0-1000 scale) on all four
   sides of the table to avoid accidentally cropping valuable data at the edges.
   - Expand ymin upward by 15 units
   - Expand ymax downward by 15 units
   - Expand xmin leftward by 15 units
   - Expand xmax rightward by 15 units
   - Never go below 0 or above 1000 on any coordinate.
4. If the image is blurry, dark, or the table structure is not clearly visible,
   set overall_confidence below 0.75.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Return this exact JSON and nothing else:
{
  "table_coordinates": {
    "ymin": 0,
    "xmin": 0,
    "ymax": 0,
    "xmax": 0
  },
  "overall_confidence": 0.0
}

table_coordinates: the bounding box of the motorcycle data table including margins.
All values are on a scale of 0 to 1000 where 0 is the top/left edge of the image
and 1000 is the bottom/right edge.
overall_confidence: float between 0.0 and 1.0 reflecting how clearly you could
locate the table boundaries. Set below 0.75 if the table is not clearly visible.
"""

EXTRACTION_PROMPT_TEMPLATE = """
You are a data extraction robot processing a scanned Mexican motorcycle delivery document.
The document is in Spanish and may contain handwritten notes, stamps, and signatures.
Return ONLY a valid JSON object. No explanation, no markdown, no text outside the JSON.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ATTENTION ZONE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
A previous analysis has identified the exact location of the motorcycle data table
in this image. Focus your attention EXCLUSIVELY on the region defined by these
bounding box coordinates. Ignore everything outside this region completely —
including the document header, footer, signatures, stamps, and handwritten notes.

The bounding box uses a scale of 0 to 1000 where:
- 0 on the vertical axis (y) is the TOP edge of the full image
- 1000 on the vertical axis (y) is the BOTTOM edge of the full image
- 0 on the horizontal axis (x) is the LEFT edge of the full image
- 1000 on the horizontal axis (x) is the RIGHT edge of the full image

TABLE REGION TO FOCUS ON:
{{TABLE_COORDINATES}}

This region contains a table that starts with a darker shaded header row
and is followed by numbered data rows. Process ONLY what is inside this region.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 1 — IDENTIFY THE TABLE STRUCTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Within the attention zone the table has these columns in this exact order:
NO., MODELO(S)/VERSION(ES), AÑO, NO.MOTOR, NO.SERIE, ESTADO ESTÉTICO,
KIT ACCESORIOS, UGO LLAVES, POLIZA, NO.FACTURA, OBSERVACIONES.

The first row of the table is a darker shaded header row containing these column names.
Every row after the header is a data row starting with a sequential number (1, 2, 3...).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2 — EXTRACT DATA ROWS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You must extract ONLY two values per row: NO.MOTOR and NO.SERIE.
Everything else must be ignored.

HOW TO IDENTIFY A VALID DATA ROW:
- Every valid row starts with a small sequential integer row number (1, 2, 3...)
- If a line does not start with a sequential row number it is NOT a valid data row
- The darker shaded header row is NOT a data row — skip it

HOW TO EXTRACT NO.MOTOR:
- This is the fourth column, after NO., MODELO(S)/VERSION(ES), and AÑO
- It is always a short alphanumeric string with NO spaces
- It contains only letters and numbers, no hyphens
- It is always exactly 11 characters long
- Examples: "JFXCSJ73225", "JZXWSJ53418", "PDXCSB82011"
- Copy it exactly as written character by character
- WARNING: be precise — a misread character will cause matching failure

HOW TO EXTRACT NO.SERIE:
- This is the fifth column, immediately after NO.MOTOR
- It is always a longer alphanumeric string with NO spaces
- It contains only letters and numbers, no hyphens
- It is always exactly 17 characters long
- Examples: "MD2A67MX9TCJ01148", "MD2C19BX7TWJ51566", "MD2B54DX0TCB00883"
- Copy it exactly as written character by character
- WARNING 1: this column may have handwritten marks, checkmarks, ink stamps,
  or pen strokes written next to or overlapping the printed value.
  These handwritten elements are NOT part of the serie number.
  Focus exclusively on the computer-printed alphanumeric characters.
  Ignore any handwritten marks completely — extract only the machine-printed text.
- WARNING 2: NO.SERIE and NO.MOTOR are structurally different.
  NO.MOTOR is shorter (11 chars). NO.SERIE is longer (17 chars).
  Never swap them. If you are unsure which column you are reading,
  count the characters — 11 means NO.MOTOR, 17 means NO.SERIE.

LINES TO SKIP COMPLETELY:
- The darker shaded header row containing column names
- Any line that does not start with a sequential row number
- Any handwritten text, stamps, or signatures that may appear near the table edges
- Any line containing only checkmarks, dashes, or empty cells

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXTRACTION PROCESS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Repeat for every valid data row inside the attention zone:
1. Find the next row starting with a sequential row number
2. Skip to the fourth column — extract NO.MOTOR (this will always be 11 characters)
3. Move to the fifth column — extract NO.SERIE (this will always be 17 characters)
4. Skip everything else on that row
5. Move to the next row number
6. Stop when there are no more numbered rows inside the attention zone

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Return this exact JSON and nothing else:
{
  "motorcycles": [
    {
      "motor": "string",
      "serie": "string"
    }
  ],
  "overall_confidence": 0.0
}

overall_confidence: float between 0.0 and 1.0.
Reflects how clearly you could read NO.MOTOR and NO.SERIE values in the attention zone.
Set below 0.75 if the image is blurry, if any value is unreadable, or if the
attention zone does not clearly contain a motorcycle data table.
"""


# ======================================================================== #
# PDF splitting                                                             #
# ======================================================================== #

def _split_pdf_into_pages(pdf_bytes: bytes) -> list[bytes]:
    """
    Splits a multi-page PDF into individual single-page PDF bytes.
    Returns a list where each element is one page as bytes.
    Uses pypdf — no system dependencies required.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages  = []
    for page in reader.pages:
        writer = PdfWriter()
        writer.add_page(page)
        buffer = io.BytesIO()
        writer.write(buffer)
        pages.append(buffer.getvalue())
    return pages


def _load_pages(raw_path: str) -> list[tuple[bytes, str]]:
    """
    Loads file from disk and returns list of (page_bytes, mime_type) tuples.
    For PDFs — splits into pages, each as single-page PDF bytes.
    For images — returns single entry as JPEG bytes.
    """
    ext = os.path.splitext(raw_path)[-1].lower()

    with open(raw_path, "rb") as f:
        file_bytes = f.read()

    if ext == ".pdf":
        pages = _split_pdf_into_pages(file_bytes)
        return [(p, "application/pdf") for p in pages]
    else:
        pil_img   = load_image_as_pil(raw_path)
        img_bytes = pil_to_jpeg_bytes(pil_img)
        return [(img_bytes, "image/jpeg")]


# ======================================================================== #
# DB-based string validation and autocorrect                               #
# ======================================================================== #

def _autocorrect_against_pool(
    gemini_value: str,
    expected_length: int,
    pool: list[str],
) -> tuple[Optional[str], str]:
    """
    Validates a Gemini-extracted string against a pool of known DB values.
    Attempts single-character auto-correction if exact match fails.

    Returns (corrected_value, status):
      "exact"      — found as-is in pool
      "corrected"  — single character error corrected unambiguously
      "ambiguous"  — multiple candidates at distance 1
      "not_found"  — no candidate within distance 1
    """
    clean = gemini_value.replace(" ", "").upper()

    if clean in [p.upper() for p in pool]:
        return clean, "exact"

    candidates = [
        p for p in pool
        if len(p) == expected_length and _hamming(clean, p.upper()) == 1
    ]

    if len(candidates) == 1:
        return candidates[0], "corrected"
    elif len(candidates) > 1:
        return None, "ambiguous"
    else:
        return None, "not_found"


# ======================================================================== #
# Matching logic                                                            #
# ======================================================================== #

def _match_motorcycle(
    serie: str,
    motor: str,
    pool: list[Motorcycle],
    consumed_ids: set[int],
) -> tuple[Optional[Motorcycle], str, str, str]:
    """
    Attempts to match a serie/motor pair against the incoming motorcycle pool.
    Returns (motorcycle, serie_status, motor_status, match_via)

    match_via values: "serie" | "motor" | "both" | "not_found"
    """
    pool_series = [
        m.reference_number for m in pool
        if m.motorcycle_id not in consumed_ids
        and m.reference_number
    ]
    pool_motors = [
        m.motor_number for m in pool
        if m.motorcycle_id not in consumed_ids
        and m.motor_number
    ]

    corrected_serie, serie_status = _autocorrect_against_pool(
        serie, SERIE_LENGTH, pool_series
    )
    corrected_motor, motor_status = _autocorrect_against_pool(
        motor, MOTOR_LENGTH, pool_motors
    )

    matched_by_serie = None
    if serie_status in ("exact", "corrected"):
        matched_by_serie = next(
            (m for m in pool
             if m.motorcycle_id not in consumed_ids
             and m.reference_number
             and m.reference_number.upper() == corrected_serie.upper()),
            None
        )

    matched_by_motor = None
    if motor_status in ("exact", "corrected"):
        matched_by_motor = next(
            (m for m in pool
             if m.motorcycle_id not in consumed_ids
             and m.motor_number
             and m.motor_number.upper() == corrected_motor.upper()),
            None
        )

    if matched_by_serie and matched_by_motor:
        if matched_by_serie.motorcycle_id == matched_by_motor.motorcycle_id:
            return matched_by_serie, serie_status, motor_status, "both"
        else:
            return matched_by_serie, serie_status, motor_status, "serie"

    if matched_by_serie:
        return matched_by_serie, serie_status, motor_status, "serie"

    if matched_by_motor:
        return matched_by_motor, serie_status, motor_status, "motor"

    if serie_status == "ambiguous" and motor_status == "ambiguous":
        return None, serie_status, motor_status, "hard_stop"

    if serie_status == "ambiguous" and motor_status in ("not_found",):
        return None, serie_status, motor_status, "hard_stop"

    if motor_status == "ambiguous" and serie_status in ("not_found",):
        return None, serie_status, motor_status, "hard_stop"

    return None, serie_status, motor_status, "not_found"


# ======================================================================== #
# Terminal validation output                                                #
# ======================================================================== #

def _print_validation_results(results: list[dict]):
    """
    Prints a clean validation summary to the FastAPI terminal.
    Shows per motorcycle: name, serie status, motor status, match result.
    """
    width = 72
    print(f"\n{'═' * width}")
    print(f"  DELIVERY CONFIRMATION — VALIDATION RESULTS")
    print(f"{'═' * width}")

    for r in results:
        print(f"\n  ROW {r['row']} — {r['model_name']} {r['year']}")
        print(f"  {'─' * 68}")
        print(f"  Serie:   {r['serie']:<20} → {r['serie_status']}")
        print(f"  Motor:   {r['motor']:<20} → {r['motor_status']}")

        if r["match_via"] == "hard_stop":
            print(f"  Result:  x HARD STOP — ambiguity detected")
        elif r["match_via"] == "not_found":
            print(f"  Result:  ! NOT FOUND -> not_purchased")
        else:
            target = "in_stock_reserved" if r.get("was_reserved") else "in_stock"
            print(f"  Result:  + MATCHED via {r['match_via'].upper()} -> {target}")
            if r.get("was_reserved"):
                print(f"  * RESERVADA -> in_stock_reserved")
            if r["serie_status"] not in ("exact", "corrected") or \
               r["motor_status"] not in ("exact", "corrected"):
                print(f"  ! Discrepancy logged — matched via one field only")

    print(f"\n{'═' * width}\n")


# ======================================================================== #
# Pipeline                                                                  #
# ======================================================================== #

def handle_delivery_confirmation(
    db: Session,
    submission: Submission,
    event: Event,
    declared_count: int,
    dealership_id: int,
) -> tuple[bool, str]:
    """
    Pipeline for delivery_confirmation event.
    1.  Load file from disk — split PDF into pages or use image directly.
    2.  For each page run Prompt 1 (table detection) + Prompt 2 (extraction).
    3.  Collect all extracted serie/motor pairs across all pages.
    4.  Count validation against declared_count.
    5.  Load incoming motorcycle pool for dealership from DB.
    6.  Match each pair against pool using DB-based autocorrect.
    7.  Print validation results to terminal.
    8.  Hard stop if any ambiguity detected.
    9.  All or nothing commit — matched → in_stock, unmatched → not_purchased.
    10. Mark submission and event complete.
    """

    # ------------------------------------------------------------------ #
    # 1. Load file and split into pages                                   #
    # ------------------------------------------------------------------ #
    raw_path = submission.raw_file_path
    if not raw_path or not os.path.exists(raw_path):
        return reject_and_return(db, submission, event, "Archivo no encontrado en disco.")

    try:
        pages = _load_pages(raw_path)
    except Exception as e:
        return reject_and_return(db, submission, event, f"Error al cargar el archivo: {e}")

    # ------------------------------------------------------------------ #
    # 2. Process each page — two prompts per page                         #
    # ------------------------------------------------------------------ #
    model = get_model()
    all_extracted = []

    for page_index, (page_bytes, mime_type) in enumerate(pages):
        page_num     = page_index + 1
        step_detect  = f"table_detection_page_{page_num}"
        step_extract = f"extraction_page_{page_num}"

        # Prompt 1 — table detection
        try:
            if mime_type == "application/pdf":
                raw1, dict1 = call_gemini_pdf(model, TABLE_DETECTION_PROMPT, page_bytes)
            else:
                raw1, dict1 = call_gemini_image(model, TABLE_DETECTION_PROMPT, page_bytes)
        except ValueError as e:
            reason = f"Error en detección de tabla página {page_num}: {e}"
            log_ai(db, submission.submission_id, step_detect, str(e), None, None, False)
            return reject_and_return(db, submission, event, reason)

        confidence1 = dict1.get("overall_confidence")
        ok, msg = check_confidence(
            db, submission, event, confidence1,
            step_detect, raw1, dict1,
        )
        if not ok: return ok, msg

        table_coords = dict1.get("table_coordinates")
        if not table_coords:
            reason = f"No se encontraron coordenadas de tabla en página {page_num}."
            return reject_and_return(db, submission, event, reason)

        # Prompt 2 — data extraction using coordinates as context
        extraction_prompt = EXTRACTION_PROMPT_TEMPLATE.replace(
            "{{TABLE_COORDINATES}}", str(table_coords)
        )

        try:
            if mime_type == "application/pdf":
                raw2, dict2 = call_gemini_pdf(model, extraction_prompt, page_bytes)
            else:
                raw2, dict2 = call_gemini_image(model, extraction_prompt, page_bytes)
        except ValueError as e:
            reason = f"Error en extracción de datos página {page_num}: {e}"
            log_ai(db, submission.submission_id, step_extract, str(e), None, None, False)
            return reject_and_return(db, submission, event, reason)

        confidence2 = dict2.get("overall_confidence")
        ok, msg = check_confidence(
            db, submission, event, confidence2,
            step_extract, raw2, dict2,
        )
        if not ok: return ok, msg

        page_motorcycles = dict2.get("motorcycles", [])
        all_extracted.extend(page_motorcycles)

    # ------------------------------------------------------------------ #
    # 3. Count validation                                                 #
    # ------------------------------------------------------------------ #
    extracted_count = len(all_extracted)
    if extracted_count != declared_count:
        reason = (
            f"El número de motocicletas extraídas ({extracted_count}) "
            f"no coincide con el total declarado ({declared_count}). "
            f"Por favor verifica el documento e intenta de nuevo."
        )
        return reject_and_return(db, submission, event, reason)

    # ------------------------------------------------------------------ #
    # 4. Load incoming pool for dealership                                #
    # ------------------------------------------------------------------ #
    incoming_pool = db.query(Motorcycle).filter(
        Motorcycle.dealership_id == dealership_id,
        Motorcycle.status.in_([
            MotorcycleStatus.incoming,
            MotorcycleStatus.incoming_reserved,
        ]),
    ).all()

    # ------------------------------------------------------------------ #
    # 5. Match each extracted pair against pool                           #
    # ------------------------------------------------------------------ #
    consumed_ids       = set()
    validation_results = []
    hard_stop_detected = False
    hard_stop_reason   = None

    for i, moto in enumerate(all_extracted):
        serie = moto.get("serie", "")
        motor = moto.get("motor", "")

        matched_moto, serie_status, motor_status, match_via = _match_motorcycle(
            serie, motor, incoming_pool, consumed_ids
        )

        if matched_moto and matched_moto.model:
            model_name = matched_moto.model.canonical_name
            year       = matched_moto.model.year
        else:
            model_name = "Desconocido"
            year       = ""

        was_reserved = (
            matched_moto.status == MotorcycleStatus.incoming_reserved
            if matched_moto else False
        )

        validation_results.append({
            "row":          i + 1,
            "serie":        serie,
            "motor":        motor,
            "serie_status": serie_status,
            "motor_status": motor_status,
            "match_via":    match_via,
            "model_name":   model_name,
            "year":         year,
            "motorcycle":   matched_moto,
            "was_reserved": was_reserved,
        })

        if match_via == "hard_stop":
            hard_stop_detected = True
            hard_stop_reason   = (
                f"Ambigüedad detectada en fila {i+1}: "
                f"serie='{serie}' ({serie_status}), "
                f"motor='{motor}' ({motor_status}). "
                f"No se puede determinar la motocicleta correcta."
            )
            break

        if match_via not in ("not_found",) and matched_moto:
            consumed_ids.add(matched_moto.motorcycle_id)

    # ------------------------------------------------------------------ #
    # 6. Print validation results to terminal                             #
    # ------------------------------------------------------------------ #
    _print_validation_results(validation_results)

    # ------------------------------------------------------------------ #
    # 7. Hard stop if ambiguity detected                                  #
    # ------------------------------------------------------------------ #
    if hard_stop_detected:
        return reject_and_return(db, submission, event, hard_stop_reason)

    # ------------------------------------------------------------------ #
    # 8. All or nothing commit                                            #
    # ------------------------------------------------------------------ #
    for result in validation_results:
        matched_moto = result["motorcycle"]
        match_via    = result["match_via"]

        if match_via == "not_found":
            new_moto = Motorcycle(
                model_id                 = NOT_PURCHASED_SENTINEL_MODEL_ID,
                dealership_id            = dealership_id,
                reference_number         = result["serie"] or None,
                motor_number             = result["motor"] or None,
                delivery_confirmation_id = submission.submission_id,
                status                   = MotorcycleStatus.not_purchased,
            )
            db.add(new_moto)
            db.flush()
        else:
            if result.get("was_reserved"):
                matched_moto.status = MotorcycleStatus.in_stock_reserved
            else:
                matched_moto.status = MotorcycleStatus.in_stock
            matched_moto.delivery_confirmation_id = submission.submission_id
            db.flush()

    # ------------------------------------------------------------------ #
    # 9. Mark submission and event complete                               #
    # ------------------------------------------------------------------ #
    mark_complete(
        db, submission, event,
        "DELIVERY_CONFIRMATION", submission.submission_id,
    )

    in_stock_count      = sum(1 for r in validation_results if r["match_via"] != "not_found")
    not_purchased_count = sum(1 for r in validation_results if r["match_via"] == "not_found")

    return True, (
        f"Entrega confirmada. {in_stock_count} motocicleta(s) en stock. "
        f"{not_purchased_count} no registrada(s) previamente."
    )
