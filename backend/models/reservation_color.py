from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class ReservationColor(Base):
    __tablename__ = "reservation_colors"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    reservation_id = Column(Integer, ForeignKey("reservations.reservation_id"),
                            nullable=False)
    color_id       = Column(Integer, ForeignKey("colors.color_id"),
                            nullable=False)
    priority       = Column(Integer, nullable=False)

    reservation = relationship("Reservation", back_populates="colors")
    color       = relationship("Color", back_populates="reservation_colors")
