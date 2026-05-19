import enum
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class MotorcycleStatus(str, enum.Enum):
    purchased         = "purchased"
    incoming          = "incoming"
    incoming_reserved = "incoming_reserved"
    in_stock          = "in_stock"
    in_stock_reserved = "in_stock_reserved"
    not_purchased     = "not_purchased"
    rejected          = "rejected"
    sold              = "sold"
    cancelled         = "cancelled"


class Motorcycle(Base):
    __tablename__ = "motorcycles"

    motorcycle_id            = Column(Integer, primary_key=True, autoincrement=True)

    # ------------------------------------------------------------------ #
    # Catalog FK                                                          #
    # ------------------------------------------------------------------ #
    model_id                 = Column(Integer, ForeignKey("motorcycle_catalog.model_id"), nullable=False)

    # ------------------------------------------------------------------ #
    # Document trail FKs                                                  #
    # ------------------------------------------------------------------ #
    purchase_document_id     = Column(Integer, ForeignKey("purchase_documents.purchase_document_id"), nullable=True)
    order_confirmation_id    = Column(Integer, ForeignKey("order_confirmation_documents.order_confirmation_document_id"), nullable=True)
    delivery_confirmation_id = Column(Integer, ForeignKey("submissions.submission_id"), nullable=True)

    # ------------------------------------------------------------------ #
    # Location                                                            #
    # ------------------------------------------------------------------ #
    dealership_id            = Column(Integer, ForeignKey("dealerships.dealership_id"), nullable=False)

    # ------------------------------------------------------------------ #
    # Identity — populated at order confirmation stage                    #
    # ------------------------------------------------------------------ #
    reference_number         = Column(String, nullable=True, unique=True)
    motor_number             = Column(String, nullable=True, unique=True)
    color                    = Column(String, nullable=True)

    # ------------------------------------------------------------------ #
    # Lifecycle                                                           #
    # ------------------------------------------------------------------ #
    status                   = Column(
                                   Enum(MotorcycleStatus),
                                   nullable=False,
                                   default=MotorcycleStatus.purchased
                               )
    created_at               = Column(DateTime, server_default=func.now(), nullable=False)

    # ------------------------------------------------------------------ #
    # Reservation link — nullable until a reservation is assigned         #
    # ------------------------------------------------------------------ #
    reservation_id = Column(Integer, ForeignKey("reservations.reservation_id"), nullable=True)

    # ------------------------------------------------------------------ #
    # Relationships                                                        #
    # ------------------------------------------------------------------ #
    model       = relationship("MotorcycleCatalog", back_populates="motorcycles")
    dealership  = relationship("Dealership")
    reservation = relationship("Reservation", back_populates="motorcycle",
                               foreign_keys=[reservation_id])
