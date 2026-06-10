"""
main.py — FastAPI application entry point.

Run from backend/ folder:
    uvicorn main:app --reload --port 8000

API docs available at:
    http://localhost:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base

# Import all models so tables are created on startup
from models.user                        import User                                  # noqa
from models.event                       import Event                                 # noqa
from models.color                       import Color                                 # noqa
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
from models.credit_institution          import CreditInstitution                      # noqa
from models.contract                    import Contract                               # noqa
from models.payment_method              import PaymentMethod                          # noqa
from models.sale                        import Sale                                   # noqa
from models.payment_event               import PaymentEvent                           # noqa
from models.payment_item                import PaymentItem                            # noqa
from models.manual_status_change        import ManualStatusChange                     # noqa
from models.client_transfer_log         import ClientTransferLog                      # noqa
from models.unconfirmed_client          import UnconfirmedClient                       # noqa
from models.payment_confirmation_token  import PaymentConfirmationToken               # noqa

from routers import events, submissions, clients, delivery_confirmations, motorcycles, reservations, sales, registrar
from routers.auth import router as auth_router
from routers.declare_payment import router as declare_payment_router
from routers.inventory_management import router as inventory_management_router
from routers.vendor_sales import router as vendor_sales_router
from routers.payment_confirmation import router as payment_confirmation_router
from services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Moto Dealer — Document Processing API",
    description="AI-powered document validation and client registration pipeline.",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow Streamlit (running on port 8501) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(events.router)
app.include_router(submissions.router)
app.include_router(clients.router)
app.include_router(delivery_confirmations.router)
app.include_router(motorcycles.router)
app.include_router(reservations.router)
app.include_router(sales.router)
app.include_router(registrar.router)
app.include_router(declare_payment_router)
app.include_router(inventory_management_router)
app.include_router(vendor_sales_router)
app.include_router(payment_confirmation_router)


@app.get("/")
async def root():
    return {"status": "ok", "message": "Moto Dealer API running"}


@app.get("/health")
async def health():
    return {"status": "ok"}
