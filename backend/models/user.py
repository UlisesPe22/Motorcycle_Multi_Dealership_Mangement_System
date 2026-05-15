import enum
from sqlalchemy import Column, Integer, String, DateTime, Enum
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
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<User id={self.user_id} name={self.name} role={self.role}>"