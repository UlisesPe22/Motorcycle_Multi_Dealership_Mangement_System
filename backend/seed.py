import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models.user                     import User, UserRole
from models.dealership               import Dealership
from models.motorcycle_catalog       import MotorcycleCatalog
from models.motorcycle_model_code    import MotorcycleModelCode
from models.motorcycle_catalog_color import MotorcycleCatalogColor
from models.credit_institution       import CreditInstitution
from models.color                    import Color


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
            name            = "BAJAJ VIA MORELOS",
            address         = "VIA MORELOS 126 #126 COL. SAN JOSE JAJALPA ECATEPEC DE MORELOS C.P. 55090",
            name_contract   = "Via Morelos",
            city_contract   = "Vía Morelos, Estado de México",
            contract_prefix = "VMOR",
        ),
        Dealership(
            name            = "BAJAJ IGNACIO ZARAGOZA",
            address         = "AV. IGNACIO ZARAGOZA #1660 Col. JUAN ESCUTIA IZTAPALAPA C.P. 09100",
            name_contract   = "Ignacio Zaragoza",
            city_contract   = "Ignacio Zaragoza, CDMX",
            contract_prefix = "IGZA",
        ),
        Dealership(
            name            = "BAJAJ TLALPIZAHUAC",
            address         = "AVENIDA CUAUHTEMOC #4 Col. SANTA CRUZ TLALPIZAHUAC IXTAPALUCA C.P. 56577",
            name_contract   = "Tlalpizahuac",
            city_contract   = "Tlalpizahuac, Estado de México",
            contract_prefix = "IXT",
        ),
    ]
    db.add_all(dealerships)
    db.commit()
    print(f"  ✓ Inserted {len(dealerships)} dealerships.")


def seed_colors(db):
    colors_data = [
        "Purpura", "Citrus", "Rojo", "Perla",
        "Azul", "Negro", "Gris",
    ]
    inserted = 0
    for name in colors_data:
        existing = db.query(Color).filter(Color.name == name).first()
        if not existing:
            db.add(Color(name=name))
            inserted += 1
    db.commit()
    print(f"  ✓ Inserted {inserted} colors.")


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
        MotorcycleCatalog(canonical_name="Pulsar N125 FI-CBS",  year="2026", full_price=38999.00, discount_price=37499.00),
        MotorcycleCatalog(canonical_name="Pulsar N125 Car",     year="2026", full_price=33999.00, discount_price=33999.00),
        MotorcycleCatalog(canonical_name="Pulsar N160",         year="2026", full_price=37099.00, discount_price=37099.00),
        MotorcycleCatalog(canonical_name="Pulsar N160 Premium", year="2026", full_price=57499.00, discount_price=53999.00),
        MotorcycleCatalog(canonical_name="Pulsar N250 FI ABS",  year="2026", full_price=69999.01, discount_price=66499.01),
        MotorcycleCatalog(canonical_name="Dominar 250",         year="2026", full_price=73499.00, discount_price=71499.00),
        MotorcycleCatalog(canonical_name="Dominar 400 UG",      year="2026", full_price=95999.00, discount_price=93999.00),
        MotorcycleCatalog(canonical_name="Pulsar NS200",        year="2026", full_price=62999.00, discount_price=57999.00),

        # 2025 models
        MotorcycleCatalog(canonical_name="Pulsar RS200",        year="2025", full_price=72499.00, discount_price=66499.00),
        MotorcycleCatalog(canonical_name="Pulsar NS400Z",       year="2025", full_price=90999.00, discount_price=86499.00),
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


def seed_motorcycle_catalog_colors(db):
    if db.query(MotorcycleCatalogColor).count() > 0:
        print("  -> motorcycle_catalog_colors already seeded, skipping.")
        return

    def get_catalog_id(canonical_name: str, year: str) -> int:
        row = db.query(MotorcycleCatalog).filter(
            MotorcycleCatalog.canonical_name == canonical_name,
            MotorcycleCatalog.year           == year,
        ).first()
        if not row:
            raise RuntimeError(f"Catalog entry '{canonical_name}' {year} not found.")
        return row.model_id

    def get_color_id(name: str) -> int:
        row = db.query(Color).filter(Color.name == name).first()
        if not row:
            raise RuntimeError(f"Color '{name}' not found — run seed_colors first.")
        return row.color_id

    color_map = [
        ("Pulsar N125 FI-CBS",  "2026", ["Purpura", "Citrus",  "Rojo"]),
        ("Pulsar N125 Car",     "2026", ["Citrus",  "Purpura"]),
        ("Pulsar N160",         "2026", ["Perla",   "Azul"]),
        ("Pulsar N160 Premium", "2026", ["Rojo",    "Azul",    "Negro"]),
        ("Pulsar N250 FI ABS",  "2026", ["Perla",   "Rojo",    "Negro"]),
        ("Dominar 250",         "2026", ["Negro",   "Rojo"]),
        ("Dominar 400 UG",      "2026", ["Negro"]),
        ("Pulsar NS200",        "2026", ["Negro",   "Rojo"]),
        ("Pulsar RS200",        "2025", ["Perla"]),
        ("Pulsar NS400Z",       "2025", ["Gris",    "Rojo"]),
    ]

    entries = []
    for canonical_name, year, colors in color_map:
        model_id = get_catalog_id(canonical_name, year)
        for color_name in colors:
            entries.append(MotorcycleCatalogColor(
                model_id = model_id,
                color_id = get_color_id(color_name),
            ))

    db.add_all(entries)
    db.commit()
    print(f"  ✓ Inserted {len(entries)} motorcycle catalog color entries.")


def seed_credit_institutions(db):
    if db.query(CreditInstitution).count() > 0:
        print("  → credit_institutions already seeded, skipping.")
        return

    db.add_all([
        CreditInstitution(name="ANM"),
        CreditInstitution(name="Maxicash"),
    ])
    db.commit()
    print("  ✓ Inserted 2 credit institutions.")


def run_seed():
    db = SessionLocal()
    try:
        print("\nSeeding database...")
        seed_users(db)
        seed_dealerships(db)
        seed_credit_institutions(db)
        seed_colors(db)
        seed_motorcycle_catalog(db)
        seed_motorcycle_model_codes(db)
        seed_motorcycle_catalog_colors(db)
        print("\nSeed complete.\n")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
