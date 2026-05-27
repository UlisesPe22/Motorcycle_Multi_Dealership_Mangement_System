from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class MotorcycleCatalogColor(Base):
    __tablename__ = "motorcycle_catalog_colors"

    id       = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("motorcycle_catalog.model_id"),
                      nullable=False)
    color_id = Column(Integer, ForeignKey("colors.color_id"),
                      nullable=False)

    model = relationship("MotorcycleCatalog",
                         back_populates="available_colors")
    color = relationship("Color",
                         back_populates="catalog_colors")
