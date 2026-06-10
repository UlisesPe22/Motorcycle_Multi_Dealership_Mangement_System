"""
unconfirmed_client.py — SQLAlchemy model for the `unconfirmed_clients` table.

Staging table for the client activation-via-email flow. A row lands here when
a vendor registers a client through the INE pipeline. The client is only
copied into the real `clients` table once they click the activation link sent
to their email (see routers/clients.py::activate_client).

Mirrors the clients table exactly, plus the verification columns
(confirmation_token, token_expires_at, status). registered_by is kept for
vendor fraud detection. No relationships — this is a short-lived staging row.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey

from database import Base


class UnconfirmedClient(Base):
    __tablename__ = "unconfirmed_clients"

    pending_client_id = Column(Integer, primary_key=True, autoincrement=True)

    # ------------------------------------------------------------------ #
    # Mirrors the clients table                                           #
    # ------------------------------------------------------------------ #
    nombre_completo  = Column(String, nullable=False)
    curp             = Column(String, nullable=False)
    clave_de_elector = Column(String, nullable=False)
    fecha_nacimiento = Column(String, nullable=False)
    domicilio        = Column(String, nullable=False)
    email            = Column(String, nullable=False)
    phone            = Column(String, nullable=True)

    front_submission_id = Column(Integer, ForeignKey("submissions.submission_id"), nullable=True)
    back_submission_id  = Column(Integer, ForeignKey("submissions.submission_id"), nullable=True)
    event_id            = Column(Integer, ForeignKey("events.event_id"),           nullable=True)
    registered_by       = Column(Integer, ForeignKey("users.user_id"),             nullable=False)
    registered_at       = Column(DateTime(timezone=True),                          nullable=False)

    # ------------------------------------------------------------------ #
    # Verification columns                                                #
    # ------------------------------------------------------------------ #
    confirmation_token = Column(String, unique=True,            nullable=False)
    token_expires_at   = Column(DateTime(timezone=True),        nullable=False)
    status             = Column(String, default="pending",      nullable=False)

    def __repr__(self):
        return (
            f"<UnconfirmedClient id={self.pending_client_id} "
            f"nombre={self.nombre_completo} status={self.status}>"
        )
