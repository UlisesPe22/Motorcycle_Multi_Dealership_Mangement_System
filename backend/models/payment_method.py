from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from database import Base


class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    method_id = Column(Integer, primary_key=True, autoincrement=True)
    name      = Column(String, unique=True, nullable=False)

    items = relationship("PaymentItem", back_populates="method")
