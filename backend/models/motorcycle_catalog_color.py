from sqlalchemy import Column, Integer, ForeignKey, Enum
from sqlalchemy.orm import relationship
from database import Base
import enum


class MotorcycleColor(str, enum.Enum):
    Purpura = "Purpura"
    Citrus  = "Citrus"
    Rojo    = "Rojo"
    Perla   = "Perla"
    Azul    = "Azul"
    Negro   = "Negro"
    Gris    = "Gris"


class MotorcycleCatalogColor(Base):
    __tablename__ = "motorcycle_catalog_colors"

    id       = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("motorcycle_catalog.model_id"),
                      nullable=False)
    color    = Column(Enum(MotorcycleColor), nullable=False)

    model = relationship("MotorcycleCatalog",
                         back_populates="available_colors")
