from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from database import Base

class Dealership(Base):
    __tablename__ = "dealerships"

    dealership_id   = Column(Integer, primary_key=True, autoincrement=True)
    name            = Column(String, nullable=False)
    address         = Column(String, nullable=False)
    name_contract   = Column(String, nullable=False)
    city_contract   = Column(String, nullable=False)
    contract_prefix = Column(String, nullable=False)

    sales = relationship("Sale", back_populates="dealership")