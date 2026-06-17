import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func

from database import AsyncSessionLocal
from models.user                     import User
from models.dealership               import Dealership
from models.motorcycle_catalog       import MotorcycleCatalog
from models.motorcycle_model_code    import MotorcycleModelCode
from models.motorcycle_catalog_color import MotorcycleCatalogColor
from models.credit_institution       import CreditInstitution
from models.color                    import Color
from models.payment_method           import PaymentMethod
from models.sale                     import Sale          # noqa: F401 — registers mapper
from models.payment_event            import PaymentEvent  # noqa: F401 — registers mapper
from models.payment_item             import PaymentItem   # noqa: F401 — registers mapper


async def seed_users(db):
    from services.auth import hash_password
    users = [
        {
            "name":     "Ulises Perez",
            "email":    "perez.ulisesernesto@gmail.com",
            "username": "perez.ulisesernesto",
            "password": "22",
            "role":     "master",
            "dealership_id": None,
        },
        {
            "name":     "Owner Test",
            "email":    "owner@bajaj.com",
            "username": "owner",
            "password": "test123",
            "role":     "owner",
            "dealership_id": None,
        },
        {
            "name":     "Manager Test",
            "email":    "manager@bajaj.com",
            "username": "manager",
            "password": "test123",
            "role":     "manager",
            "dealership_id": 1,  # Via Morelos (first seeded dealership)
        },
        {
            "name":     "Vendor Test",
            "email":    "vendor@bajaj.com",
            "username": "vendor",
            "password": "test123",
            "role":     "vendor",
            "dealership_id": 1,
        },
    ]
    inserted = 0
    for u in users:
        existing = await db.execute(select(User).where(User.email == u["email"]))
        if existing.scalar_one_or_none():
            continue
        db.add(User(
            name            = u["name"],
            email           = u["email"],
            username        = u["username"],
            hashed_password = hash_password(u["password"]),
            role            = u["role"],
            dealership_id   = u["dealership_id"],
            is_active       = True,
            created_by      = None,
        ))
        inserted += 1
    await db.commit()
    print(f"  [OK] Inserted {inserted} users.")


async def seed_dealerships(db):
    count = (await db.execute(select(func.count()).select_from(Dealership))).scalar()
    if count > 0:
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
    await db.commit()
    print(f"  ✓ Inserted {len(dealerships)} dealerships.")


async def seed_colors(db):
    colors_data = [
        "Purpura", "Citrus", "Rojo", "Perla",
        "Azul", "Negro", "Gris",
    ]
    inserted = 0
    for name in colors_data:
        existing = (await db.execute(select(Color).where(Color.name == name))).scalars().first()
        if not existing:
            db.add(Color(name=name))
            inserted += 1
    await db.commit()
    print(f"  ✓ Inserted {inserted} colors.")


async def seed_motorcycle_catalog(db):
    count = (await db.execute(select(func.count()).select_from(MotorcycleCatalog))).scalar()
    if count > 0:
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
    await db.commit()
    print(f"  ✓ Inserted {len(catalog_entries)} motorcycle catalog entries.")


async def seed_motorcycle_model_codes(db):
    count = (await db.execute(select(func.count()).select_from(MotorcycleModelCode))).scalar()
    if count > 0:
        print("  → motorcycle_model_codes already seeded, skipping.")
        return

    async def get_catalog_id(canonical_name: str, year: str) -> int:
        row = (await db.execute(
            select(MotorcycleCatalog).where(
                MotorcycleCatalog.canonical_name == canonical_name,
                MotorcycleCatalog.year           == year,
            )
        )).scalars().first()
        if not row:
            raise RuntimeError(f"Catalog entry '{canonical_name}' {year} not found.")
        return row.model_id

    codes = [
        # Pulsar N125 FI CBS 2026
        MotorcycleModelCode(model_id=await get_catalog_id("Pulsar N125 FI-CBS", "2026"),  modelo_code="P125N-PU26DI"),
        MotorcycleModelCode(model_id=await get_catalog_id("Pulsar N125 FI-CBS", "2026"),  modelo_code="P125N-CI26DI"),
        MotorcycleModelCode(model_id=await get_catalog_id("Pulsar N125 FI-CBS", "2026"),  modelo_code="P125N-RO26DI"),

        # Pulsar N125 Car 2026
        MotorcycleModelCode(model_id=await get_catalog_id("Pulsar N125 Car", "2026"),     modelo_code="P125NCCI26DI"),
        MotorcycleModelCode(model_id=await get_catalog_id("Pulsar N125 Car", "2026"),     modelo_code="P125NCPU26DI"),

        # Pulsar N160 2026
        MotorcycleModelCode(model_id=await get_catalog_id("Pulsar N160", "2026"),         modelo_code="P160CAPE26DI"),
        MotorcycleModelCode(model_id=await get_catalog_id("Pulsar N160", "2026"),         modelo_code="P160CAAZ26DI"),

        # Pulsar N160 Premium 2026
        MotorcycleModelCode(model_id=await get_catalog_id("Pulsar N160 Premium", "2026"), modelo_code="P160NPRO26DI"),
        MotorcycleModelCode(model_id=await get_catalog_id("Pulsar N160 Premium", "2026"), modelo_code="P160NPAZ26DI"),
        MotorcycleModelCode(model_id=await get_catalog_id("Pulsar N160 Premium", "2026"), modelo_code="P160NPNE26DI"),

        # Pulsar N250 FI ABS 2026
        MotorcycleModelCode(model_id=await get_catalog_id("Pulsar N250 FI ABS", "2026"),  modelo_code="P250N-PE26DI"),
        MotorcycleModelCode(model_id=await get_catalog_id("Pulsar N250 FI ABS", "2026"),  modelo_code="P250N-RO26DI"),
        MotorcycleModelCode(model_id=await get_catalog_id("Pulsar N250 FI ABS", "2026"),  modelo_code="P250N-NE26DI"),

        # Dominar 250 2026
        MotorcycleModelCode(model_id=await get_catalog_id("Dominar 250", "2026"),         modelo_code="D250UGNE26DI"),
        MotorcycleModelCode(model_id=await get_catalog_id("Dominar 250", "2026"),         modelo_code="D250UGRO26DI"),

        # Dominar 400 UG 2026
        MotorcycleModelCode(model_id=await get_catalog_id("Dominar 400 UG", "2026"),      modelo_code="D400UGNE26DI"),

        # Pulsar NS200 2026
        MotorcycleModelCode(model_id=await get_catalog_id("Pulsar NS200", "2026"),        modelo_code="P200NSNE26DI"),
        MotorcycleModelCode(model_id=await get_catalog_id("Pulsar NS200", "2026"),        modelo_code="P200NSRO26DI"),

        # Pulsar RS200 2025
        MotorcycleModelCode(model_id=await get_catalog_id("Pulsar RS200", "2025"),        modelo_code="P200RSPE25DI"),

        # Pulsar NS400Z 2025
        MotorcycleModelCode(model_id=await get_catalog_id("Pulsar NS400Z", "2025"),       modelo_code="P400NSGR25DI"),
        MotorcycleModelCode(model_id=await get_catalog_id("Pulsar NS400Z", "2025"),       modelo_code="P400NSRO25DI"),
    ]
    db.add_all(codes)
    await db.commit()
    print(f"  ✓ Inserted {len(codes)} motorcycle model codes.")


async def seed_motorcycle_catalog_colors(db):
    count = (await db.execute(select(func.count()).select_from(MotorcycleCatalogColor))).scalar()
    if count > 0:
        print("  -> motorcycle_catalog_colors already seeded, skipping.")
        return

    async def get_catalog_id(canonical_name: str, year: str) -> int:
        row = (await db.execute(
            select(MotorcycleCatalog).where(
                MotorcycleCatalog.canonical_name == canonical_name,
                MotorcycleCatalog.year           == year,
            )
        )).scalars().first()
        if not row:
            raise RuntimeError(f"Catalog entry '{canonical_name}' {year} not found.")
        return row.model_id

    async def get_color_id(name: str) -> int:
        row = (await db.execute(select(Color).where(Color.name == name))).scalars().first()
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
        model_id = await get_catalog_id(canonical_name, year)
        for color_name in colors:
            entries.append(MotorcycleCatalogColor(
                model_id = model_id,
                color_id = await get_color_id(color_name),
            ))

    db.add_all(entries)
    await db.commit()
    print(f"  ✓ Inserted {len(entries)} motorcycle catalog color entries.")


async def seed_credit_institutions(db):
    count = (await db.execute(select(func.count()).select_from(CreditInstitution))).scalar()
    if count > 0:
        print("  → credit_institutions already seeded, skipping.")
        return

    db.add_all([
        CreditInstitution(name="Galgo"),
        CreditInstitution(name="Banco Azteca"),
        CreditInstitution(name="Maxicash"),
    ])
    await db.commit()
    print("  ✓ Inserted 2 credit institutions.")


async def seed_payment_methods(db):
    methods = [
        "Efectivo",
        "Terminal Banamex",
        "Terminal Mifel",
        "Terminal Banorte",
        "Transferencia",
        "Financiera",
    ]
    inserted = 0
    for name in methods:
        existing = (await db.execute(
            select(PaymentMethod).where(PaymentMethod.name == name)
        )).scalars().first()
        if not existing:
            db.add(PaymentMethod(name=name))
            inserted += 1
    await db.commit()
    print(f"  [OK] Inserted {inserted} payment methods.")


async def seed():
    async with AsyncSessionLocal() as db:
        print("\nSeeding database...")
        await seed_dealerships(db)
        await seed_users(db)
        await seed_credit_institutions(db)
        await seed_payment_methods(db)
        await seed_colors(db)
        await seed_motorcycle_catalog(db)
        await seed_motorcycle_model_codes(db)
        await seed_motorcycle_catalog_colors(db)
        print("\nSeed complete.\n")


if __name__ == "__main__":
    asyncio.run(seed())
