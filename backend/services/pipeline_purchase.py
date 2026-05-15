import os
import shutil
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from config import STORAGE_ROOT, CONFIDENCE_THRESHOLD, MODELO_CODE_LENGTH 
from models.event import Event, EventStatus
from models.submission import Submission, SubmissionStatus
from models.motorcycle import Motorcycle, MotorcycleStatus
from models.purchase_document import PurchaseDocument
from models.dealership import Dealership
from models.motorcycle_model_code import MotorcycleModelCode
from services.main_pipeline import (
    get_model,
    call_gemini_pdf,
    log_ai,
    reject_submission,
    reject_event,
)
from services.image_utils import extract_clean_pdf_text, validate_and_correct_string
from models.motorcycle_catalog import MotorcycleCatalog
# ======================================================================== #
# Prompt                                                                    #
# ======================================================================== #
def _build_purchase_prompt() -> str:
    return """
You are a data extraction robot processing a Mexican motorcycle purchase order PDF.
The document is in Spanish.
Return ONLY a valid JSON object. No explanation, no markdown, no text outside the JSON.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 1 — EXTRACT HEADER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Find these two fields in the document header area (top of the page):

- "sucursal": the value that appears on the same line as the word "Sucursal".
  Copy it exactly as written.

- "fecha_documento": the date that appears on the same line as
  "Fecha del Documento". Format it as DD/MM/YY.
  Example: if the document says "30-03-2026" output "30/03/26"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2 — EXTRACT MOTORCYCLE ROWS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The table has many columns. You must extract ONLY two values per row:
the Modelo code and the Cantidad. Everything else must be ignored.

HOW TO IDENTIFY A VALID DATA ROW:
A valid row always contains a Modelo code. A Modelo code has these properties:
- It is a single continuous string with NO spaces
- It contains only letters (A-Z), numbers (0-9), and hyphens (-)
- It ALWAYS ends with exactly two digits followed by the letters "DI"
- Examples of valid Modelo codes: "P125N-PU26DI", "D250UGNE26DI", "P160CAPE26DI"
- If a string does not end in [two digits + DI] it is NOT a Modelo code

HOW TO EXTRACT CANTIDAD FOR EACH ROW:
- Cantidad always appears as a decimal number written as X.00
  Examples: 1.00, 2.00, 3.00
- It is always a small number between 1 and 20
- It is the FIRST standalone X.00 decimal that appears after the Modelo code
  on the same line
- Convert it to integer: 1.00 becomes 1, 3.00 becomes 3
- WARNING: numbers like "125", "160", "250", "26", "25" that appear inside
  the Modelo code or elsewhere are NOT cantidad — ignore them

LINES TO SKIP COMPLETELY:
- Any line that contains ONLY numbers, decimals, commas, and spaces with no letters
  Example: "103,527.46 14,279.65" — SKIP THIS, it is wrapped financial data
- Any line that does not contain a Modelo code pattern ending in [digits]DI
- Header lines with column titles
- Footer lines with totals or signatures

EXTRACTION PROCESS — repeat for every valid row:
1. Find the next Modelo code (ends in [digits]DI, no spaces)
2. Extract it exactly as written
3. Find the first X.00 decimal after it on the same line
4. Convert to integer and extract as cantidad
5. Skip everything else on that line
6. Move to the next Modelo code

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Return this exact JSON and nothing else:
{
  "sucursal": "string",
  "fecha_documento": "DD/MM/YY",
  "motorcycles": [
    {
      "modelo": "string",
      "cantidad": 1
    }
  ],
  "overall_confidence": 0.0
}

overall_confidence: float between 0.0 and 1.0.
Reflects how clearly you could read the header fields and all Modelo codes.
Set below 0.75 ONLY if a header field is missing or a Modelo code is unreadable.
Skipping wrapped financial lines does NOT lower confidence.
"""


# ======================================================================== #
# Pipeline                                                                  #
# ======================================================================== #
def handle_purchase_order(
    db: Session,
    submission: Submission,
    event: Event,
) -> tuple[bool, str]:
    """
    Pipeline for purchase_order event.
    1.  Read PDF bytes from disk.
    2.  Extract clean PDF text via pdfplumber for validation.
    3.  Call Gemini for extraction.
    4.  Validate confidence and required fields.
    5.  Validate and auto-correct modelo codes against PDF ground truth.
    6.  Look up catalog entries — hard stop if any code not in DB.
    7.  Match sucursal to dealership_id.
    8.  Copy PDF to purchase_documents/raw/.
    9.  Create PurchaseDocument row.
    10. Create one Motorcycle row per unit (quantity expansion).
    11. Mark submission and event complete.
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
    prompt = _build_purchase_prompt()

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
    sucursal         = parsed_dict.get("sucursal")
    fecha            = parsed_dict.get("fecha_documento")
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

    if not sucursal:
        reason = "No se pudo extraer el campo Sucursal del documento."
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
    # 5. Validate and auto-correct modelo codes against PDF ground truth  #
    # ------------------------------------------------------------------ #
    remaining_text = clean_pdf_text
    corrected_motorcycles = []

    for moto in motorcycles_data:
        raw_code = moto.get("modelo", "")

        corrected_code, status, remaining_text = validate_and_correct_string(
            gemini_value    = raw_code,
            expected_length = MODELO_CODE_LENGTH,
            remaining_text  = remaining_text,
        )

        if status == "ambiguous":
            reason = (
                f"Ambigüedad detectada en el código de modelo '{raw_code}'. "
                f"El código coincide con múltiples valores en el documento. "
                f"Por favor vuelve a subir el PDF."
            )
            reject_submission(db, submission, reason)
            reject_event(db, event, reason)
            db.commit()
            return False, reason

        if status == "not_found":
            reason = (
                f"El código de modelo '{raw_code}' no fue encontrado en el documento. "
                f"Por favor verifica que el PDF es correcto."
            )
            reject_submission(db, submission, reason)
            reject_event(db, event, reason)
            db.commit()
            return False, reason

        corrected_motorcycles.append({
            **moto,
            "modelo": corrected_code,
        })

    # ------------------------------------------------------------------ #
    # 6. Look up catalog entries — hard stop if any code not in DB        #
    # ------------------------------------------------------------------ #
    resolved = []
    for moto in corrected_motorcycles:
        code = moto["modelo"]
        code_entry = db.query(MotorcycleModelCode).filter(MotorcycleModelCode.modelo_code == code).first()

        catalog_entry = code_entry.model if code_entry else None

        if not catalog_entry:
            reason = (
                f"El código '{code}' no existe en el catálogo de modelos. "
                f"Por favor actualiza el catálogo antes de procesar este pedido."
            )
            reject_submission(db, submission, reason)
            reject_event(db, event, reason)
            db.commit()
            return False, reason

        resolved.append({
            **moto,
            "catalog_entry": catalog_entry,
        })

    # ------------------------------------------------------------------ #
    # 7. Match sucursal to dealership                                     #
    # ------------------------------------------------------------------ #
    dealership = db.query(Dealership).filter(
        Dealership.name == sucursal
    ).first()

    if not dealership:
        reason = (
            f"Sucursal '{sucursal}' no encontrada en el sistema. "
            f"Verifica el catálogo de sucursales."
        )
        reject_submission(db, submission, reason)
        reject_event(db, event, reason)
        db.commit()
        return False, reason    

    # ------------------------------------------------------------------ #
    # 8. Copy PDF to purchase_documents/raw/                              #
    # ------------------------------------------------------------------ #
    dest_folder = os.path.join(STORAGE_ROOT, "purchase_documents", "raw")
    os.makedirs(dest_folder, exist_ok=True)
    dest_path = os.path.join(
        dest_folder, f"orden_de_compra_{submission.submission_id}.pdf"
    )

    try:
        shutil.copy2(raw_path, dest_path)
    except Exception as e:
        reason = f"Error al guardar el archivo: {e}"
        reject_submission(db, submission, reason)
        reject_event(db, event, reason)
        db.commit()
        return False, reason

    # ------------------------------------------------------------------ #
    # 9. Count total units and create PurchaseDocument row               #
    # ------------------------------------------------------------------ #
    total_units = sum(
        int(m.get("cantidad", 0))
        for m in resolved
        if m.get("cantidad")
    )

    purchase_doc = PurchaseDocument(
        submission_id        = submission.submission_id,
        dealership_id        = dealership.dealership_id,
        normalised_file_path = dest_path,
        order_date           = fecha,
        total_units          = total_units,
    )
    db.add(purchase_doc)
    db.flush()

    # ------------------------------------------------------------------ #
    # 10. Create one Motorcycle row per unit (quantity expansion)         #
    # ------------------------------------------------------------------ #
    for moto in resolved:
        cantidad      = int(moto.get("cantidad", 0))
        catalog_entry = moto["catalog_entry"]
        for _ in range(cantidad):
            motorcycle = Motorcycle(
                purchase_document_id = purchase_doc.purchase_document_id,
                dealership_id        = dealership.dealership_id,
                model_id             = catalog_entry.model_id,
                status               = MotorcycleStatus.purchased,
            )
            db.add(motorcycle)

    # ------------------------------------------------------------------ #
    # 11. Mark submission and event complete                              #
    # ------------------------------------------------------------------ #
    submission.status        = SubmissionStatus.complete
    submission.submitted_at  = datetime.now(timezone.utc)
    event.status             = EventStatus.complete
    event.completed_at       = datetime.now(timezone.utc)
    event.linked_entity_type = "PURCHASE_DOCUMENT"

    db.flush()
    event.linked_entity_id = purchase_doc.purchase_document_id
    db.commit()

    return True, (
        f"Pedido registrado exitosamente. "
        f"{total_units} motocicleta(s) registrada(s) en sucursal {sucursal}."
    )