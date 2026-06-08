from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class ManualStatusChange(Base):
    __tablename__ = "manual_status_changes"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    event_type       = Column(String, nullable=False)  # "moto_rejected" | "reservation_cancelled" | "sale_cancelled"
    motorcycle_id    = Column(Integer, ForeignKey("motorcycles.motorcycle_id"),   nullable=True)
    reservation_id   = Column(Integer, ForeignKey("reservations.reservation_id"), nullable=True)
    sale_id          = Column(Integer, ForeignKey("sales.sale_id"),               nullable=True)
    reason           = Column(String(128), nullable=False)
    performed_by     = Column(Integer, ForeignKey("users.user_id"),               nullable=False)
    created_at       = Column(DateTime, server_default=func.now(),                nullable=False)

    motorcycle  = relationship("Motorcycle")
    reservation = relationship("Reservation")
    sale        = relationship("Sale")
    performer   = relationship("User", foreign_keys=[performed_by])
