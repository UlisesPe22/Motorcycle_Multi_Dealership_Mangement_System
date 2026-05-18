from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from database import Base


class CreditInstitution(Base):
    __tablename__ = "credit_institutions"

    credit_institution_id = Column(Integer, primary_key=True,
                                   autoincrement=True)
    name                  = Column(String, unique=True, nullable=False)
