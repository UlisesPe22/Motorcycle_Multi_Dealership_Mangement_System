from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.sql import func
from database import Base


class OrderConfirmationDocument(Base):
    """
    Stores document-level metadata for each order confirmation event.
    One row per Aviso de Traslado PDF processed.
    Links to the submission that uploaded it and the destination dealership.
    """
    __tablename__ = "order_confirmation_documents"

    order_confirmation_document_id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id                  = Column(Integer, ForeignKey("submissions.submission_id"), nullable=False)
    dealership_id                  = Column(Integer, ForeignKey("dealerships.dealership_id"), nullable=False)
    total_units                    = Column(Integer, nullable=False)
    created_at                     = Column(DateTime, server_default=func.now(), nullable=False)