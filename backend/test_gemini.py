
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Add backend/ to path so local imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import google.generativeai as genai
from PIL import Image


# ======================================================================== #
# Prompts                                                                   #
# ======================================================================== #

def build_phase1_prompt(expected_slot: str) -> str:
    """
    Phase 1 — Identification prompt.
    Tells Gemini which side to expect and asks it to validate,
    detect version, and return the 4 corner coordinates.

    expected_slot: "id_front" or "id_back"
    """
    side = "FRONT" if expected_slot == "id_front" else "BACK"

    return f"""
You are a document validator for a Mexican motorcycle dealership.
You must analyse the uploaded image and return ONLY a JSON object. No explanation, no markdown.

I am expecting the {side} side of a Mexican INE (Credencial para Votar) voter ID card.

Your task:
1. Confirm there is exactly ONE INE card visible in the image.
2. Confirm it is the {side} side specifically.
3. Identify the INE version: "2019" or "2014".
4. Detect the 4 corners of the card in the image.

Rules:
- If the image contains both sides, the wrong side, or is not an INE, set is_match to false.
- Corners must be in normalized coordinates where the full image width and height = 1000.
- Order corners as: top_left, top_right, bottom_right, bottom_left.
- confidence must reflect your certainty across ALL fields combined (0.0 to 1.0).
- user_message must be written in Spanish and be suitable to show directly to a dealership employee.

Return this exact JSON structure:
{{
  "is_match": true or false,
  "detected_side": "{side.lower()}",
  "detected_version": "2019" or "2014" or null,
  "corners": {{
    "top_left":     [x, y],
    "top_right":    [x, y],
    "bottom_right": [x, y],
    "bottom_left":  [x, y]
  }},
  "confidence": 0.0 to 1.0,
  "user_message": "message in Spanish"
}}
"""


def build_phase2_prompt(side: str, version: str, corners: dict) -> str:
    """
    Phase 2 — Data extraction prompt.
    Passes the corners from Phase 1 back to Gemini as spatial context
    so it focuses on the card area only.

    side:    "front" or "back"
    version: "2019" or "2014"
    corners: dict with top_left, top_right, bottom_right, bottom_left
    """
    tl = corners["top_left"]
    tr = corners["top_right"]
    br = corners["bottom_right"]
    bl = corners["bottom_left"]

    if side == "front":
        fields_instruction = """
Extract these fields from the FRONT of the card:
- nombre_completo: full name as printed
- curp: the CURP code (18 characters)
- clave_de_elector: the voter key code
- fecha_nacimiento: date of birth as printed
- domicilio: full address as printed
- vigencia: expiry year as printed
"""
    else:
        fields_instruction = """
Extract these fields from the BACK of the card:
- mrz_line_1: first MRZ line (full string, exactly as printed)
- mrz_line_2: second MRZ line (full string, exactly as printed)
- mrz_line_3: third MRZ line if present, otherwise null
- tiene_zona_firma: true if a handwritten signature zone is visible, false if not
"""

    return f"""
You are a document data extractor for a Mexican motorcycle dealership.
You must analyse the uploaded image and return ONLY a JSON object. No explanation, no markdown.

This is the {side.upper()} side of a Mexican INE version {version}.

The card corners in this image are located at these normalized coordinates (0-1000 scale):
  TL: {tl}
  TR: {tr}
  BR: {br}
  BL: {bl}

Use these corners to focus your extraction precisely on the card area.

{fields_instruction}

Rules:
- If a field is not visible or not applicable, return null for that field.
- Do not guess or invent values. If uncertain, return null.
- confidence must reflect your certainty across ALL extracted fields (0.0 to 1.0).
- Each field must also have its own individual confidence score.

Return this exact JSON structure:
{{
  "fields": {{
    "field_name": {{
      "value": "extracted value or null",
      "confidence": 0.0 to 1.0
    }}
  }},
  "overall_confidence": 0.0 to 1.0
}}
"""


# ======================================================================== #
# Helpers                                                                   #
# ======================================================================== #
def load_image(path: str):
    """Load image from disk path, return PIL Image.
    Converts MPO and other exotic formats to standard RGB JPEG
    so Gemini always receives a supported MIME type.
    """
    p = Path(path.strip().strip('"'))
    if not p.exists():
        raise FileNotFoundError(f"Image not found: {p}")
    img = Image.open(p)
    # Convert to RGB — drops MPO stereo layers, CMYK, palette modes etc.
    # Gemini supports image/jpeg, image/png, image/webp, image/heic only.
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img

def print_section(title: str):
    print(f"\n{'═' * 55}")
    print(f"  {title}")
    print(f"{'═' * 55}")


def print_json(data: dict):
    print(json.dumps(data, indent=2, ensure_ascii=False))


def call_gemini(model, prompt: str, image) -> dict:
    """
    Send prompt + image to Gemini.
    Forces image to standard JPEG bytes to avoid MPO/exotic format errors.
    Returns parsed JSON dict.
    """
    import io
    # Re-encode to standard JPEG bytes regardless of original format
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG")
    buffer.seek(0)
    jpeg_bytes = buffer.read()

    image_part = {
        "mime_type": "image/jpeg",
        "data": jpeg_bytes
    }

    response = model.generate_content([prompt, image_part])
    raw = response.text.strip()

    # Strip markdown fences if Gemini ignores response_mime_type
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"\n  Raw response was:\n{raw}")
        raise ValueError(f"Gemini returned invalid JSON: {e}")
# ======================================================================== #
# Main test flow                                                            #
# ======================================================================== #

def run_test():
    # ------------------------------------------------------------------ #
    # Setup                                                                #
    # ------------------------------------------------------------------ #
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("\n  ERROR: GEMINI_API_KEY not found in .env file.")
        sys.exit(1)

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.1,
        }
    )
    print("\n  ✓ Gemini client initialised.")

    # ------------------------------------------------------------------ # C:\Users\perez\Documents\moto_app\storage\submissions\raw\sub_2_id_back.jpg.jpeg
    # Get image path and slot from user  C:\Users\perez\Documents\moto_app\storage\submissions\raw\test.jpeg                                 #
    # ------------------------------------------------------------------ #
    print_section("IMAGE INPUT")
    print("  Paste the full path to your INE scan image.")
    print("  Example: C:\\Users\\perez\\Desktop\\ine_front.jpg\n")
    image_path = input("  Image path: ").strip().strip('"')

    print("\n  Which side is this image?")
    print("  1 = id_front")
    print("  2 = id_back")
    choice = input("  Enter 1 or 2: ").strip()
    expected_slot = "id_front" if choice == "1" else "id_back"

    # ------------------------------------------------------------------ #
    # Load image                                                           #
    # ------------------------------------------------------------------ #
    try:
        image = load_image(image_path)
        print(f"\n  ✓ Image loaded: {image.size[0]}x{image.size[1]} px")
    except FileNotFoundError as e:
        print(f"\n  ERROR: {e}")
        sys.exit(1)

    # ------------------------------------------------------------------ #
    # Phase 1 — Identification                                             #
    # ------------------------------------------------------------------ #
    print_section("PHASE 1 — IDENTIFICATION")
    print("  Sending to Gemini...\n")

    phase1_prompt = build_phase1_prompt(expected_slot)

    try:
        phase1_result = call_gemini(model, phase1_prompt, image)
    except ValueError as e:
        print(f"\n  ERROR: {e}")
        sys.exit(1)

    print("  Raw Gemini response:")
    print_json(phase1_result)

    # Evaluate Phase 1
    is_match   = phase1_result.get("is_match", False)
    confidence = phase1_result.get("confidence", 0.0)
    version    = phase1_result.get("detected_version")
    corners    = phase1_result.get("corners")
    msg        = phase1_result.get("user_message", "")

    print(f"\n  is_match:   {is_match}")
    print(f"  confidence: {confidence}")
    print(f"  version:    {version}")
    print(f"  message:    {msg}")

    if not is_match:
        print("\n  ✗ Phase 1 FAILED — is_match is false.")
        print(f"  Reason: {msg}")
        sys.exit(0)

    if confidence < 0.95:
        print(f"\n  ✗ Phase 1 FAILED — confidence {confidence} is below 0.95 threshold.")
        sys.exit(0)

    if not corners:
        print("\n  ✗ Phase 1 FAILED — no corners returned.")
        sys.exit(0)

    print("\n  ✓ Phase 1 PASSED")

    # ------------------------------------------------------------------ #
    # Phase 2 — Data Extraction                                            #
    # ------------------------------------------------------------------ #
    print_section("PHASE 2 — DATA EXTRACTION")
    print("  Sending to Gemini...\n")

    side = "front" if expected_slot == "id_front" else "back"
    phase2_prompt = build_phase2_prompt(side, version, corners)

    try:
        phase2_result = call_gemini(model, phase2_prompt, image)
    except ValueError as e:
        print(f"\n  ERROR: {e}")
        sys.exit(1)

    print("  Raw Gemini response:")
    print_json(phase2_result)

    overall = phase2_result.get("overall_confidence", 0.0)
    fields  = phase2_result.get("fields", {})

    print(f"\n  Overall confidence: {overall}")
    print(f"\n  Extracted fields:")
    for field_name, field_data in fields.items():
        value      = field_data.get("value")
        field_conf = field_data.get("confidence", 0.0)
        flag = "✓" if field_conf >= 0.95 else "⚠"
        print(f"    {flag} {field_name}: {value!r}  (conf: {field_conf})")

    if overall < 0.95:
        print(f"\n  ⚠ Overall confidence {overall} is below 0.95 threshold.")
        print("    In the real pipeline this submission would be rejected.")
    else:
        print("\n  ✓ Phase 2 PASSED")

    # ------------------------------------------------------------------ #
    # Summary                                                              #
    # ------------------------------------------------------------------ #
    print_section("SUMMARY")
    print(f"  Image:      {image_path}")
    print(f"  Slot:       {expected_slot}")
    print(f"  Version:    {version}")
    print(f"  P1 passed:  {is_match and confidence >= 0.95}")
    print(f"  P2 passed:  {overall >= 0.95}")
    print()


if __name__ == "__main__":
    run_test()