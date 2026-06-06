"""
client.py — SQLAlchemy model for the `clients` table.

A Client record is created only after a complete successful pipeline run:
  - Both submissions (front + back) reached status=complete
  - All cross-validation checks passed
  - MRZ data matched front data

Fields come from Phase 2 Gemini extraction of the INE front.
MRZ lines are NOT stored here — they live in ai_analysis_log as raw
extraction data and are only used during cross-validation.

signature_image_path is NULL for now. Phase 3 (signature extraction)
will populate it in a future implementation.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from database import Base


class Client(Base):
    __tablename__ = "clients"

    # ------------------------------------------------------------------ #
    # Primary key                                                          #
    # ------------------------------------------------------------------ #
    client_id = Column(Integer, primary_key=True, autoincrement=True)

    # ------------------------------------------------------------------ #
    # Extracted fields from INE front                                      #
    # ------------------------------------------------------------------ #
    nombre_completo   = Column(String, nullable=False)
    curp              = Column(String, nullable=False, unique=True)
    clave_de_elector  = Column(String, nullable=False, unique=True)
    fecha_nacimiento  = Column(String, nullable=True)   # stored as string
                                                         # as printed on card
    domicilio         = Column(String, nullable=True)
    email             = Column(String, unique=True, nullable=True)
    phone             = Column(String, nullable=True)

    # ------------------------------------------------------------------ #
    # Traceability FKs — link back to the documents that created this     #
    # ------------------------------------------------------------------ #
    front_submission_id = Column(Integer, ForeignKey("submissions.submission_id"), nullable=False)
    back_submission_id  = Column(Integer, ForeignKey("submissions.submission_id"), nullable=False)
    event_id            = Column(Integer, ForeignKey("events.event_id"),           nullable=False)
    registered_by       = Column(Integer, ForeignKey("users.user_id"),             nullable=False)

    # ------------------------------------------------------------------ #
    # Timestamp                                                            #
    # ------------------------------------------------------------------ #
    registered_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    # ------------------------------------------------------------------ #
    # Relationships                                                        #
    # ------------------------------------------------------------------ #
    front_submission = relationship("Submission", foreign_keys=[front_submission_id])
    back_submission  = relationship("Submission", foreign_keys=[back_submission_id])
    event            = relationship("Event")
    registered_by_user = relationship("User", foreign_keys=[registered_by])
    reservations     = relationship("Reservation", back_populates="client")
    sales            = relationship("Sale", back_populates="client")

    def __repr__(self):
        return f"<Client id={self.client_id} nombre={self.nombre_completo} curp={self.curp}>"