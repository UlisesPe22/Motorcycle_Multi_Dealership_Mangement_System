from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class MotorcycleModelCode(Base):
    """
    Maps every distributor modelo_code to a canonical MotorcycleModel.
    One row per color variant code.

    Example rows:
      code_id=1  modelo_code="P160CAPE26DI"  model_id=1  (Pulsar N160 2026 Perla)
      code_id=2  modelo_code="P160CAAZ26DI"  model_id=1  (Pulsar N160 2026 Azul)
      code_id=3  modelo_code="P160NPRO26DI"  model_id=2  (Pulsar N160 Premium 2026 Rojo)
    """
    __tablename__ = "motorcycle_model_codes"

    code_id     = Column(Integer, primary_key=True, autoincrement=True)
    model_id    = Column(Integer, ForeignKey("motorcycle_catalog.model_id"), nullable=False)
    modelo_code = Column(String, nullable=False, unique=True)

    # ------------------------------------------------------------------ #
    # Relationships                                                        #
    # ------------------------------------------------------------------ #
    model = relationship("MotorcycleCatalog", back_populates="codes")

    def __repr__(self) -> str:
        return (
            f"<MotorcycleModelCode id={self.code_id} "
            f"code={self.modelo_code} "
            f"model_id={self.model_id}>"
        )