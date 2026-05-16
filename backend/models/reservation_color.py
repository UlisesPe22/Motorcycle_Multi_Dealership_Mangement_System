from sqlalchemy import Column, Integer, ForeignKey, Enum
from sqlalchemy.orm import relationship
from database import Base
from models.motorcycle_catalog_color import MotorcycleColor


class ReservationColor(Base):
    __tablename__ = "reservation_colors"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    reservation_id = Column(Integer, ForeignKey("reservations.reservation_id"), nullable=False)
    color          = Column(Enum(MotorcycleColor),                               nullable=False)
    priority       = Column(Integer,                                              nullable=False)

    reservation = relationship("Reservation", back_populates="colors")
