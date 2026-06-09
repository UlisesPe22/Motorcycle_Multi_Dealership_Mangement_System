import enum

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class SaleStatus(str, enum.Enum):
    open     = "open"
    verified = "verified"
    complete = "complete"
    refunded = "refunded"


class Sale(Base):
    __tablename__ = "sales"

    sale_id          = Column(Integer, primary_key=True, autoincrement=True)
    motorcycle_id    = Column(Integer, ForeignKey("motorcycles.motorcycle_id"),   nullable=True)
    client_id        = Column(Integer, ForeignKey("clients.client_id"),           nullable=False)
    vendor_id        = Column(Integer, ForeignKey("users.user_id"),               nullable=False)
    dealership_id    = Column(Integer, ForeignKey("dealerships.dealership_id"),   nullable=False)
    total_price      = Column(Float,                                               nullable=False)
    amount_verified  = Column(Float,   default=0.0,                               nullable=False)
    status           = Column(String,  default=SaleStatus.open.value,             nullable=False)
    created_at       = Column(DateTime, server_default=func.now(),                nullable=False)

    motorcycle  = relationship("Motorcycle",  back_populates="sale")
    client      = relationship("Client",      back_populates="sales")
    vendor      = relationship("User",        back_populates="sales")
    dealership  = relationship("Dealership",  back_populates="sales")
    events      = relationship("PaymentEvent", back_populates="sale",
                               cascade="all, delete-orphan",
                               order_by="PaymentEvent.created_at")
