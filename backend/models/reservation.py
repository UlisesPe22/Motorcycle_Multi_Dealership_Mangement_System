from sqlalchemy import Column, Integer, Float, ForeignKey, Enum, DateTime
from sqlalchemy.orm import relationship
from database import Base
import enum
from datetime import datetime, timezone


class ReservationStatus(str, enum.Enum):
    active    = "active"
    assigned  = "assigned"
    cancelled = "cancelled"


class Reservation(Base):
    __tablename__ = "reservations"

    reservation_id  = Column(Integer, primary_key=True, autoincrement=True)
    client_id       = Column(Integer, ForeignKey("clients.client_id"),              nullable=False)
    model_id        = Column(Integer, ForeignKey("motorcycle_catalog.model_id"),    nullable=False)
    dealership_id   = Column(Integer, ForeignKey("dealerships.dealership_id"),      nullable=False)
    deposit_amount  = Column(Float,                                                  nullable=False)
    status          = Column(Enum(ReservationStatus),
                             default=ReservationStatus.active,                       nullable=False)
    created_by      = Column(Integer, ForeignKey("users.user_id"),                  nullable=False)
    event_id        = Column(Integer, ForeignKey("events.event_id"),                nullable=False)
    created_at      = Column(DateTime,
                             default=lambda: datetime.now(timezone.utc),            nullable=False)

    client     = relationship("Client",            back_populates="reservations")
    model      = relationship("MotorcycleCatalog", back_populates="reservations")
    dealership = relationship("Dealership")
    creator    = relationship("User")
    event      = relationship("Event")
    colors     = relationship("ReservationColor",  back_populates="reservation",
                              order_by="ReservationColor.priority",
                              cascade="all, delete-orphan")
    motorcycle = relationship("Motorcycle",        back_populates="reservation",
                              foreign_keys="Motorcycle.reservation_id", uselist=False)
