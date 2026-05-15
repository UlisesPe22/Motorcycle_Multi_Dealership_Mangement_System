"""
submission.py — SQLAlchemy model for the `submissions` table.

A Submission represents one physical document slot within an Event.
For a client_registration event there are always exactly 2 submissions:
  slot 1 → id_front
  slot 2 → id_back

State machine for SubmissionStatus:
  pending    → processing  (file uploaded, pipeline starts)
  processing → matched     (Phase 1 passed, template resolved,
                            normalised image saved)
  matched    → complete    (Phase 2 extraction done)
  processing → rejected    (Phase 1 failed: wrong doc, low confidence)
  matched    → rejected    (cross-validation failed: version mismatch,
                            MRZ does not match front, etc.)

Key columns:
  raw_file_path         — path to the original upload, never modified.
  normalised_image_path — path to the OpenCV perspective-corrected image
                          saved at canonical 1012×638. Displayed in the UI
                          and its coordinates reused in Phase 2 prompts.
  template_id           — NULL on creation. Resolved after Phase 1 by
                          querying document_templates WHERE
                          ine_version = gemini_detected_version
                          AND side    = gemini_detected_side.
  gemini_detected_version — raw string Gemini returned ("2019" | "2014").
                            Stored separately from template_id so we can
                            audit what the model said vs what we resolved.
  gemini_detected_side    — raw string Gemini returned ("front" | "back").
  rejection_reason        — Spanish string shown to the user. Set by Gemini
                            (Phase 1 failure) or by our cross-validation
                            logic (version mismatch, field mismatch, etc.).

SlotName enum is imported from event.py — it is part of the event system
definition and must not be duplicated here.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, DateTime,
    ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship

from database import Base
from models.event import SlotName   # single source of truth for slot names


class SubmissionStatus(str, enum.Enum):
    """
    Lifecycle states for a single document submission.
    """
    pending    = "pending"     # row created, no file uploaded yet
    processing = "processing"  # file uploaded, Gemini Phase 1 running
    matched    = "matched"     # Phase 1 passed, template resolved,
                               # normalised image saved
    complete   = "complete"    # Phase 2 extraction done, all fields saved
    rejected   = "rejected"    # permanent failure at any stage


class Submission(Base):
    __tablename__ = "submissions"

    # ------------------------------------------------------------------ #
    # Primary key                                                          #
    # ------------------------------------------------------------------ #
    submission_id = Column(Integer, primary_key=True, autoincrement=True)

    # ------------------------------------------------------------------ #
    # Foreign keys                                                         #
    # ------------------------------------------------------------------ #
    event_id = Column(
        Integer,
        ForeignKey("events.event_id"),
        nullable=False
    )
    # ------------------------------------------------------------------ #
    # Slot metadata                                                        #
    # ------------------------------------------------------------------ #
    slot_number = Column(Integer, nullable=False)
    slot_name   = Column(
        SAEnum(SlotName, name="slot_name_enum"),
        nullable=False
    )

    # ------------------------------------------------------------------ #
    # Status                                                               #
    # ------------------------------------------------------------------ #
    status = Column(
        SAEnum(SubmissionStatus, name="submission_status_enum"),
        nullable=False,
        default=SubmissionStatus.pending
    )
    rejection_reason = Column(String, nullable=True)

    # ------------------------------------------------------------------ #
    # File paths                                                           #
    # ------------------------------------------------------------------ #
    raw_file_path         = Column(String, nullable=True)  # original upload
    normalised_image_path = Column(String, nullable=True)  # post-OpenCV warp

    # ------------------------------------------------------------------ #
    # Gemini detection metadata                                            #
    # Stored as plain strings so we can audit AI output independently     #
    # of our own template resolution logic.                               #
    # ------------------------------------------------------------------ #
    gemini_detected_side    = Column(String, nullable=True)  # "front" | "back"

    # ------------------------------------------------------------------ #
    # Timestamps                                                           #
    # ------------------------------------------------------------------ #
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    created_at   = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    # ------------------------------------------------------------------ #
    # Relationships                                                        #
    # ------------------------------------------------------------------ #
    event = relationship("Event", back_populates="submissions")


    ai_logs = relationship(
        "AIAnalysisLog",
        back_populates="submission",
        cascade="all, delete-orphan"
        # Deleting a submission removes all its Gemini call logs.
        # This keeps the DB clean when a submission is retried from scratch.
    )

    def __repr__(self) -> str:
        return (
            f"<Submission id={self.submission_id} "
            f"event={self.event_id} "
            f"slot={self.slot_name} "
            f"status={self.status}>"
        )