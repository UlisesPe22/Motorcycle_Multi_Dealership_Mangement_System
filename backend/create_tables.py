import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine, Base

from models.user                        import User                                  # noqa: F401
from models.event                       import Event                                 # noqa: F401
from models.color                       import Color                                 # noqa: F401
from models.submission                  import Submission                             # noqa: F401
from models.ai_analysis_log             import AIAnalysisLog                         # noqa: F401
from models.client                      import Client                                # noqa: F401
from models.dealership                  import Dealership                            # noqa: F401
from models.motorcycle_catalog          import MotorcycleCatalog                     # noqa: F401
from models.motorcycle_model_code       import MotorcycleModelCode                  # noqa: F401
from models.purchase_document           import PurchaseDocument                      # noqa: F401
from models.order_confirmation_document import OrderConfirmationDocument             # noqa: F401
from models.motorcycle_catalog_color    import MotorcycleCatalogColor               # noqa: F401
from models.reservation                 import Reservation, ReservationStatus        # noqa: F401
from models.reservation_color           import ReservationColor                      # noqa: F401
from models.motorcycle                  import Motorcycle                            # noqa: F401
from models.credit_institution          import CreditInstitution                      # noqa: F401
from models.contract                    import Contract                               # noqa: F401


def create_all_tables():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("Done. Tables created:")
    for table_name in Base.metadata.tables.keys():
        print(f"  ✓ {table_name}")


if __name__ == "__main__":
    create_all_tables()