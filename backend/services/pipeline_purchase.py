import os
import shutil

from sqlalchemy.orm import Session

from config import STORAGE_ROOT
from models.event import Event
from models.submission import Submission
from models.motorcycle import Motorcycle, MotorcycleStatus
from models.purchase_document import PurchaseDocument
from models.dealership import Dealership
from models.motorcycle_model_code import MotorcycleModelCode
from services.main_pipeline import (
    get_model,
    call_gemini_text,
    log_ai,
)
from services.pipeline_utils import (
    reject_and_return,
    check_confidence,
    extract_raw_pdf_text,
    is_valid_modelo_code,
    is_valid_cantidad,
    mark_complete,
)
# ======================================================================== #
# Prompt                                                                    #
# ======================================================================== #
def _build_purchase_prompt() -> str:
    return """
You are a data extraction robot processing the plain text of a Mexican motorcycle
purchase order (Orden de Compra de Vehículos). The text was extracted from a PDF
using pdfplumber and is provided at the end of these instructions.
Return ONLY a valid JSON object. No explanation, no markdown, no text outside the JSON.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 1 — EXTRACT HEADER FIELDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Find these two fields in the header lines at the top of the text:

- "sucursal": the value that appears after "Sucursal :" on the same line.
  That line also contains "Nombre del documento :" followed by a document code.
  Extract ONLY the dealership name — stop before "Nombre del documento".
  Example: from "Sucursal : BAJAJ TLALPIZAHUAC Nombre del documento : VPOC000..."
  extract only "BAJAJ TLALPIZAHUAC"

- "fecha_documento": the date that appears after "Fecha del documento :" on the
  same line. That line also contains "No. de Referencia :".
  Format the date as DD/MM/YY.
  Example: "29-04-2026" → "29/04/26"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2 — EXTRACT MOTORCYCLE TABLE ROWS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Each valid data row in the table follows this pattern on a single line:
<row_number> <MODELO_CODE> <model name words> <CANTIDAD> <financial data>

You must extract ONLY two values per row: the MODELO code and the CANTIDAD.

HOW TO IDENTIFY THE MODELO CODE:
- It is the first token after the row number
- It is a single continuous string with NO spaces
- It contains only letters (A-Z), numbers (0-9), and hyphens (-)
- It ALWAYS ends with exactly two digits followed by "DI"
- Examples: "P125NCCI26DI", "D400UGNE26DI", "P250N-PE26DI", "P160NPRO26DI"
- If a token does not end in [two digits + DI] it is NOT a modelo code

HOW TO IDENTIFY CANTIDAD:
- It is the first number written as exactly X.00 (two decimal zeros) after the
  MODELO code on the same line
- Examples of valid cantidad: 1.00, 2.00, 3.00
- Convert to integer: 1.00 → 1, 3.00 → 3
- WARNING: prices like 24,913.06 or 3,986.09 contain non-zero decimals and
  commas — they are NOT cantidad and must be completely ignored
- WARNING: the number 0.00 is a discount or tax field, not cantidad — skip it
- The cantidad is always a small whole number between 1 and 20

LINES TO SKIP COMPLETELY:
- Any line that does not contain a MODELO code ending in [digits]DI
- Lines containing only numbers, decimals, or commas with no letters
  Example: "11,489.5" or "4" — these are financial overflow lines, skip them
- The header line: "S. NO. Modelo Nombre del Modelo Cantidad Descuento..."
- The header line: "Precio Cantidad" or "Unitario Cancelada"
- Footer lines: "TOTAL AMOUNT", "Importe en Palabras", "Firma", "Printed On",
  "Por ANAYELI", "THANKS FOR DOING"

EXTRACTION PROCESS — repeat for every valid row:
1. Find the next line that contains a MODELO code (ends in [digits]DI, no spaces)
2. Extract the MODELO code exactly as written
3. Find the first X.00 value after the code — this is cantidad
4. Convert cantidad to integer
5. Skip all other values on that line
6. Move to the next line containing a MODELO code

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
Since you are reading clean extracted text, confidence should be high when
all rows and header fields are clearly identifiable.
Set below 0.75 ONLY if the sucursal field is missing or any modelo code
cannot be identified with certainty.
Lines containing only numbers that appear between data rows are financial
overflow lines and should NOT lower your confidence.

DOCUMENT TEXT:
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
    1.  Load PDF bytes from disk.
    2.  Call Gemini for extraction.
    3.  Validate confidence and required fields.
    4.  Structural validation of extracted modelo codes and cantidades.
    5.  Look up catalog entries — hard stop if any code not in DB.
    6.  Match sucursal to dealership_id.
    7.  Copy PDF to purchase_documents/raw/.
    8.  Create PurchaseDocument row.
    9.  Create one Motorcycle row per unit (quantity expansion).
    10. Mark submission and event complete.
    """

    # ------------------------------------------------------------------ #
    # 1. Load PDF bytes from disk                                         #
    # ------------------------------------------------------------------ #
    if not submission.raw_file_path or not os.path.exists(submission.raw_file_path):
        return reject_and_return(db, submission, event, "Archivo PDF no encontrado en disco.")

    with open(submission.raw_file_path, "rb") as f:
        pdf_bytes = f.read()

    raw_text = extract_raw_pdf_text(pdf_bytes)

    # ------------------------------------------------------------------ #
    # 2. Call Gemini                                                       #
    # ------------------------------------------------------------------ #
    model  = get_model()
    prompt = _build_purchase_prompt()

    try:
        raw_response, parsed_dict = call_gemini_text(model, prompt, raw_text)
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

    print(f"[GEMINI CONFIDENCE] {confidence}")

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
    # 4. Structural validation of extracted modelo codes and cantidades   #
    # ------------------------------------------------------------------ #
    for i, moto in enumerate(motorcycles_data):
        code     = moto.get("modelo", "")
        cantidad = moto.get("cantidad")
        if not is_valid_modelo_code(code):
            reason = (
                f"Fila {i + 1}: el código de modelo '{code}' no tiene el formato "
                f"esperado. Debe tener exactamente 12 caracteres, contener solo "
                f"letras, números y guiones, y terminar en dos dígitos seguidos de 'DI'."
            )
            return reject_and_return(db, submission, event, reason)
        if not is_valid_cantidad(cantidad):
            reason = (
                f"Fila {i + 1}: la cantidad '{cantidad}' no es válida. "
                f"Debe ser un número entero entre 1 y 99."
            )
            return reject_and_return(db, submission, event, reason)

    # ------------------------------------------------------------------ #
    # 5. Look up catalog entries — hard stop if any code not in DB        #
    # ------------------------------------------------------------------ #
    resolved = []
    for moto in motorcycles_data:
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
