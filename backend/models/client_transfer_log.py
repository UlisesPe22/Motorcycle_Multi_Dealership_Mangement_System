from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class ClientTransferLog(Base):
    __tablename__ = "client_transfer_logs"

    transfer_id      = Column(Integer, primary_key=True, autoincrement=True)
    sale_id          = Column(Integer, ForeignKey("sales.sale_id"),               nullable=True)
    reservation_id   = Column(Integer, ForeignKey("reservations.reservation_id"), nullable=True)
    from_client_id   = Column(Integer, ForeignKey("clients.client_id"),           nullable=False)
    to_client_id     = Column(Integer, ForeignKey("clients.client_id"),           nullable=False)
    reason           = Column(String(128), nullable=False)
    performed_by     = Column(Integer, ForeignKey("users.user_id"),               nullable=False)
    created_at       = Column(DateTime, server_default=func.now(),                nullable=False)

    sale         = relationship("Sale")
    reservation  = relationship("Reservation")
    from_client  = relationship("Client", foreign_keys=[from_client_id])
    to_client    = relationship("Client", foreign_keys=[to_client_id])
    performer    = relationship("User",   foreign_keys=[performed_by])
