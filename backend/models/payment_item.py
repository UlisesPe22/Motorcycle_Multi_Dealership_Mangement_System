from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class PaymentItem(Base):
    __tablename__ = "payment_items"

    payment_item_id   = Column(Integer, primary_key=True, autoincrement=True)
    payment_event_id  = Column(Integer, ForeignKey("payment_events.payment_event_id"), nullable=False)
    amount            = Column(Float,                                                   nullable=False)
    method_id         = Column(Integer, ForeignKey("payment_methods.method_id"),        nullable=False)
    financiera_id     = Column(Integer, ForeignKey("credit_institutions.credit_institution_id"), nullable=True)
    reference_input   = Column(String,                                                  nullable=True)
    status            = Column(String,  default="open",                                 nullable=False)
    created_at        = Column(DateTime, server_default=func.now(),                     nullable=False)

    event      = relationship("PaymentEvent",    back_populates="items")
    method     = relationship("PaymentMethod",   back_populates="items")
    financiera = relationship("CreditInstitution")
