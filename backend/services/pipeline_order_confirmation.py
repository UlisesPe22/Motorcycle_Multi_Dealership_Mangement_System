import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from config import CONFIDENCE_THRESHOLD ,SERIE_LENGTH, MOTOR_LENGTH 
from models.event import Event, EventStatus
from models.submission import Submission, SubmissionStatus
from models.motorcycle import Motorcycle, MotorcycleStatus
from models.motorcycle_catalog import MotorcycleCatalog
from models.order_confirmation_document import OrderConfirmationDocument
from models.dealership import Dealership
from services.main_pipeline import (
    get_model,
    call_gemini_pdf,
    log_ai,
    reject_submission,
    reject_event,
)
from services.image_utils import extract_clean_pdf_text, validate_and_correct_string

# ======================================================================== #
# Constants                                                                 #
# ======================================================================== #


# ======================================================================== #
# Prompt — to be built later                                                #
# ======================================================================== #

def _build_order_confirmation_prompt() -> str:
    return """
You are a data extraction robot processing a Mexican motorcycle transfer notice PDF (Aviso de Traslado).
The document is in Spanish.
Return ONLY a valid JSON object. No explanation, no markdown, no text outside the JSON.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 1 — EXTRACT FOOTER FIELD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Find this field in the BOTTOM LEFT area of the page in a labeled section:

- "domicilio_destino": the value that appears next to or below the label
  "Domicilio del destino:".
  This is a street address. Copy it exactly as written including street name,
  number, colony, city and postal code if present.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2 — EXTRACT MOTORCYCLE TABLE ROWS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The table has these columns: NO., MODELO(S)/VERSION(ES), AÑO(S),
NO. DE MOTOR, NO. DE SERIE, MES DE REPORTE, VALOR DECLARADO, EXTENSION PLAN PISO.

You must extract ONLY three values per row:
MODELO(S)/VERSION(ES), NO. DE MOTOR, and NO. DE SERIE.
Everything else must be ignored.

HOW TO IDENTIFY A VALID DATA ROW:
- Every valid row starts with a small sequential integer row number (1, 2, 3...)
- Followed immediately by the model name in MODELO(S)/VERSION(ES) column
- If a line does not start with a sequential row number it is NOT a valid data row

HOW TO EXTRACT MODELO(S)/VERSION(ES):
- This is the second column, immediately after the row number
- It always contains multiple words with spaces
- Format is always: "<canonical model name> <color> <two digit year>"
- Examples: "Dominar 400 UG Negro 26", "Pulsar N125 Car Citrus 26",
  "Pulsar N160 Premium Azul 26", "Pulsar N250 FI ABS Perla 26"
- Copy the full value exactly as written including color and year suffix
- Stop when you reach the AÑO(S) column which contains a 4-digit year like "2026"

HOW TO EXTRACT NO. DE MOTOR:
- This is the fourth column
- It is always a short alphanumeric string with NO spaces
- It contains only letters and numbers, no hyphens
- It is always exactly 11 characters long
- Examples: "JFXCSJ73242", "JZXWSJ53394", "PDXCSB82014"
- Copy it exactly as written

HOW TO EXTRACT NO. DE SERIE:
- This is the fifth column
- It is always a longer alphanumeric string with NO spaces
- It contains only letters and numbers, no hyphens
- It is always exactly 17 characters long
- Examples: "MD2A67MX3TCJ01162", "MD2C19BX3TWJ51564", "MD2B54DX7TCB00881"
- Copy it exactly as written
- WARNING: NO. DE SERIE and NO. DE MOTOR are different values in different columns.
  NO. DE MOTOR is shorter (11 chars), NO. DE SERIE is longer (17 chars).
  Never swap them.

LINES TO SKIP COMPLETELY:
- Any line that does not start with a sequential row number
- Header lines containing column titles
- Footer lines containing totals, addresses, signatures, dates, or labels
- Any line containing only numbers, decimals, or financial data

EXTRACTION PROCESS — repeat for every valid row:
1. Find the next line starting with a sequential row number
2. Extract the full MODELO(S)/VERSION(ES) value — everything between the
   row number and the 4-digit year in AÑO(S) column
3. Extract NO. DE MOTOR — the 11-character alphanumeric string
4. Extract NO. DE SERIE — the 17-character alphanumeric string
5. Skip everything else on that line
6. Move to the next row number

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
Reflects how clearly you could read the domicilio field and all table rows.
Set below 0.75 ONLY if the domicilio is missing or any motor/serie value is unreadable.
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
    Example: "Pulsar N160 Premium Azul 26" ->
             canonical="Pulsar N160 Premium", color="Azul", year="2026"

    Receives canonical_names list from caller queried from DB before loop.
    Matches longest canonical name at start of string.
    Remaining tokens: last is year suffix, middle is color.

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


def _find_matching_purchased_motorcycle(
    db: Session,
    model_id: int,
    dealership_id: int,
) -> Optional[Motorcycle]:
    """
    Finds the oldest purchased motorcycle matching model_id and dealership.
    Greedy by created_at — oldest unmatched record gets priority.
    model_id here refers to MotorcycleCatalog.model_id.
    """
    return db.query(Motorcycle).filter(
        Motorcycle.model_id      == model_id,
        Motorcycle.dealership_id == dealership_id,
        Motorcycle.status        == MotorcycleStatus.purchased,
    ).order_by(Motorcycle.created_at.asc()).first()


# ======================================================================== #
# Pipeline                                                                  #
# ======================================================================== #

def handle_order_confirmation(
    db: Session,
    submission: Submission,
    event: Event,
) -> tuple[bool, str]:
    """
    Pipeline for order_confirmation event.
    1.  Load PDF from disk.
    2.  Extract clean PDF text via pdfplumber.
    3.  Call Gemini for extraction.
    4.  Validate confidence and required fields.
    5.  Match domicilio to dealership via ilike.
    6.  Validate and auto-correct serie numbers against PDF ground truth.
    7.  Validate and auto-correct motor numbers against PDF ground truth.
    8.  Build canonical names list from catalog.
    9.  Parse model names — extract canonical name, color, year.
    10. Look up model_id from motorcycle_catalog — hard stop if not found.
    11. Create OrderConfirmationDocument row.
    12. Match each motorcycle to purchased record or create as not_purchased.
    13. Mark submission and event complete.
    """

    # ------------------------------------------------------------------ #
    # 1. Load PDF from disk                                               #
    # ------------------------------------------------------------------ #
    raw_path = submission.raw_file_path
    if not raw_path or not os.path.exists(raw_path):
        reason = "Archivo PDF no encontrado en disco."
        reject_submission(db, submission, reason)
        reject_event(db, event, reason)
        db.commit()
        return False, reason

    with open(raw_path, "rb") as f:
        pdf_bytes = f.read()

    # ------------------------------------------------------------------ #
    # 2. Extract clean PDF text for validation                            #
    # ------------------------------------------------------------------ #
    try:
        clean_pdf_text = extract_clean_pdf_text(pdf_bytes)
    except Exception as e:
        reason = f"Error al leer el PDF: {e}"
        reject_submission(db, submission, reason)
        reject_event(db, event, reason)
        db.commit()
        return False, reason

    # ------------------------------------------------------------------ #
    # 3. Call Gemini                                                       #
    # ------------------------------------------------------------------ #
    model  = get_model()
    prompt = _build_order_confirmation_prompt()

    try:
        raw_response, parsed_dict = call_gemini_pdf(model, prompt, pdf_bytes)
    except ValueError as e:
        reason = f"Error al procesar respuesta de IA: {e}"
        log_ai(db, submission.submission_id, "extraction", str(e), None, None, False)
        reject_submission(db, submission, reason)
        reject_event(db, event, reason)
        db.commit()
        return False, reason

    # ------------------------------------------------------------------ #
    # 4. Validate confidence and required fields                          #
    # ------------------------------------------------------------------ #
    confidence       = parsed_dict.get("overall_confidence")
    domicilio        = parsed_dict.get("domicilio_destino")
    motorcycles_data = parsed_dict.get("motorcycles", [])

    log_ai(
        db,
        submission.submission_id,
        "extraction",
        raw_response,
        parsed_dict,
        confidence,
        confidence is not None and confidence >= CONFIDENCE_THRESHOLD,
    )

    if confidence is None or confidence < CONFIDENCE_THRESHOLD:
        reason = f"Confianza insuficiente ({confidence}). Por favor sube un PDF más claro."
        reject_submission(db, submission, reason)
        reject_event(db, event, reason)
        db.commit()
        return False, reason

    if not domicilio:
        reason = "No se pudo extraer el domicilio de destino del documento."
        reject_submission(db, submission, reason)
        reject_event(db, event, reason)
        db.commit()
        return False, reason

    if not motorcycles_data:
        reason = "No se encontraron motocicletas en el documento."
        reject_submission(db, submission, reason)
        reject_event(db, event, reason)
        db.commit()
        return False, reason

    # ------------------------------------------------------------------ #
    # 5. Match domicilio to dealership via ilike                          #
    # ------------------------------------------------------------------ #
    dealership = db.query(Dealership).filter(
        Dealership.address.ilike(f"%{domicilio}%")
    ).first()

    if not dealership:
        reason = (
            f"Domicilio '{domicilio}' no encontrado en el sistema. "
            f"Verifica el catálogo de sucursales."
        )
        reject_submission(db, submission, reason)
        reject_event(db, event, reason)
        db.commit()
        return False, reason

    # ------------------------------------------------------------------ #
    # 6. Validate and auto-correct serie numbers                          #
    # ------------------------------------------------------------------ #
    remaining_text  = clean_pdf_text
    serie_corrected = []

    for i, moto in enumerate(motorcycles_data):
        raw_serie = moto.get("serie", "")

        corrected_serie, status, remaining_text = validate_and_correct_string(
            gemini_value    = raw_serie,
            expected_length = SERIE_LENGTH,
            remaining_text  = remaining_text,
        )

        if status == "ambiguous":
            reason = (
                f"Ambigüedad detectada en número de serie fila {i+1}: "
                f"'{raw_serie}' coincide con múltiples valores en el documento. "
                f"Por favor vuelve a subir el PDF."
            )
            reject_submission(db, submission, reason)
            reject_event(db, event, reason)
            db.commit()
            return False, reason

        if status == "not_found":
            reason = (
                f"Número de serie fila {i+1}: '{raw_serie}' no encontrado "
                f"en el documento. Por favor verifica el PDF."
            )
            reject_submission(db, submission, reason)
            reject_event(db, event, reason)
            db.commit()
            return False, reason

        serie_corrected.append(corrected_serie)

    # ------------------------------------------------------------------ #
    # 7. Validate and auto-correct motor numbers                          #
    # ------------------------------------------------------------------ #
    motor_corrected = []

    for i, moto in enumerate(motorcycles_data):
        raw_motor = moto.get("motor", "")

        corrected_motor, status, remaining_text = validate_and_correct_string(
            gemini_value    = raw_motor,
            expected_length = MOTOR_LENGTH,
            remaining_text  = remaining_text,
        )

        if status == "ambiguous":
            reason = (
                f"Ambigüedad detectada en número de motor fila {i+1}: "
                f"'{raw_motor}' coincide con múltiples valores en el documento. "
                f"Por favor vuelve a subir el PDF."
            )
            reject_submission(db, submission, reason)
            reject_event(db, event, reason)
            db.commit()
            return False, reason

        if status == "not_found":
            reason = (
                f"Número de motor fila {i+1}: '{raw_motor}' no encontrado "
                f"en el documento. Por favor verifica el PDF."
            )
            reject_submission(db, submission, reason)
            reject_event(db, event, reason)
            db.commit()
            return False, reason

        motor_corrected.append(corrected_motor)

    # ------------------------------------------------------------------ #
    # 8. Build canonical names list from catalog                          #
    # ------------------------------------------------------------------ #
    canonical_names = [
        row.canonical_name
        for row in db.query(MotorcycleCatalog.canonical_name).distinct().all()
    ]

    # ------------------------------------------------------------------ #
    # 9. Parse model names                                                #
    # ------------------------------------------------------------------ #
    parsed_models = []

    for i, moto in enumerate(motorcycles_data):
        raw_name = moto.get("modelo_version", "")
        canonical_name, color, year = _parse_model_name(raw_name, canonical_names)

        if not canonical_name:
            reason = (
                f"No se pudo identificar el modelo en fila {i+1}: "
                f"'{raw_name}'. Verifica el documento."
            )
            reject_submission(db, submission, reason)
            reject_event(db, event, reason)
            db.commit()
            return False, reason

        parsed_models.append({
            "canonical_name": canonical_name,
            "color":          color,
            "year":           year,
            "serie":          serie_corrected[i],
            "motor":          motor_corrected[i],
        })

    # ------------------------------------------------------------------ #
    # 10. Look up model_id from motorcycle_catalog                        #
    # ------------------------------------------------------------------ #
    resolved_models = []

    for i, parsed in enumerate(parsed_models):
        catalog_entry = db.query(MotorcycleCatalog).filter(
            MotorcycleCatalog.canonical_name == parsed["canonical_name"],
            MotorcycleCatalog.year           == parsed["year"],
        ).first()

        if not catalog_entry:
            reason = (
                f"Modelo '{parsed['canonical_name']}' año {parsed['year']} "
                f"no encontrado en el catálogo. Verifica el catálogo de modelos."
            )
            reject_submission(db, submission, reason)
            reject_event(db, event, reason)
            db.commit()
            return False, reason

        resolved_models.append({
            **parsed,
            "model_id": catalog_entry.model_id,
        })

    # ------------------------------------------------------------------ #
    # 11. Create OrderConfirmationDocument row                            #
    # ------------------------------------------------------------------ #
    order_conf_doc = OrderConfirmationDocument(
        submission_id = submission.submission_id,
        dealership_id = dealership.dealership_id,
        total_units   = len(resolved_models),
    )
    db.add(order_conf_doc)
    db.flush()

    # ------------------------------------------------------------------ #
    # 12. Match each motorcycle to purchased record or create             #
    #     as not_purchased                                                #
    # ------------------------------------------------------------------ #
    for resolved in resolved_models:
        existing = _find_matching_purchased_motorcycle(
            db,
            model_id      = resolved["model_id"],
            dealership_id = dealership.dealership_id,
        )

        if existing:
            existing.status               = MotorcycleStatus.incoming
            existing.reference_number     = resolved["serie"]
            existing.motor_number         = resolved["motor"]
            existing.color                = resolved["color"]
            existing.order_confirmation_id = order_conf_doc.order_confirmation_document_id
            db.flush()
        else:
            new_moto = Motorcycle(
                model_id               = resolved["model_id"],
                dealership_id          = dealership.dealership_id,
                reference_number       = resolved["serie"],
                motor_number           = resolved["motor"],
                color                  = resolved["color"],
                order_confirmation_id  = order_conf_doc.order_confirmation_document_id,
                status                 = MotorcycleStatus.not_purchased,
            )
            db.add(new_moto)
            db.flush()

    # ------------------------------------------------------------------ #
    # 13. Mark submission and event complete                              #
    # ------------------------------------------------------------------ #
    submission.status        = SubmissionStatus.complete
    submission.submitted_at  = datetime.now(timezone.utc)
    event.status             = EventStatus.complete
    event.completed_at       = datetime.now(timezone.utc)
    event.linked_entity_type = "ORDER_CONFIRMATION"

    db.flush()
    event.linked_entity_id = order_conf_doc.order_confirmation_document_id
    db.commit()

    total = len(resolved_models)
    return True, (
        f"Confirmación de pedido registrada exitosamente. "
        f"{total} motocicleta(s) procesada(s) para {dealership.name}."
    )