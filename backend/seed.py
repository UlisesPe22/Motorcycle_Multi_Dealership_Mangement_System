import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models.user                  import User, UserRole
from models.event                 import EventType, EventSlotDefinition, EventName, SlotName
from models.dealership            import Dealership
from models.motorcycle_catalog    import MotorcycleCatalog
from models.motorcycle_model_code import MotorcycleModelCode


def seed_users(db):
    if db.query(User).count() > 0:
        print("  → users already seeded, skipping.")
        return

    users = [
        User(name="eskeleton", role=UserRole.admin),
        User(name="eskeleton", role=UserRole.employee),
    ]
    db.add_all(users)
    db.commit()
    print(f"  ✓ Inserted {len(users)} users.")


def seed_dealerships(db):
    if db.query(Dealership).count() > 0:
        print("  → dealerships already seeded, skipping.")
        return

    dealerships = [
        Dealership(
            name    = "BAJAJ VIA MORELOS",
            address = "VIA MORELOS 126 #126 COL. SAN JOSE JAJALPA ECATEPEC DE MORELOS C.P. 55090"
        ),
        Dealership(
            name    = "BAJAJ IGNACIO ZARAGOZA",
            address = "AV. IGNACIO ZARAGOZA #1660 Col. JUAN ESCUTIA IZTAPALAPA C.P. 09100"
        ),
        Dealership(
            name    = "BAJAJ TLALPIZAHUAC",
            address = "AVENIDA CUAUHTEMOC #4 Col. SANTA CRUZ TLALPIZAHUAC IXTAPALUCA C.P. 56577"
        ), 
    ]
    db.add_all(dealerships)
    db.commit()
    print(f"  ✓ Inserted {len(dealerships)} dealerships.")


def seed_event_types(db):
    if db.query(EventType).count() > 0:
        print("  → event_types already seeded, skipping.")
        return

    event_types = [
        EventType(
            name           = EventName.client_registration,
            required_slots = 2,
            description    = "Register a new client by validating both sides of their INE."
        ),
        EventType(
            name           = EventName.sale_validation,
            required_slots = 1,
            description    = "Validate a motorcycle sale contract to unlock commission."
        ),
        EventType(
            name           = EventName.delivery_confirmation,
            required_slots = 1,
            description    = "Confirm motorcycle delivery with signed delivery table."
        ),
        EventType(
            name           = EventName.purchase_order,
            required_slots = 1,
            description    = "Register a new motorcycle purchase order from distributor PDF."
        ),
        EventType(
            name           = EventName.order_confirmation,
            required_slots = 1,
            description    = "Register distributor order confirmation with reference numbers."
        ),
    ]
    db.add_all(event_types)
    db.commit()
    print(f"  ✓ Inserted {len(event_types)} event types.")


def seed_slot_definitions(db):
    if db.query(EventSlotDefinition).count() > 0:
        print("  → event_slot_definitions already seeded, skipping.")
        return

    def get_type_id(name: EventName) -> int:
        row = db.query(EventType).filter(EventType.name == name).first()
        if not row:
            raise RuntimeError(f"EventType '{name}' not found. Run seed_event_types first.")
        return row.event_type_id

    slots = [
        EventSlotDefinition(
            event_type_id = get_type_id(EventName.client_registration),
            slot_number   = 1,
            slot_name     = SlotName.id_front,
            description   = "Front side of the client's INE voter ID card."
        ),
        EventSlotDefinition(
            event_type_id = get_type_id(EventName.client_registration),
            slot_number   = 2,
            slot_name     = SlotName.id_back,
            description   = "Back side of the client's INE voter ID card."
        ),
        EventSlotDefinition(
            event_type_id = get_type_id(EventName.sale_validation),
            slot_number   = 1,
            slot_name     = SlotName.contract,
            description   = "Signed motorcycle sale contract."
        ),
        EventSlotDefinition(
            event_type_id = get_type_id(EventName.delivery_confirmation),
            slot_number   = 1,
            slot_name     = SlotName.delivery_table,
            description   = "Signed delivery confirmation table."
        ),
        EventSlotDefinition(
            event_type_id = get_type_id(EventName.purchase_order),
            slot_number   = 1,
            slot_name     = SlotName.purchase_order_table,
            description   = "Purchase order PDF sent to distributor."
        ),
        EventSlotDefinition(
            event_type_id = get_type_id(EventName.order_confirmation),
            slot_number   = 1,
            slot_name     = SlotName.order_table,
            description   = "Order confirmation PDF received from distributor."
        ),
    ]
    db.add_all(slots)
    db.commit()
    print(f"  ✓ Inserted {len(slots)} slot definitions.")


def seed_motorcycle_catalog(db):
    if db.query(MotorcycleCatalog).count() > 0:
        print("  → motorcycle_catalog already seeded, skipping.")
        return

    # ------------------------------------------------------------------ #
    # Catalog rows — one per canonical_name + year combination            #
    # Price left null until confirmed by company                          #
    # ------------------------------------------------------------------ #
    catalog_entries = [
        # 2026 models
        MotorcycleCatalog(canonical_name="Pulsar N125 FI-CBS",  year="2026", full_price=None),
        MotorcycleCatalog(canonical_name="Pulsar N125 Car",     year="2026", full_price=None),
        MotorcycleCatalog(canonical_name="Pulsar N160",         year="2026", full_price=None),
        MotorcycleCatalog(canonical_name="Pulsar N160 Premium", year="2026", full_price=None),
        MotorcycleCatalog(canonical_name="Pulsar N250 FI ABS",  year="2026", full_price=None),
        MotorcycleCatalog(canonical_name="Dominar 250",         year="2026", full_price=None),
        MotorcycleCatalog(canonical_name="Dominar 400 UG",      year="2026", full_price=None),
        MotorcycleCatalog(canonical_name="Pulsar NS200",        year="2026", full_price=None),

        # 2025 models
        MotorcycleCatalog(canonical_name="Pulsar RS200",        year="2025", full_price=None),
        MotorcycleCatalog(canonical_name="Pulsar NS400Z",       year="2025", full_price=None),
    ]
    db.add_all(catalog_entries)
    db.commit()
    print(f"  ✓ Inserted {len(catalog_entries)} motorcycle catalog entries.")


def seed_motorcycle_model_codes(db):
    if db.query(MotorcycleModelCode).count() > 0:
        print("  → motorcycle_model_codes already seeded, skipping.")
        return

    def get_catalog_id(canonical_name: str, year: str) -> int:
        row = db.query(MotorcycleCatalog).filter(
            MotorcycleCatalog.canonical_name == canonical_name,
            MotorcycleCatalog.year           == year,
        ).first()
        if not row:
            raise RuntimeError(f"Catalog entry '{canonical_name}' {year} not found.")
        return row.model_id

    codes = [
        # Pulsar N125 FI CBS 2026
        MotorcycleModelCode(model_id=get_catalog_id("Pulsar N125 FI-CBS", "2026"),  modelo_code="P125N-PU26DI"),
        MotorcycleModelCode(model_id=get_catalog_id("Pulsar N125 FI-CBS", "2026"),  modelo_code="P125N-CI26DI"),
        MotorcycleModelCode(model_id=get_catalog_id("Pulsar N125 FI-CBS", "2026"),  modelo_code="P125N-RO26DI"),

        # Pulsar N125 Car 2026
        MotorcycleModelCode(model_id=get_catalog_id("Pulsar N125 Car", "2026"),     modelo_code="P125NCCI26DI"),
        MotorcycleModelCode(model_id=get_catalog_id("Pulsar N125 Car", "2026"),     modelo_code="P125NCPU26DI"),

        # Pulsar N160 2026
        MotorcycleModelCode(model_id=get_catalog_id("Pulsar N160", "2026"),         modelo_code="P160CAPE26DI"),
        MotorcycleModelCode(model_id=get_catalog_id("Pulsar N160", "2026"),         modelo_code="P160CAAZ26DI"),

        # Pulsar N160 Premium 2026
        MotorcycleModelCode(model_id=get_catalog_id("Pulsar N160 Premium", "2026"), modelo_code="P160NPRO26DI"),
        MotorcycleModelCode(model_id=get_catalog_id("Pulsar N160 Premium", "2026"), modelo_code="P160NPAZ26DI"),
        MotorcycleModelCode(model_id=get_catalog_id("Pulsar N160 Premium", "2026"), modelo_code="P160NPNE26DI"),

        # Pulsar N250 FI ABS 2026
        MotorcycleModelCode(model_id=get_catalog_id("Pulsar N250 FI ABS", "2026"),  modelo_code="P250N-PE26DI"),
        MotorcycleModelCode(model_id=get_catalog_id("Pulsar N250 FI ABS", "2026"),  modelo_code="P250N-RO26DI"),
        MotorcycleModelCode(model_id=get_catalog_id("Pulsar N250 FI ABS", "2026"),  modelo_code="P250N-NE26DI"),

        # Dominar 250 2026
        MotorcycleModelCode(model_id=get_catalog_id("Dominar 250", "2026"),         modelo_code="D250UGNE26DI"),
        MotorcycleModelCode(model_id=get_catalog_id("Dominar 250", "2026"),         modelo_code="D250UGRO26DI"),

        # Dominar 400 UG 2026
        MotorcycleModelCode(model_id=get_catalog_id("Dominar 400 UG", "2026"),      modelo_code="D400UGNE26DI"),

        # Pulsar NS200 2026
        MotorcycleModelCode(model_id=get_catalog_id("Pulsar NS200", "2026"),        modelo_code="P200NSNE26DI"),
        MotorcycleModelCode(model_id=get_catalog_id("Pulsar NS200", "2026"),        modelo_code="P200NSRO26DI"),

        # Pulsar RS200 2025
        MotorcycleModelCode(model_id=get_catalog_id("Pulsar RS200", "2025"),        modelo_code="P200RSPE25DI"),

        # Pulsar NS400Z 2025
        MotorcycleModelCode(model_id=get_catalog_id("Pulsar NS400Z", "2025"),       modelo_code="P400NSGR25DI"),
        MotorcycleModelCode(model_id=get_catalog_id("Pulsar NS400Z", "2025"),       modelo_code="P400NSRO25DI"),
    ]
    db.add_all(codes)
    db.commit()
    print(f"  ✓ Inserted {len(codes)} motorcycle model codes.")


def run_seed():
    db = SessionLocal()
    try:
        print("\nSeeding database...")
        seed_users(db)
        seed_dealerships(db)
        seed_event_types(db)
        seed_slot_definitions(db)
        seed_motorcycle_catalog(db)
        seed_motorcycle_model_codes(db)
        print("\nSeed complete.\n")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()