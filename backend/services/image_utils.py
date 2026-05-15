"""
image_utils.py — Image processing utilities.

Handles perspective warp using corners returned by Gemini Phase 1.
Corners are in normalised 0-1000 scale. We convert them to pixel
coordinates, apply OpenCV perspective transform, and save the result
at canonical 1012x638.
"""

import io
import os
import cv2
import numpy as np
from PIL import Image

from typing import Optional
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
    # Load image
    pil_img = load_image_as_pil(raw_image_path)
    cv2_img = pil_to_cv2(pil_img)
    h, w = cv2_img.shape[:2]

    # Convert normalised corners to pixel coordinates
    src_pts = normalise_corners(corners, w, h)

    # Destination points — the four corners of the canonical output size
    dst_pts = np.array([
        [0,                  0                 ],
        [CANONICAL_WIDTH - 1, 0                ],
        [CANONICAL_WIDTH - 1, CANONICAL_HEIGHT - 1],
        [0,                  CANONICAL_HEIGHT - 1],
    ], dtype=np.float32)

    # Compute perspective transform matrix
    M = cv2.getPerspectiveTransform(src_pts, dst_pts)

    # Apply warp
    warped = cv2.warpPerspective(cv2_img, M, (CANONICAL_WIDTH, CANONICAL_HEIGHT))

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Save result
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
    import io

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

    Args:
        gemini_value:    the string Gemini extracted
        expected_length: the fixed expected length of this string type
        remaining_text:  mutable pool — already matched strings should be
                         removed before calling this function

    Returns:
        (corrected_value, status, updated_remaining_text)

        status values:
          "exact"      — Gemini was correct, no correction needed
          "corrected"  — single character error found and auto-corrected
          "ambiguous"  — multiple candidates at distance 1, cannot safely correct
          "not_found"  — no candidate within distance 1, string too corrupt

        updated_remaining_text — pool with matched string consumed.
        If status is "ambiguous" or "not_found" the pool is unchanged.
    """
    clean_value = gemini_value.replace(" ", "").upper()

    # ------------------------------------------------------------------ #
    # Step 1 — exact match                                                #
    # ------------------------------------------------------------------ #
    if clean_value in remaining_text:
        updated = remaining_text.replace(clean_value, "", 1)
        return clean_value, "exact", updated

    # ------------------------------------------------------------------ #
    # Step 2 — find all substrings of expected_length at distance 1      #
    # ------------------------------------------------------------------ #
    candidates = set()
    for i in range(len(remaining_text) - expected_length + 1):
        substring = remaining_text[i:i + expected_length]
        if _levenshtein(clean_value, substring) == 1:
            candidates.add(substring)

    # ------------------------------------------------------------------ #
    # Step 3 — evaluate candidates                                        #
    # ------------------------------------------------------------------ #
    if len(candidates) == 1:
        corrected = candidates.pop()
        updated = remaining_text.replace(corrected, "", 1)
        return corrected, "corrected", updated

    elif len(candidates) > 1:
        return None, "ambiguous", remaining_text

    else:
        return None, "not_found", remaining_text