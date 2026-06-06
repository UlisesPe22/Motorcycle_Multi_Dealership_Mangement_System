from sqlalchemy import Column, Integer, String, Float, ForeignKey, Enum, DateTime
from sqlalchemy.orm import relationship
from database import Base
import enum
from datetime import datetime, timezone


class SaleType(str, enum.Enum):
    contado = "contado"
    credito = "credito"


class ContractPaymentMethod(str, enum.Enum):
    transferencia = "transferencia"
    efectivo      = "efectivo"


class Contract(Base):
    __tablename__ = "contracts"

    contract_id            = Column(Integer, primary_key=True,
                                    autoincrement=True)
    contract_number        = Column(String, unique=True, nullable=False)
    sale_event_id          = Column(Integer, ForeignKey("events.event_id"),
                                    nullable=False)
    client_id              = Column(Integer, ForeignKey("clients.client_id"),
                                    nullable=False)
    motorcycle_id          = Column(Integer, ForeignKey("motorcycles.motorcycle_id"),
                                    nullable=False)
    dealership_id          = Column(Integer, ForeignKey("dealerships.dealership_id"),
                                    nullable=False)
    employee_id            = Column(Integer, ForeignKey("users.user_id"),
                                    nullable=False)
    sale_type              = Column(Enum(SaleType), nullable=False)
    payment_method         = Column(Enum(ContractPaymentMethod, name="paymentmethod"), nullable=True)
    payment_downpayment    = Column(Float, nullable=True)
    payment_institution_id = Column(Integer,
                                    ForeignKey("credit_institutions.credit_institution_id"),
                                    nullable=True)
    payment_bank           = Column(String, nullable=True)
    reference_name         = Column(String, nullable=True)
    reference_phone        = Column(String, nullable=True)
    reference_relation     = Column(String, nullable=True)
    buyer_colonia          = Column(String, nullable=True)
    buyer_cp               = Column(String, nullable=True)
    buyer_municipio        = Column(String, nullable=True)
    buyer_estado           = Column(String, nullable=True)
    created_at             = Column(DateTime(timezone=True),
                                    default=lambda: datetime.now(timezone.utc),
                                    nullable=False)

    event       = relationship("Event")
    client      = relationship("Client")
    motorcycle  = relationship("Motorcycle")
    dealership  = relationship("Dealership")
    employee    = relationship("User")
    institution = relationship("CreditInstitution")
