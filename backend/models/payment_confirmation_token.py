"""
payment_confirmation_token.py — SQLAlchemy model for `payment_confirmation_tokens`.

One row per PaymentEvent (payment_event_id is UNIQUE). Tracks the email
confirmation a client must click before the PaymentEvent's items count toward
Sale.amount_verified.

verification_source is intentionally present for phase 2 (bank statement
reconciliation). In phase 1 it is always 'email'. Do not remove it.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base


class PaymentConfirmationToken(Base):
    __tablename__ = "payment_confirmation_tokens"

    token_id         = Column(Integer, primary_key=True, autoincrement=True)
    payment_event_id = Column(
        Integer,
        ForeignKey("payment_events.payment_event_id"),
        unique=True,
        nullable=False,
    )
    token               = Column(String, unique=True,           nullable=False)
    expires_at          = Column(DateTime(timezone=True),       nullable=False)
    status              = Column(String, default="pending",     nullable=False)
    confirmed_at        = Column(DateTime(timezone=True),       nullable=True)
    verification_source = Column(String, default="email",       nullable=False)
    created_at          = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    event = relationship("PaymentEvent")

    def __repr__(self):
        return (
            f"<PaymentConfirmationToken id={self.token_id} "
            f"payment_event_id={self.payment_event_id} status={self.status}>"
        )
