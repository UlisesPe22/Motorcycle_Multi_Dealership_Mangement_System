from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.orm import relationship
from database import Base


class MotorcycleCatalog(Base):
    """
    Static catalog of canonical motorcycle models.
    One row per canonical name + year combination.
    Price depends on year so it lives here.

    Example rows:
      id=1  canonical_name="Pulsar N160"  year="2026"  full_price=48874.15
      id=2  canonical_name="Pulsar N160"  year="2025"  full_price=46500.00
    """
    __tablename__ = "motorcycle_catalog"

    model_id       = Column(Integer, primary_key=True, autoincrement=True)
    canonical_name = Column(String, nullable=False)
    year           = Column(String, nullable=False)
    full_price     = Column(Float, nullable=True)   # nullable until seeded with real prices

    # ------------------------------------------------------------------ #
    # Relationships                                                        #
    # ------------------------------------------------------------------ #
    codes = relationship(
        "MotorcycleModelCode",
        back_populates="model",
        cascade="all, delete-orphan"
    )

    motorcycles = relationship(
        "Motorcycle",
        back_populates="model"
    )

    def __repr__(self) -> str:
        return (
            f"<MotorcycleModel id={self.model_id} "
            f"name={self.canonical_name} "
            f"year={self.year}>"
        )