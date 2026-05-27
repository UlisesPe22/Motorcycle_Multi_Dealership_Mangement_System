from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from database import Base


class Color(Base):
    __tablename__ = "colors"

    color_id = Column(Integer, primary_key=True, autoincrement=True)
    name     = Column(String, unique=True, nullable=False)

    catalog_colors     = relationship("MotorcycleCatalogColor",
                                      back_populates="color")
    reservation_colors = relationship("ReservationColor",
                                      back_populates="color")

    def __repr__(self):
        return f"<Color id={self.color_id} name={self.name}>"
