"""
seed_load_test.py — Populates the DB with realistic load-test data.

Prerequisite: seed.py has already been run (users, dealerships, colors,
catalog, model codes, catalog colors, credit institutions must exist).

Inserts:
  - 200 clients  (each backed by a minimal event + 2 submissions for FK integrity)
  - 200 motorcycles  (67 Via Morelos / 67 Ignacio Zaragoza / 66 Tlalpizahuac;
                      first 20 of each main dealership are incoming, rest in_stock)
  - 60 reservations  (30 Via Morelos / 30 Ignacio Zaragoza, pointing at
                      incoming motorcycles with valid catalog colors)

Each section is idempotent: skipped when the target count already exists.
"""

import sys
import os
import asyncio
import random
import string
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func

from database import AsyncSessionLocal
from models.client import Client
from models.color import Color
from models.dealership import Dealership
from models.event import Event, EventName, EventStatus, SlotName
from models.motorcycle import Motorcycle, MotorcycleStatus
from models.motorcycle_catalog import MotorcycleCatalog
from models.reservation import Reservation, ReservationStatus
from models.reservation_color import ReservationColor
from models.submission import Submission, SubmissionStatus
from services.pipeline_utils import create_event

# ======================================================================== #
# Constants                                                                  #
# ======================================================================== #

first_names = [
    "Juan", "Maria", "Carlos", "Ana", "Luis", "Rosa", "Pedro", "Carmen",
    "Jorge", "Patricia", "Miguel", "Laura", "Roberto", "Sandra", "Francisco",
    "Monica", "Antonio", "Veronica", "Manuel", "Alejandra",
]
last_names = [
    "Garcia", "Martinez", "Lopez", "Hernandez", "Gonzalez", "Perez",
    "Rodriguez", "Sanchez", "Ramirez", "Torres", "Flores", "Rivera",
    "Gomez", "Diaz", "Cruz", "Morales", "Reyes", "Gutierrez", "Ortiz", "Chavez",
]

VALID_COLORS = {
    "Pulsar N125 FI-CBS":  ["Purpura", "Citrus",  "Rojo"],
    "Pulsar N125 Car":     ["Citrus",  "Purpura"],
    "Pulsar N160":         ["Perla",   "Azul"],
    "Pulsar N160 Premium": ["Rojo",    "Azul",    "Negro"],
    "Pulsar N250 FI ABS":  ["Perla",   "Rojo",    "Negro"],
    "Dominar 250":         ["Negro",   "Rojo"],
    "Dominar 400 UG":      ["Negro"],
    "Pulsar NS200":        ["Negro",   "Rojo"],
    "Pulsar RS200":        ["Perla"],
    "Pulsar NS400Z":       ["Gris",    "Rojo"],
}

_UPPER    = string.ascii_uppercase
_DIGITS   = string.digits
_ALPHANUM = _UPPER + _DIGITS


def _rand(chars: str, n: int) -> str:
    return "".join(random.choices(chars, k=n))


def _gen_curp() -> str:
    return _rand(_ALPHANUM, 18)


def _gen_clave() -> str:
    return _rand(_ALPHANUM, 18)


def _gen_rfc() -> str:
    day   = f"{random.randint(1, 28):02d}"
    month = f"{random.randint(1, 12):02d}"
    year  = f"{random.randint(50, 99):02d}"
    return _rand(_UPPER, 4) + day + month + year + _rand(_ALPHANUM, 3)


def _gen_ref() -> str:
    return "MD" + _rand(_ALPHANUM, 15)


def _gen_motor() -> str:
    return _rand(_ALPHANUM, 11)


# ======================================================================== #
# Step 1 — Query existing reference data                                    #
# ======================================================================== #

async def load_reference_data(db):
    dealerships = (await db.execute(select(Dealership))).scalars().all()
    if not dealerships:
        raise RuntimeError("No dealerships found — run seed.py first.")

    via_morelos_id = next(
        (d.dealership_id for d in dealerships if "VIA MORELOS" in d.name.upper()), None
    )
    ignacio_zaragoza_id = next(
        (d.dealership_id for d in dealerships if "ZARAGOZA" in d.name.upper()), None
    )
    tlalpizahuac_id = next(
        (d.dealership_id for d in dealerships if "TLALPIZAHUAC" in d.name.upper()), None
    )

    if not via_morelos_id or not ignacio_zaragoza_id or not tlalpizahuac_id:
        names = [d.name for d in dealerships]
        raise RuntimeError(f"Missing a required dealership. Found: {names}")

    catalog_rows = (await db.execute(select(MotorcycleCatalog))).scalars().all()
    if not catalog_rows:
        raise RuntimeError("No motorcycle catalog entries — run seed.py first.")

    catalog = [
        {
            "model_id":       c.model_id,
            "canonical_name": c.canonical_name,
            "year":           c.year,
        }
        for c in catalog_rows
    ]

    color_rows = (await db.execute(select(Color))).scalars().all()
    if not color_rows:
        raise RuntimeError("No colors found — run seed.py first.")
    color_name_to_id = {c.name: c.color_id for c in color_rows}

    print(f"  via_morelos_id={via_morelos_id}, "
          f"ignacio_zaragoza_id={ignacio_zaragoza_id}, "
          f"tlalpizahuac_id={tlalpizahuac_id}")
    print(f"  catalog: {len(catalog)} entries")
    print(f"  colors: {list(color_name_to_id.keys())}")

    return (
        via_morelos_id,
        ignacio_zaragoza_id,
        tlalpizahuac_id,
        catalog,
        color_name_to_id,
    )


# ======================================================================== #
# Step 2 — Seed 200 clients                                                 #
# ======================================================================== #

async def seed_clients(db) -> tuple:
    """Returns (inserted_count, [client_id, ...])."""
    count = (await db.execute(select(func.count()).select_from(Client))).scalar()
    if count >= 200:
        print(f"  -- clients already has {count} rows, skipping.")
        ids = list((await db.execute(select(Client.client_id))).scalars().all())
        return 0, ids

    used_curps  = set()
    used_claves = set()
    inserted    = 0

    for i in range(200):
        first        = random.choice(first_names)
        last1, last2 = random.sample(last_names, 2)
        nombre       = f"{first} {last1} {last2}"
        email        = f"client{i:03d}@loadtest.com"
        phone        = f"55{i:08d}"

        curp = _gen_curp()
        while curp in used_curps:
            curp = _gen_curp()
        used_curps.add(curp)

        clave = _gen_clave()
        while clave in used_claves:
            clave = _gen_clave()
        used_claves.add(clave)

        # Client.front_submission_id, back_submission_id, event_id are NOT NULL FKs.
        # Create minimal stubs to satisfy integrity.
        event = Event(
            event_type   = EventName.client_registration.value,
            initiated_by = 2,
            status       = EventStatus.complete,
            started_at   = datetime.utcnow(),
        )
        db.add(event)
        await db.flush()

        front_sub = Submission(
            event_id    = event.event_id,
            slot_number = 1,
            slot_name   = SlotName.id_front.value,
            status      = SubmissionStatus.complete,
        )
        back_sub = Submission(
            event_id    = event.event_id,
            slot_number = 2,
            slot_name   = SlotName.id_back.value,
            status      = SubmissionStatus.complete,
        )
        db.add(front_sub)
        db.add(back_sub)
        await db.flush()

        db.add(Client(
            nombre_completo     = nombre,
            curp                = curp,
            clave_de_elector    = clave,
            email               = email,
            phone               = phone,
            front_submission_id = front_sub.submission_id,
            back_submission_id  = back_sub.submission_id,
            event_id            = event.event_id,
            registered_by       = 2,
        ))
        await db.flush()
        inserted += 1

        if inserted % 50 == 0:
            await db.commit()
            print(f"    ... committed {inserted} clients")

    await db.commit()
    print(
        f"  [OK] Inserted {inserted} clients "
        f"(+ {inserted} events, {inserted * 2} submissions)."
    )
    ids = list((await db.execute(select(Client.client_id))).scalars().all())
    return inserted, ids


# ======================================================================== #
# Step 3 — Seed 200 motorcycles                                             #
# ======================================================================== #

async def seed_motorcycles(
    db,
    via_morelos_id: int,
    ignacio_zaragoza_id: int,
    tlalpizahuac_id: int,
    catalog: list,
    color_name_to_id: dict,
) -> tuple:
    """
    Returns (inserted_count, incoming_by_dealership).
    incoming_by_dealership = {dealership_id: [{motorcycle_id, model_id, canonical_name}]}
    """
    count = (await db.execute(select(func.count()).select_from(Motorcycle))).scalar()
    if count >= 200:
        print(f"  -- motorcycles already has {count} rows, skipping.")
        rows = (await db.execute(
            select(Motorcycle, MotorcycleCatalog)
            .join(MotorcycleCatalog, Motorcycle.model_id == MotorcycleCatalog.model_id)
            .where(
                Motorcycle.status == MotorcycleStatus.incoming,
                Motorcycle.dealership_id.in_([via_morelos_id, ignacio_zaragoza_id]),
            )
        )).all()
        incoming: dict = {}
        for moto, cat in rows:
            incoming.setdefault(moto.dealership_id, []).append({
                "motorcycle_id":  moto.motorcycle_id,
                "model_id":       moto.model_id,
                "canonical_name": cat.canonical_name,
            })
        return 0, incoming

    used_refs   = set()
    used_motors = set()
    inserted    = 0
    incoming: dict = {
        via_morelos_id:      [],
        ignacio_zaragoza_id: [],
    }

    # (dealership_id, total, n_incoming)
    batches = [
        (via_morelos_id,      67, 20),
        (ignacio_zaragoza_id, 67, 20),
        (tlalpizahuac_id,     66,  0),
    ]

    for did, total, n_incoming in batches:
        for i in range(total):
            entry          = random.choice(catalog)
            canonical_name = entry["canonical_name"]
            color          = random.choice(VALID_COLORS[canonical_name])

            ref = _gen_ref()
            while ref in used_refs:
                ref = _gen_ref()
            used_refs.add(ref)

            motor = _gen_motor()
            while motor in used_motors:
                motor = _gen_motor()
            used_motors.add(motor)

            status = (
                MotorcycleStatus.incoming
                if i < n_incoming
                else MotorcycleStatus.in_stock
            )

            moto = Motorcycle(
                model_id         = entry["model_id"],
                dealership_id    = did,
                color            = color,
                status           = status,
                reference_number = ref,
                motor_number     = motor,
            )
            db.add(moto)
            await db.flush()

            if status == MotorcycleStatus.incoming and did in incoming:
                incoming[did].append({
                    "motorcycle_id":  moto.motorcycle_id,
                    "model_id":       entry["model_id"],
                    "canonical_name": canonical_name,
                })

            inserted += 1
            if inserted % 50 == 0:
                await db.commit()
                print(f"    ... committed {inserted} motorcycles")

    await db.commit()
    print(
        f"  [OK] Inserted {inserted} motorcycles "
        f"(20 incoming Via Morelos, 20 incoming Ignacio Zaragoza, rest in_stock)."
    )
    return inserted, incoming


# ======================================================================== #
# Step 4 — Seed 60 reservations                                             #
# ======================================================================== #

async def seed_reservations(
    db,
    via_morelos_id: int,
    ignacio_zaragoza_id: int,
    client_ids: list,
    color_name_to_id: dict,
    incoming: dict,
) -> int:
    """Returns inserted_count."""
    count = (await db.execute(select(func.count()).select_from(Reservation))).scalar()
    if count >= 60:
        print(f"  -- reservations already has {count} rows, skipping.")
        return 0

    inserted = 0
    plan = [
        (via_morelos_id,      30),
        (ignacio_zaragoza_id, 30),
    ]

    for dealership_id, n in plan:
        pool = incoming.get(dealership_id, [])
        if not pool:
            print(
                f"  WARNING: no incoming motorcycles found for dealership "
                f"{dealership_id}, skipping its {n} reservations."
            )
            continue

        for _ in range(n):
            moto_info      = random.choice(pool)
            canonical_name = moto_info["canonical_name"]
            color_name     = random.choice(VALID_COLORS[canonical_name])
            color_id       = color_name_to_id[color_name]

            event = await create_event(db, EventName.motorcycle_reservation.value, 2)

            reservation = Reservation(
                client_id      = random.choice(client_ids),
                model_id       = moto_info["model_id"],
                dealership_id  = dealership_id,
                deposit_amount = round(random.uniform(2000.0, 8000.0), 2),
                status         = ReservationStatus.active,
                created_by     = 2,
                event_id       = event.event_id,
                created_at     = datetime.utcnow(),
            )
            db.add(reservation)
            await db.flush()

            db.add(ReservationColor(
                reservation_id = reservation.reservation_id,
                color_id       = color_id,
                priority       = 1,
            ))

            inserted += 1
            if inserted % 10 == 0:
                await db.commit()
                print(f"    ... committed {inserted} reservations")

    await db.commit()
    print(
        f"  [OK] Inserted {inserted} reservations "
        f"(30 Via Morelos, 30 Ignacio Zaragoza) "
        f"with valid colors pointing to incoming motos."
    )
    return inserted


# ======================================================================== #
# Entry point                                                                #
# ======================================================================== #

async def seed_load_test():
    async with AsyncSessionLocal() as db:
        print("\nLoad-test seeding...\n")

        (
            via_morelos_id,
            ignacio_zaragoza_id,
            tlalpizahuac_id,
            catalog,
            color_name_to_id,
        ) = await load_reference_data(db)

        print("\nSeeding clients...")
        clients_inserted, client_ids = await seed_clients(db)

        print("\nSeeding motorcycles...")
        motos_inserted, incoming = await seed_motorcycles(
            db,
            via_morelos_id,
            ignacio_zaragoza_id,
            tlalpizahuac_id,
            catalog,
            color_name_to_id,
        )

        print("\nSeeding reservations...")
        reservations_inserted = await seed_reservations(
            db,
            via_morelos_id,
            ignacio_zaragoza_id,
            client_ids,
            color_name_to_id,
            incoming,
        )

        # Final DB counts (actual state, not just what this run inserted)
        final_clients      = (await db.execute(select(func.count()).select_from(Client))).scalar()
        final_motos        = (await db.execute(select(func.count()).select_from(Motorcycle))).scalar()
        final_reservations = (await db.execute(select(func.count()).select_from(Reservation))).scalar()

        print(f"\n[OK] Seeded {clients_inserted} clients  (DB total: {final_clients})")
        print(
            f"[OK] Seeded {motos_inserted} motorcycles "
            f"(20 incoming Via Morelos, 20 incoming Ignacio Zaragoza, rest available)"
            f"  (DB total: {final_motos})"
        )
        print(
            f"[OK] Seeded {reservations_inserted} reservations "
            f"(30 Via Morelos, 30 Ignacio Zaragoza) "
            f"with valid colors pointing to incoming motos"
            f"  (DB total: {final_reservations})"
        )
        print()


if __name__ == "__main__":
    asyncio.run(seed_load_test())
