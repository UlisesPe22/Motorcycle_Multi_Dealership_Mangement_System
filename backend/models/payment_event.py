from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class PaymentEvent(Base):
    __tablename__ = "payment_events"

    payment_event_id = Column(Integer, primary_key=True, autoincrement=True)
    sale_id          = Column(Integer, ForeignKey("sales.sale_id"),       nullable=False)
    event_type       = Column(String,                                      nullable=False)
    status           = Column(String,  default="pending",                  nullable=False)
    expected_amount  = Column(Float,                                       nullable=True)
    created_by       = Column(Integer, ForeignKey("users.user_id"),        nullable=False)
    created_at       = Column(DateTime, server_default=func.now(),         nullable=False)

    sale    = relationship("Sale",        back_populates="events")
    creator = relationship("User",        foreign_keys=[created_by])
    items   = relationship("PaymentItem", back_populates="event",
                           cascade="all, delete-orphan",
                           order_by="PaymentItem.created_at")
