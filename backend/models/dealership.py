from sqlalchemy import Column, Integer, String
from database import Base

class Dealership(Base):
    __tablename__ = "dealerships"

    dealership_id = Column(Integer, primary_key=True, autoincrement=True)
    name          = Column(String, nullable=False)
    address       = Column(String, nullable=False)