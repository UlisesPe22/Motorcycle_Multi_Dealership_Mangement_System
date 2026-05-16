"""
main.py — FastAPI application entry point.

Run from backend/ folder:
    uvicorn main:app --reload --port 8000

API docs available at:
    http://localhost:8000/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base

# Import all models so tables are created on startup
from models.user                        import User                                  # noqa
from models.event                       import EventType, EventSlotDefinition, Event # noqa
from models.submission                  import Submission                             # noqa
from models.ai_analysis_log             import AIAnalysisLog                         # noqa
from models.client                      import Client                                # noqa
from models.dealership                  import Dealership                            # noqa
from models.motorcycle_catalog          import MotorcycleCatalog                     # noqa
from models.motorcycle_model_code       import MotorcycleModelCode                  # noqa
from models.purchase_document           import PurchaseDocument                      # noqa
from models.order_confirmation_document import OrderConfirmationDocument             # noqa
from models.motorcycle_catalog_color    import MotorcycleCatalogColor               # noqa
from models.reservation                 import Reservation, ReservationStatus        # noqa
from models.reservation_color           import ReservationColor                      # noqa
from models.motorcycle                  import Motorcycle                            # noqa

from routers import events, submissions, clients, delivery_confirmations, motorcycles, reservations

# Create tables if they don't exist yet
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Moto Dealer — Document Processing API",
    description="AI-powered document validation and client registration pipeline.",
    version="0.1.0",
)

# Allow Streamlit (running on port 8501) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events.router)
app.include_router(submissions.router)
app.include_router(clients.router)
app.include_router(delivery_confirmations.router)
app.include_router(motorcycles.router)
app.include_router(reservations.router)


@app.get("/")
def root():
    return {"status": "ok", "message": "Moto Dealer API running"}


@app.get("/health")
def health():
    return {"status": "ok"}