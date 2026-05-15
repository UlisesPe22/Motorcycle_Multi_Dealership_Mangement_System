"""
gemini_responses.py — Pydantic models for validating Gemini API responses.

Every Gemini response passes through one of these models before the pipeline
trusts it. If the response is missing required fields or has wrong types,
Pydantic raises a ValidationError which the pipeline catches and converts
into a submission rejection.

This is the anti-hallucination layer — it enforces the contract between
what we asked Gemini to return and what we actually received.
"""

from typing import Optional
from pydantic import BaseModel, field_validator


# ======================================================================== #
# Phase 1 — Identification                                                  #
# ======================================================================== #

class CornersModel(BaseModel):
    top_left:     list[float]
    top_right:    list[float]
    bottom_right: list[float]
    bottom_left:  list[float]

    @field_validator("top_left", "top_right", "bottom_right", "bottom_left")
    @classmethod
    def must_be_two_coords(cls, v):
        if len(v) != 2:
            raise ValueError("Each corner must have exactly 2 coordinates [x, y]")
        return v


class Phase1Response(BaseModel):
    is_match:         bool
    detected_side:    str
    corners:          Optional[CornersModel]
    confidence:       float
    user_message:     str



    @field_validator("detected_side")
    @classmethod
    def side_must_be_valid(cls, v):
        if v not in ("front", "back"):
            raise ValueError(f"detected_side must be 'front' or 'back', got '{v}'")
        return v

    @field_validator("confidence")
    @classmethod
    def confidence_must_be_in_range(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {v}")
        return v


# ======================================================================== #
# Phase 2 — Front extraction                                                #
# ======================================================================== #

class FieldValue(BaseModel):
    value:      Optional[str]
    confidence: float
    
class BoolFieldValue(BaseModel):
    value:      Optional[bool]
    confidence: float

class Phase2FrontFields(BaseModel):
    nombre_completo:  Optional[FieldValue] = None
    curp:             Optional[FieldValue] = None
    clave_de_elector: Optional[FieldValue] = None
    fecha_nacimiento: Optional[FieldValue] = None
    domicilio:        Optional[FieldValue] = None


class Phase2FrontResponse(BaseModel):
    fields:             Phase2FrontFields
    overall_confidence: float

    @field_validator("overall_confidence")
    @classmethod
    def confidence_must_be_in_range(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"overall_confidence must be between 0.0 and 1.0, got {v}")
        return v


# ======================================================================== #
# Phase 2 — Back extraction (MRZ)                                           #
# ======================================================================== #

class Phase2BackFields(BaseModel):
    mrz_line_1:        Optional[FieldValue] = None
    mrz_line_2:        Optional[FieldValue] = None
    mrz_line_3:        Optional[FieldValue] = None


class Phase2BackResponse(BaseModel):
    fields:             Phase2BackFields
    overall_confidence: float

    @field_validator("overall_confidence")
    @classmethod
    def confidence_must_be_in_range(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"overall_confidence must be between 0.0 and 1.0, got {v}")
        return v