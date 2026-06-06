import enum
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class UserRole(enum.Enum):
    admin    = "admin"
    employee = "employee"


class User(Base):
    __tablename__ = "users"

    user_id    = Column(Integer, primary_key=True, index=True)
    name       = Column(String, nullable=False)
    role       = Column(Enum(UserRole), nullable=False)
    phone         = Column(String, nullable=True)
    dealership_id = Column(Integer, ForeignKey("dealerships.dealership_id"), nullable=True)
    created_by    = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    dealership     = relationship("Dealership")
    sales          = relationship("Sale",         back_populates="vendor",  foreign_keys="Sale.vendor_id")
    payment_events = relationship("PaymentEvent", back_populates="creator", foreign_keys="PaymentEvent.created_by")

    def __repr__(self):
        return f"<User id={self.user_id} name={self.name} role={self.role}>"