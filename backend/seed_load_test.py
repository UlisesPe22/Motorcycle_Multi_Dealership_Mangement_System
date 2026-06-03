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
    return _rand(_UPPER, 4) + _rand(_DIGITS, 6) + _rand(_ALPHANUM, 3)


def _gen_ref() -> str:
    return "MD" + _rand(_ALPHANUM, 15)


def _gen_motor() -> str:
    return _rand(_ALPHANUM, 11)


_STATUS_POOL = (
    [MotorcycleStatus.in_stock]          * 60 +
    [MotorcycleStatus.incoming]          * 20 +
    [MotorcycleStatus.reserved_for_sale] * 10 +
    [MotorcycleStatus.sold]              * 10
)


def _random_status() -> MotorcycleStatus:
    return random.choice(_STATUS_POOL)


# ======================================================================== #
# Seed clients                                                               #
# ======================================================================== #

async def seed_clients(db) -> list:
    count = (await db.execute(select(func.count()).select_from(Client))).scalar()
    if count >= 200:
        print(f"  --clients already has {count} rows, skipping.")
        result = await db.execute(select(Client.client_id))
        return list(result.scalars().all())

    used_curps  = set()
    used_claves = set()
    used_emails = set()
    inserted    = 0

    for i in range(200):
        first = random.choice(first_names)
        last1 = random.choice(last_names)
        last2 = random.choice(last_names)
        nombre = f"{first} {last1} {last2}"
        email  = f"{first.lower()}.{last1.lower()}{i}@gmail.com"

        curp = _gen_curp()
        while curp in used_curps:
            curp = _gen_curp()
        used_curps.add(curp)

        clave = _gen_clave()
        while clave in used_claves:
            clave = _gen_clave()
        used_claves.add(clave)

        while email in used_emails:
            email = f"{first.lower()}.{last1.lower()}{i}_{_rand(_DIGITS, 4)}@gmail.com"
        used_emails.add(email)

        # Each client requires an event and two submissions as non-null FKs
        event = Event(
            event_type   = EventName.client_registration.value,
            initiated_by = 2,
            status       = EventStatus.complete,
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

        client = Client(
            nombre_completo     = nombre,
            curp                = curp,
            clave_de_elector    = clave,
            email               = email,
            phone               = f"55{_rand(_DIGITS, 8)}",
            front_submission_id = front_sub.submission_id,
            back_submission_id  = back_sub.submission_id,
            event_id            = event.event_id,
            registered_by       = 2,
        )
        db.add(client)
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

    result = await db.execute(select(Client.client_id))
    return list(result.scalars().all())


# ======================================================================== #
# Seed motorcycles                                                           #
# ======================================================================== #

async def seed_motorcycles(db, dealership_ids: list, model_ids: list) -> None:
    count = (await db.execute(select(func.count()).select_from(Motorcycle))).scalar()
    if count >= 200:
        print(f"  --motorcycles already has {count} rows, skipping.")
        return

    colors       = ["Negro", "Rojo", "Azul", "Perla", "Gris", "Purpura", "Citrus"]
    used_refs    = set()
    used_motors  = set()
    inserted     = 0

    # Distribute evenly across all dealerships
    per_dealer = 200 // len(dealership_ids)
    extras     = 200 % len(dealership_ids)

    for idx, did in enumerate(dealership_ids):
        n = per_dealer + (1 if idx < extras else 0)
        for _ in range(n):
            ref = _gen_ref()
            while ref in used_refs:
                ref = _gen_ref()
            used_refs.add(ref)

            motor = _gen_motor()
            while motor in used_motors:
                motor = _gen_motor()
            used_motors.add(motor)

            db.add(Motorcycle(
                model_id         = random.choice(model_ids),
                dealership_id    = did,
                color            = random.choice(colors),
                status           = _random_status(),
                reference_number = ref,
                motor_number     = motor,
            ))
            inserted += 1

    await db.commit()
    print(
        f"  [OK] Inserted {inserted} motorcycles "
        f"across {len(dealership_ids)} dealerships "
        f"(~{per_dealer} per dealership)."
    )


# ======================================================================== #
# Seed reservations                                                          #
# ======================================================================== #

async def seed_reservations(
    db,
    vm_id: int,
    iz_id: int,
    model_ids: list,
    client_ids: list,
    color_ids: list,
) -> None:
    count = (await db.execute(select(func.count()).select_from(Reservation))).scalar()
    if count >= 100:
        print(f"  --reservations already has {count} rows, skipping.")
        return

    inserted = 0
    dealership_plan = [vm_id] * 50 + [iz_id] * 50

    for dealership_id in dealership_plan:
        event = Event(
            event_type   = EventName.motorcycle_reservation.value,
            initiated_by = 2,
            status       = EventStatus.complete,
        )
        db.add(event)
        await db.flush()

        reservation = Reservation(
            client_id      = random.choice(client_ids),
            model_id       = random.choice(model_ids),
            dealership_id  = dealership_id,
            deposit_amount = round(random.uniform(2000.0, 8000.0), 2),
            status         = ReservationStatus.active,
            created_by     = 2,
            event_id       = event.event_id,
            created_at     = datetime.utcnow(),
        )
        db.add(reservation)
        await db.flush()

        num_colors    = random.choice([1, 2])
        chosen_colors = random.sample(color_ids, min(num_colors, len(color_ids)))
        for priority, cid in enumerate(chosen_colors, start=1):
            db.add(ReservationColor(
                reservation_id = reservation.reservation_id,
                color_id       = cid,
                priority       = priority,
            ))

        inserted += 1
        if inserted % 25 == 0:
            await db.commit()
            print(f"    ... committed {inserted} reservations")

    await db.commit()
    print(f"  [OK] Inserted {inserted} reservations (50 Via Morelos, 50 Ignacio Zaragoza).")


# ======================================================================== #
# Entry point                                                                #
# ======================================================================== #

async def seed_load_test():
    async with AsyncSessionLocal() as db:
        print("\nLoad-test seeding...\n")

        # ── 1. Read existing reference data ──────────────────────────────
        dealerships = (await db.execute(select(Dealership))).scalars().all()
        if not dealerships:
            print("ERROR: No dealerships found — run seed.py first.")
            return

        dealership_map = {d.name_contract: d.dealership_id for d in dealerships}
        dealership_ids = [d.dealership_id for d in dealerships]

        vm_id = dealership_map.get("Via Morelos")
        iz_id = dealership_map.get("Ignacio Zaragoza")
        if not vm_id or not iz_id:
            print(
                f"ERROR: Could not find Via Morelos or Ignacio Zaragoza. "
                f"Found: {list(dealership_map.keys())}"
            )
            return

        print(f"  Dealerships: {dealership_map}")
        print(f"  Via Morelos id={vm_id}, Ignacio Zaragoza id={iz_id}")

        model_ids = list(
            (await db.execute(select(MotorcycleCatalog.model_id))).scalars().all()
        )
        if not model_ids:
            print("ERROR: No motorcycle catalog entries — run seed.py first.")
            return
        print(f"  Catalog model_ids: {model_ids}")

        color_ids = list(
            (await db.execute(select(Color.color_id))).scalars().all()
        )
        if not color_ids:
            print("ERROR: No colors found — run seed.py first.")
            return
        print(f"  Color ids: {color_ids}\n")

        # ── 2. Seed clients ───────────────────────────────────────────────
        print("Seeding clients...")
        client_ids = await seed_clients(db)

        # ── 3. Seed motorcycles ───────────────────────────────────────────
        print("\nSeeding motorcycles...")
        await seed_motorcycles(db, dealership_ids, model_ids)

        # ── 4. Seed reservations ──────────────────────────────────────────
        print("\nSeeding reservations...")
        await seed_reservations(db, vm_id, iz_id, model_ids, client_ids, color_ids)

        print("\nLoad-test seed complete.\n")


if __name__ == "__main__":
    asyncio.run(seed_load_test())
