import os
import shutil

from sqlalchemy.orm import Session

from config import STORAGE_ROOT, MODELO_CODE_LENGTH
from models.event import Event
from models.submission import Submission
from models.motorcycle import Motorcycle, MotorcycleStatus
from models.purchase_document import PurchaseDocument
from models.dealership import Dealership
from models.motorcycle_model_code import MotorcycleModelCode
from models.motorcycle_catalog import MotorcycleCatalog
from services.main_pipeline import (
    get_model,
    call_gemini_pdf,
    log_ai,
)
from services.pipeline_utils import (
    reject_and_return,
    check_confidence,
    load_pdf_with_text,
    validate_string_list,
    mark_complete,
)


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
    1.  Read PDF bytes from disk and extract clean text.
    2.  Call Gemini for extraction.
    3.  Validate confidence and required fields.
    4.  Validate and auto-correct modelo codes against PDF ground truth.
    5.  Look up catalog entries — hard stop if any code not in DB.
    6.  Match sucursal to dealership_id.
    7.  Copy PDF to purchase_documents/raw/.
    8.  Create PurchaseDocument row.
    9.  Create one Motorcycle row per unit (quantity expansion).
    10. Mark submission and event complete.
    """

    # ------------------------------------------------------------------ #
    # 1. Load PDF from disk and extract clean text                        #
    # ------------------------------------------------------------------ #
    pdf_bytes, remaining_text, err = load_pdf_with_text(
        db, submission, event, submission.raw_file_path
    )
    if err: return err

    # ------------------------------------------------------------------ #
    # 2. Call Gemini                                                       #
    # ------------------------------------------------------------------ #
    model  = get_model()
    prompt = _build_purchase_prompt()

    try:
        raw_response, parsed_dict = call_gemini_pdf(model, prompt, pdf_bytes)
    except ValueError as e:
        reason = f"Error al procesar respuesta de IA: {e}"
        log_ai(db, submission.submission_id, "extraction", str(e), None, None, False)
        return reject_and_return(db, submission, event, reason)

    # ------------------------------------------------------------------ #
    # 3. Validate confidence and required fields                          #
    # ------------------------------------------------------------------ #
    confidence       = parsed_dict.get("overall_confidence")
    sucursal         = parsed_dict.get("sucursal")
    fecha            = parsed_dict.get("fecha_documento")
    motorcycles_data = parsed_dict.get("motorcycles", [])

    ok, msg = check_confidence(
        db, submission, event, confidence,
        "extraction", raw_response, parsed_dict,
    )
    if not ok: return ok, msg

    if not sucursal:
        reason = "No se pudo extraer el campo Sucursal del documento."
        return reject_and_return(db, submission, event, reason)

    if not motorcycles_data:
        reason = "No se encontraron motocicletas en el documento."
        return reject_and_return(db, submission, event, reason)

    # ------------------------------------------------------------------ #
    # 4. Validate and auto-correct modelo codes against PDF ground truth  #
    # ------------------------------------------------------------------ #
    corrected_codes, remaining_text, err = validate_string_list(
        db, submission, event,
        motorcycles_data, "modelo", "código de modelo",
        MODELO_CODE_LENGTH, remaining_text,
    )
    if err: return err

    corrected_motorcycles = [
        {**moto, "modelo": code}
        for moto, code in zip(motorcycles_data, corrected_codes)
    ]

    # ------------------------------------------------------------------ #
    # 5. Look up catalog entries — hard stop if any code not in DB        #
    # ------------------------------------------------------------------ #
    resolved = []
    for moto in corrected_motorcycles:
        code = moto["modelo"]
        code_entry = db.query(MotorcycleModelCode).filter(
            MotorcycleModelCode.modelo_code == code
        ).first()

        catalog_entry = code_entry.model if code_entry else None

        if not catalog_entry:
            reason = (
                f"El código '{code}' no existe en el catálogo de modelos. "
                f"Por favor actualiza el catálogo antes de procesar este pedido."
            )
            return reject_and_return(db, submission, event, reason)

        resolved.append({**moto, "catalog_entry": catalog_entry})

    # ------------------------------------------------------------------ #
    # 6. Match sucursal to dealership                                     #
    # ------------------------------------------------------------------ #
    dealership = db.query(Dealership).filter(
        Dealership.name == sucursal
    ).first()

    if not dealership:
        reason = (
            f"Sucursal '{sucursal}' no encontrada en el sistema. "
            f"Verifica el catálogo de sucursales."
        )
        return reject_and_return(db, submission, event, reason)

    # ------------------------------------------------------------------ #
    # 7. Copy PDF to purchase_documents/raw/                              #
    # ------------------------------------------------------------------ #
    dest_folder = os.path.join(STORAGE_ROOT, "purchase_documents", "raw")
    os.makedirs(dest_folder, exist_ok=True)
    dest_path = os.path.join(
        dest_folder, f"orden_de_compra_{submission.submission_id}.pdf"
    )

    try:
        shutil.copy2(submission.raw_file_path, dest_path)
    except Exception as e:
        reason = f"Error al guardar el archivo: {e}"
        return reject_and_return(db, submission, event, reason)

    # ------------------------------------------------------------------ #
    # 8. Count total units and create PurchaseDocument row               #
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
    # 9. Create one Motorcycle row per unit (quantity expansion)          #
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
    # 10. Mark submission and event complete                              #
    # ------------------------------------------------------------------ #
    mark_complete(
        db, submission, event,
        "PURCHASE_DOCUMENT", purchase_doc.purchase_document_id,
    )

    return True, (
        f"Pedido registrado exitosamente. "
        f"{total_units} motocicleta(s) registrada(s) en sucursal {sucursal}."
    )
