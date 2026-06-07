import os
import io

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
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
    _levenshtein,
    reject_and_return,
    check_confidence,
    mark_complete,
    _auto_assign_reservations,
    _print_reservation_assignment_results,
)

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
1. The table STARTS at the top edge of the darker shaded header row.
   The column names must be fully visible and included within your coordinates.
2. The table ENDS at the bottom edge of the last numbered data row.
3. Add a margin of approximately 15 units (on the 0-1000 scale) on all four sides.
4. If the image is blurry or the table structure is not clearly visible,
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
overall_confidence: float between 0.0 and 1.0.
"""

EXTRACTION_PROMPT_TEMPLATE = """
You are a data extraction robot processing a scanned Mexican motorcycle delivery document.
The document is in Spanish and may contain handwritten notes, stamps, and signatures.
Return ONLY a valid JSON object. No explanation, no markdown, no text outside the JSON.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ATTENTION ZONE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Focus your attention EXCLUSIVELY on the region defined by these bounding box coordinates.
Ignore everything outside this region completely.

TABLE REGION TO FOCUS ON:
{{TABLE_COORDINATES}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2 — EXTRACT DATA ROWS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You must extract ONLY two values per row: NO.MOTOR and NO.SERIE.

HOW TO EXTRACT NO.MOTOR:
- This is the fourth column, after NO., MODELO(S)/VERSION(ES), and AÑO
- It is always exactly 11 characters long
- It contains only letters and numbers, no hyphens
- Examples: "JFXCSJ73225", "JZXWSJ53418", "PDXCSB82011"

HOW TO EXTRACT NO.SERIE:
- This is the fifth column, immediately after NO.MOTOR
- It is always exactly 17 characters long
- It contains only letters and numbers, no hyphens
- Examples: "MD2A67MX9TCJ01148", "MD2C19BX7TWJ51566", "MD2B54DX0TCB00883"
- WARNING: handwritten marks near the column must be ignored.
  Focus exclusively on the computer-printed alphanumeric characters.

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
Set below 0.75 if the image is blurry or any value is unreadable.
"""


# ======================================================================== #
# PDF splitting                                                             #
# ======================================================================== #

def _split_pdf_into_pages(pdf_bytes: bytes) -> list[bytes]:
    """Splits a multi-page PDF into individual single-page PDF bytes."""
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
# Terminal validation output                                                #
# ======================================================================== #

def _print_validation_results(results: list[dict]):
    """Prints a clean validation summary to the FastAPI terminal."""
    width = 72
    print(f"\n{'═' * width}")
    print(f"  DELIVERY CONFIRMATION — VALIDATION RESULTS")
    print(f"{'═' * width}")

    for r in results:
        model_name = r.get("model_name", "Desconocido")
        year       = r.get("year", "")
        print(f"\n  ROW {r['row']} — {model_name} {year}")
        print(f"  {'─' * 68}")
        print(f"  Serie:   {r['serie']:<20} → {r['serie_status']}")
        print(f"  Motor:   {r['motor']:<20} → {r['motor_status']}")

        if not r.get("resolved"):
            print(f"  Result:  x UNRESOLVED — no match found in pool")
        else:
            print(f"  Result:  + MATCHED via {r['match_via'].upper()} -> in_stock")
            if r.get("discrepancy"):
                print(f"  ! Discrepancy logged: {r['discrepancy']}")
            if r.get("auto_assigned_to_reservation_id"):
                print(f"  * AUTO-ASSIGNED to reservation #{r['auto_assigned_to_reservation_id']}")

    print(f"\n{'═' * width}\n")


# ======================================================================== #
# Pipeline                                                                  #
# ======================================================================== #

async def handle_delivery_confirmation(
    db: AsyncSession,
    submission: Submission,
    event: Event,
    declared_count: int,
    dealership_id: int,
) -> tuple[bool, str]:
    """
    Pipeline for delivery_confirmation event.
    """

    # 1. Load file and split into pages
    raw_path = submission.raw_file_path
    if not raw_path or not os.path.exists(raw_path):
        return await reject_and_return(db, submission, event, "Archivo no encontrado en disco.")

    try:
        pages = _load_pages(raw_path)
    except Exception as e:
        return await reject_and_return(db, submission, event, f"Error al cargar el archivo: {e}")

    # 2. Process each page — two prompts per page
    model = get_model()
    all_extracted = []

    for page_index, (page_bytes, mime_type) in enumerate(pages):
        page_num     = page_index + 1
        step_detect  = f"table_detection_page_{page_num}"
        step_extract = f"extraction_page_{page_num}"

        # Prompt 1 — table detection
        try:
            if mime_type == "application/pdf":
                raw1, dict1 = await call_gemini_pdf(model, TABLE_DETECTION_PROMPT, page_bytes)
            else:
                raw1, dict1 = await call_gemini_image(model, TABLE_DETECTION_PROMPT, page_bytes)
        except ValueError as e:
            reason = f"Error en detección de tabla página {page_num}: {e}"
            await log_ai(db, submission.submission_id, step_detect, str(e), None, None, False)
            return await reject_and_return(db, submission, event, reason)

        confidence1 = dict1.get("overall_confidence")
        ok, msg = await check_confidence(
            db, submission, event, confidence1,
            step_detect, raw1, dict1,
        )
        if not ok: return ok, msg

        table_coords = dict1.get("table_coordinates")
        if not table_coords:
            reason = f"No se encontraron coordenadas de tabla en página {page_num}."
            return await reject_and_return(db, submission, event, reason)

        # Prompt 2 — data extraction using coordinates as context
        extraction_prompt = EXTRACTION_PROMPT_TEMPLATE.replace(
            "{{TABLE_COORDINATES}}", str(table_coords)
        )

        try:
            if mime_type == "application/pdf":
                raw2, dict2 = await call_gemini_pdf(model, extraction_prompt, page_bytes)
            else:
                raw2, dict2 = await call_gemini_image(model, extraction_prompt, page_bytes)
        except ValueError as e:
            reason = f"Error en extracción de datos página {page_num}: {e}"
            await log_ai(db, submission.submission_id, step_extract, str(e), None, None, False)
            return await reject_and_return(db, submission, event, reason)

        confidence2 = dict2.get("overall_confidence")
        ok, msg = await check_confidence(
            db, submission, event, confidence2,
            step_extract, raw2, dict2,
        )
        if not ok: return ok, msg

        page_motorcycles = dict2.get("motorcycles", [])
        all_extracted.extend(page_motorcycles)

    # 3. Count validation
    extracted_count = len(all_extracted)
    if extracted_count != declared_count:
        reason = (
            f"El número de motocicletas extraídas ({extracted_count}) "
            f"no coincide con el total declarado ({declared_count}). "
            f"Por favor verifica el documento e intenta de nuevo."
        )
        return await reject_and_return(db, submission, event, reason)

    # 4. Build structured pool from DB
    result = await db.execute(
        select(Motorcycle)
        .options(selectinload(Motorcycle.model))
        .where(
            Motorcycle.dealership_id == dealership_id,
            Motorcycle.status == MotorcycleStatus.incoming,
        )
    )
    raw_incoming = result.scalars().all()

    moto_by_id = {m.motorcycle_id: m for m in raw_incoming}

    pool = [
        {
            "motorcycle_id": m.motorcycle_id,
            "serie": m.reference_number.replace(" ", "").upper(),
            "motor": m.motor_number.replace(" ", "").upper(),
        }
        for m in raw_incoming
        if m.reference_number and m.motor_number
    ]

    # 5. PASS 1 — Exact pair matching
    results       = [None] * len(all_extracted)
    unmatched_idx = []

    for i, gemini_moto in enumerate(all_extracted):
        clean_serie = gemini_moto.get("serie", "").replace(" ", "").upper()
        clean_motor = gemini_moto.get("motor", "").replace(" ", "").upper()

        match_pos = None
        for j, entry in enumerate(pool):
            if entry["serie"] == clean_serie and entry["motor"] == clean_motor:
                match_pos = j
                break

        if match_pos is not None:
            matched = pool.pop(match_pos)
            results[i] = {
                "row":           i + 1,
                "serie":         clean_serie,
                "motor":         clean_motor,
                "serie_status":  "exact",
                "motor_status":  "exact",
                "match_via":     "both",
                "motorcycle_id": matched["motorcycle_id"],
                "discrepancy":   None,
                "resolved":      True,
            }
        else:
            unmatched_idx.append(i)

    # 6. PASS 2 — Autocorrection on unmatched pairs
    corrected_pairs = []

    for i in unmatched_idx:
        gemini_moto = all_extracted[i]
        clean_serie = gemini_moto.get("serie", "").replace(" ", "").upper()
        clean_motor = gemini_moto.get("motor", "").replace(" ", "").upper()

        pool_series = [entry["serie"] for entry in pool]
        pool_motors = [entry["motor"] for entry in pool]

        if clean_serie in pool_series:
            corrected_serie = clean_serie
            serie_status    = "exact"
        else:
            serie_candidates = [
                s for s in pool_series
                if abs(len(s) - SERIE_LENGTH) <= 2
                and _levenshtein(clean_serie, s) == 1
            ]
            if len(serie_candidates) == 1:
                corrected_serie = serie_candidates[0]
                serie_status    = "corrected"
            elif len(serie_candidates) > 1:
                corrected_serie = None
                serie_status    = "ambiguous"
            else:
                corrected_serie = None
                serie_status    = "not_found"

        if clean_motor in pool_motors:
            corrected_motor = clean_motor
            motor_status    = "exact"
        else:
            motor_candidates = [
                m for m in pool_motors
                if abs(len(m) - MOTOR_LENGTH) <= 2
                and _levenshtein(clean_motor, m) == 1
            ]
            if len(motor_candidates) == 1:
                corrected_motor = motor_candidates[0]
                motor_status    = "corrected"
            elif len(motor_candidates) > 1:
                corrected_motor = None
                motor_status    = "ambiguous"
            else:
                corrected_motor = None
                motor_status    = "not_found"

        corrected_pairs.append({
            "original_index":  i,
            "serie":           clean_serie,
            "motor":           clean_motor,
            "corrected_serie": corrected_serie,
            "corrected_motor": corrected_motor,
            "serie_status":    serie_status,
            "motor_status":    motor_status,
        })

    # 7. PASS 3 — Second matching attempt after autocorrection
    for cp in corrected_pairs:
        i               = cp["original_index"]
        corrected_serie = cp["corrected_serie"]
        corrected_motor = cp["corrected_motor"]
        serie_status    = cp["serie_status"]
        motor_status    = cp["motor_status"]

        matched_by_serie = None
        matched_by_motor = None

        if corrected_serie is not None:
            for entry in pool:
                if entry["serie"] == corrected_serie:
                    matched_by_serie = entry
                    break

        if corrected_motor is not None:
            for entry in pool:
                if entry["motor"] == corrected_motor:
                    matched_by_motor = entry
                    break

        matched_entry = None
        match_via     = "not_found"
        discrepancy   = None
        resolved      = False

        if matched_by_serie and matched_by_motor:
            if matched_by_serie["motorcycle_id"] == matched_by_motor["motorcycle_id"]:
                matched_entry = matched_by_serie
                match_via     = "both"
            else:
                matched_entry = matched_by_serie
                match_via     = "serie"
                discrepancy   = "motor matches a different motorcycle"
            pool.remove(matched_entry)
            resolved = True

        elif matched_by_serie:
            matched_entry = matched_by_serie
            match_via     = "serie"
            discrepancy   = "motor not found in pool"
            pool.remove(matched_entry)
            resolved      = True

        elif matched_by_motor:
            matched_entry = matched_by_motor
            match_via     = "motor"
            discrepancy   = "serie not found in pool"
            pool.remove(matched_entry)
            resolved      = True

        results[i] = {
            "row":           i + 1,
            "serie":         cp["serie"],
            "motor":         cp["motor"],
            "serie_status":  serie_status,
            "motor_status":  motor_status,
            "match_via":     match_via,
            "motorcycle_id": matched_entry["motorcycle_id"] if matched_entry else None,
            "discrepancy":   discrepancy,
            "resolved":      resolved,
        }

    # 8. Enrich results with model info and reservation status
    for r in results:
        moto_id = r.get("motorcycle_id")
        if moto_id:
            moto = moto_by_id.get(moto_id)
            r["model_name"] = moto.model.canonical_name if moto and moto.model else "Desconocido"
            r["year"]       = moto.model.year           if moto and moto.model else ""
            r["motorcycle"] = moto
        else:
            r["model_name"] = "Desconocido"
            r["year"]       = ""
            r["motorcycle"] = None

    # 9. Print validation results to terminal
    _print_validation_results(results)

    # 10. PASS 4 — Cancel if any pair unresolved (zero DB writes)
    unresolved_rows = [r for r in results if not r.get("resolved")]
    if unresolved_rows:
        first = unresolved_rows[0]
        reason = (
            f"No se pudo identificar la motocicleta en fila {first['row']}: "
            f"serie='{first['serie']}' ({first['serie_status']}), "
            f"motor='{first['motor']}' ({first['motor_status']}). "
            f"Por favor sube una imagen más clara."
        )
        return await reject_and_return(db, submission, event, reason)

    # 11. PASS 5 — Commit status transitions (all pairs resolved)
    for r in results:
        moto = r["motorcycle"]
        moto.status = MotorcycleStatus.in_stock
        moto.delivery_confirmation_id = submission.submission_id
        await db.flush()

    # 11b. Auto-assign reservations against newly in_stock motos
    newly_in_stock = [r["motorcycle"] for r in results if r.get("resolved")]
    if newly_in_stock:
        assignment_results = await _auto_assign_reservations(
            db, dealership_id, newly_in_stock
        )
        _print_reservation_assignment_results(assignment_results)

    # 12. Mark submission and event complete
    await mark_complete(
        db, submission, event,
        "DELIVERY_CONFIRMATION", submission.submission_id,
    )

    return True, (
        f"Entrega confirmada. {len(results)} motocicleta(s) actualizadas a en stock."
    )
