import os
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.event import Event
from models.submission import Submission
from models.motorcycle import Motorcycle, MotorcycleStatus
from models.motorcycle_catalog import MotorcycleCatalog
from models.order_confirmation_document import OrderConfirmationDocument
from models.dealership import Dealership
from services.main_pipeline import (
    get_model,
    call_gemini_text,
    log_ai,
)
from services.pipeline_utils import (
    reject_and_return,
    check_confidence,
    extract_raw_pdf_text,
    is_valid_serie,
    is_valid_motor,
    mark_complete,
    _auto_assign_reservations,
    _print_reservation_assignment_results,
)


# ======================================================================== #
# Prompt                                                                    #
# ======================================================================== #
def _build_order_confirmation_prompt() -> str:
    return """
You are a data extraction robot processing the plain text of a Mexican motorcycle
transfer notice (Aviso de Traslado). The text was extracted from a PDF using
pdfplumber and is provided at the end of these instructions.
Return ONLY a valid JSON object. No explanation, no markdown, no text outside the JSON.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 1 — EXTRACT DESTINATION ADDRESS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The destination address appears in the lower portion of the text, split across
multiple lines due to the multi-column layout of the original document.

RULES FOR FINDING THE ADDRESS:
- Look for a line that contains a street address starting with words like
  "AVENIDA", "AV.", "CALZ", "CALLE", "VIA", "BLVD" followed by a street name
  and number. This is the first line of the destination address.
- The address may continue on the following line with a colony name starting
  with "Col." or "COL." and/or a city name and postal code "C.P. XXXXX"
- Collect all address parts: street, colony, city, and postal code if present
- Concatenate them into a single string separated by spaces

Output as: "AVENIDA CALZ IGNACIO ZARAGOZA #396 Col. FEDERAL VENUSTIANO CARRANZA C.P. 15700"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2 — EXTRACT MOTORCYCLE TABLE ROWS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Each valid data row in the table follows this exact pattern on a single line:
<row_number> <modelo_version words> <4-digit year> <NO.MOTOR> <NO.SERIE> <price> <NA>

You must extract ONLY three values per row:
MODELO(S)/VERSION(ES), NO. DE MOTOR, and NO. DE SERIE.

HOW TO EXTRACT MODELO(S)/VERSION(ES):
- It is all the words between the row number and the 4-digit year (e.g. 2026)
- Format is always: "<model name> <color> <two digit year suffix>"
- Examples: "Dominar 400 UG Negro 26", "Pulsar N125 Car Citrus 26"
- Copy it exactly including the color and the two-digit year suffix
- STOP before the 4-digit year column value (e.g. stop before "2026")

HOW TO EXTRACT NO. DE MOTOR:
- It is the first token after the 4-digit year on the same line
- It is always exactly 11 characters long
- It contains only letters and numbers, no spaces, no hyphens
- Examples: "JFXCSJ73242", "JZXWSJ53394", "PDXCSB82014"

HOW TO EXTRACT NO. DE SERIE:
- It is the second token after the 4-digit year on the same line
- It is always exactly 17 characters long
- It contains only letters and numbers, no spaces, no hyphens
- Examples: "MD2A67MX3TCJ01162", "MD2C19BX3TWJ51564", "MD2B54DX7TCB00881"
- WARNING: NO. DE MOTOR (11 chars) and NO. DE SERIE (17 chars) are different.

LINES TO SKIP COMPLETELY:
- Any line that does not start with a sequential row number
- The header line containing: "NO. MODELO(S)/VERSION(ES) AÑO(S) NO. DE MOTOR..."
- Footer lines: "Tipo de traslado", "Responsable", "Domicilio", "Nombre del"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Return this exact JSON and nothing else:
{
  "domicilio_destino": "string",
  "motorcycles": [
    {
      "modelo_version": "string",
      "motor": "string",
      "serie": "string"
    }
  ],
  "overall_confidence": 0.0
}

overall_confidence: float between 0.0 and 1.0.
Set below 0.75 ONLY if the address is missing or any motor/serie value cannot
be determined with certainty.

DOCUMENT TEXT:
"""


# ======================================================================== #
# Helpers                                                                   #
# ======================================================================== #

def _parse_model_name(
    raw_name: str,
    canonical_names: list[str],
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Parses a raw model name from the order confirmation document.
    Format is always: "<canonical name> <color> <last two digits of year>"
    Returns (canonical_name, color, year) — any can be None if parsing fails.
    """
    if not raw_name:
        return None, None, None

    raw_stripped      = raw_name.strip()
    matched_canonical = None

    sorted_canonicals = sorted(canonical_names, key=len, reverse=True)
    for canonical in sorted_canonicals:
        if raw_stripped.lower().startswith(canonical.lower()):
            matched_canonical = canonical
            break

    if not matched_canonical:
        return None, None, None

    remainder = raw_stripped[len(matched_canonical):].strip()
    tokens    = remainder.split()

    year  = None
    color = None

    if tokens:
        last_token = tokens[-1]
        if last_token.isdigit() and len(last_token) == 2:
            year         = f"20{last_token}"
            color_tokens = tokens[:-1]
        else:
            color_tokens = tokens
        color = " ".join(color_tokens) if color_tokens else None

    return matched_canonical, color, year


async def _find_matching_purchased_motorcycle(
    db: AsyncSession,
    model_id: int,
    dealership_id: int,
) -> Optional[Motorcycle]:
    """
    Finds the oldest purchased motorcycle matching model_id and dealership.
    Greedy by created_at — oldest unmatched record gets priority.
    """
    result = await db.execute(
        select(Motorcycle)
        .where(
            Motorcycle.model_id == model_id,
            Motorcycle.dealership_id == dealership_id,
            Motorcycle.status == MotorcycleStatus.purchased,
        )
        .order_by(Motorcycle.created_at.asc())
        .limit(1)                            
    )
    return result.scalar_one_or_none()


# ======================================================================== #
# Pipeline                                                                  #
# ======================================================================== #

async def handle_order_confirmation(
    db: AsyncSession,
    submission: Submission,
    event: Event,
) -> tuple[bool, str]:
    """
    Pipeline for order_confirmation event.
    """

    # 1. Load PDF bytes from disk
    if not submission.raw_file_path or not os.path.exists(submission.raw_file_path):
        return await reject_and_return(db, submission, event, "Archivo PDF no encontrado en disco.")

    with open(submission.raw_file_path, "rb") as f:
        pdf_bytes = f.read()

    raw_text = extract_raw_pdf_text(pdf_bytes)

    # 2. Call Gemini
    model  = get_model()
    prompt = _build_order_confirmation_prompt()

    try:
        raw_response, parsed_dict = await call_gemini_text(model, prompt, raw_text)
    except ValueError as e:
        reason = f"Error al procesar respuesta de IA: {e}"
        await log_ai(db, submission.submission_id, "extraction", str(e), None, None, False)
        return await reject_and_return(db, submission, event, reason)

    # 3. Validate confidence and required fields
    confidence       = parsed_dict.get("overall_confidence")
    domicilio        = parsed_dict.get("domicilio_destino")
    motorcycles_data = parsed_dict.get("motorcycles", [])

    print(f"[GEMINI CONFIDENCE] {confidence}")

    ok, msg = await check_confidence(
        db, submission, event, confidence,
        "extraction", raw_response, parsed_dict,
    )
    if not ok: return ok, msg

    if not domicilio:
        reason = "No se pudo extraer el domicilio de destino del documento."
        return await reject_and_return(db, submission, event, reason)

    if not motorcycles_data:
        reason = "No se encontraron motocicletas en el documento."
        return await reject_and_return(db, submission, event, reason)

    # 4. Match domicilio to dealership via ilike
    result = await db.execute(
        select(Dealership).where(Dealership.address.ilike(f"%{domicilio}%"))
    )
    dealership = result.scalar_one_or_none()

    if not dealership:
        reason = (
            f"Domicilio '{domicilio}' no encontrado en el sistema. "
            f"Verifica el catálogo de sucursales."
        )
        return await reject_and_return(db, submission, event, reason)

    # 5. Structural validation of extracted serie and motor numbers
    for i, moto in enumerate(motorcycles_data):
        serie = moto.get("serie", "")
        motor = moto.get("motor", "")
        if not is_valid_serie(serie):
            reason = (
                f"Fila {i + 1}: el número de serie '{serie}' no tiene el formato "
                f"esperado. Debe tener exactamente 17 caracteres alfanuméricos."
            )
            return await reject_and_return(db, submission, event, reason)
        if not is_valid_motor(motor):
            reason = (
                f"Fila {i + 1}: el número de motor '{motor}' no tiene el formato "
                f"esperado. Debe tener exactamente 11 caracteres alfanuméricos."
            )
            return await reject_and_return(db, submission, event, reason)

    # 6. Build canonical names list from catalog
    result = await db.execute(select(MotorcycleCatalog.canonical_name).distinct())
    canonical_names = list(result.scalars().all())

    # 7. Parse model names
    parsed_models = []

    for i, moto in enumerate(motorcycles_data):
        raw_name = moto.get("modelo_version", "")
        canonical_name, color, year = _parse_model_name(raw_name, canonical_names)

        if not canonical_name:
            reason = (
                f"No se pudo identificar el modelo en fila {i+1}: "
                f"'{raw_name}'. Verifica el documento."
            )
            return await reject_and_return(db, submission, event, reason)

        parsed_models.append({
            "canonical_name": canonical_name,
            "color":          color,
            "year":           year,
            "serie":          moto.get("serie", ""),
            "motor":          moto.get("motor", ""),
        })

    # 8. Look up model_id from motorcycle_catalog
    resolved_models = []

    for i, parsed in enumerate(parsed_models):
        result = await db.execute(
            select(MotorcycleCatalog).where(
                MotorcycleCatalog.canonical_name == parsed["canonical_name"],
                MotorcycleCatalog.year == parsed["year"],
            )
        )
        catalog_entry = result.scalar_one_or_none()

        if not catalog_entry:
            reason = (
                f"Modelo '{parsed['canonical_name']}' año {parsed['year']} "
                f"no encontrado en el catálogo. Verifica el catálogo de modelos."
            )
            return await reject_and_return(db, submission, event, reason)

        resolved_models.append({**parsed, "model_id": catalog_entry.model_id})

    # 9. Create OrderConfirmationDocument row
    order_conf_doc = OrderConfirmationDocument(
        submission_id = submission.submission_id,
        dealership_id = dealership.dealership_id,
        total_units   = len(resolved_models),
    )
    db.add(order_conf_doc)
    await db.flush()

    # 10. Match each motorcycle to purchased record or create as incoming
    newly_incoming = []

    for resolved in resolved_models:
        existing = await _find_matching_purchased_motorcycle(
            db,
            model_id      = resolved["model_id"],
            dealership_id = dealership.dealership_id,
        )

        if existing:
            existing.status                = MotorcycleStatus.incoming
            existing.reference_number      = resolved["serie"]
            existing.motor_number          = resolved["motor"]
            existing.color                 = resolved["color"]
            existing.order_confirmation_id = order_conf_doc.order_confirmation_document_id
            await db.flush()
            newly_incoming.append(existing)
        else:
            new_moto = Motorcycle(
                model_id               = resolved["model_id"],
                dealership_id          = dealership.dealership_id,
                reference_number       = resolved["serie"],
                motor_number           = resolved["motor"],
                color                  = resolved["color"],
                order_confirmation_id  = order_conf_doc.order_confirmation_document_id,
                status                 = MotorcycleStatus.incoming,
            )
            db.add(new_moto)
            await db.flush()
            newly_incoming.append(new_moto)

    # 11. Auto-assign reservations
    if newly_incoming:
        assignment_results = await _auto_assign_reservations(
            db, dealership.dealership_id, newly_incoming
        )
        _print_reservation_assignment_results(assignment_results)

    # 12. Mark submission and event complete
    await mark_complete(
        db, submission, event,
        "ORDER_CONFIRMATION", order_conf_doc.order_confirmation_document_id,
    )

    total = len(resolved_models)
    return True, (
        f"Confirmación de pedido registrada exitosamente. "
        f"{total} motocicleta(s) procesada(s) para {dealership.name}."
    )
