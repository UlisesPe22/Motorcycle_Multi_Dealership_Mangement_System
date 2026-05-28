from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from database import Base


class PurchaseDocument(Base):
    __tablename__ = "purchase_documents"

    purchase_document_id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id        = Column(Integer, ForeignKey("submissions.submission_id"), nullable=False)
    dealership_id        = Column(Integer, ForeignKey("dealerships.dealership_id"), nullable=False)
    order_date           = Column(String, nullable=True)    # extracted from PDF header
    total_units          = Column(Integer, nullable=False)  # total motorcycle rows generated
    created_at           = Column(DateTime, server_default=func.now(), nullable=False)