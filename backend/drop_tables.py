import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import engine, Base

# All models must be imported so Base.metadata knows about them
from models.user               import User               # noqa: F401
from models.event              import EventType, EventSlotDefinition, Event  # noqa: F401
from models.submission         import Submission         # noqa: F401
from models.ai_analysis_log    import AIAnalysisLog      # noqa: F401


def drop_all_tables():
    print("Dropping all tables...")
    # drop_all respects FK constraints automatically when using
    # Base.metadata because SQLAlchemy knows the dependency graph.
    Base.metadata.drop_all(bind=engine)
    print("Done. All tables dropped.")


if __name__ == "__main__":

    drop_all_tables()
