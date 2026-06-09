import sys
import os
import asyncio
import random
import string
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from database import AsyncSessionLocal
from config import DISCOUNTS_ACTIVE
from models.client import Client
from models.color import Color
from models.dealership import Dealership
from models.event import Event, EventName, EventStatus, SlotName
from models.motorcycle import Motorcycle, MotorcycleStatus
from models.motorcycle_catalog import MotorcycleCatalog
from models.payment_event import PaymentEvent
from models.payment_item import PaymentItem
from models.payment_method import PaymentMethod
from models.reservation import Reservation, ReservationStatus
from models.reservation_color import ReservationColor
from models.sale import Sale, SaleStatus
from models.submission import Submission, SubmissionStatus

# ======================================================================== #
# Constants                                                                  #
# ======================================================================== #

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

CLIENTS_DATA = [
    ("Carlos Mendoza Rivera",      "MERC850312AB1", "55123456789", "carlos.mendoza@gmail.com"),
    ("Ana Sofia Gutierrez Lopez",  "GULA920815CD2", "55234567890", "ana.gutierrez@gmail.com"),
    ("Jose Luis Ramirez Torres",   "RATJ880601EF3", "55345678901", "jose.ramirez@gmail.com"),
    ("Maria Elena Flores Castro",  "FLCM910420GH4", "55456789012", "maria.flores@gmail.com"),
    ("Roberto Sanchez Morales",    "SAMR870930IJ5", "55567890123", "roberto.sanchez@gmail.com"),
    ("Laura Patricia Diaz Reyes",  "DIRL940715KL6", "55678901234", "laura.diaz@gmail.com"),
    ("Miguel Angel Herrera Vega",  "HEVM960203MN7", "55789012345", "miguel.herrera@gmail.com"),
    ("Gabriela Torres Mendez",     "TOMG830518OP8", "55890123456", "gabriela.torres@gmail.com"),
    ("Fernando Castillo Ruiz",     "CARF910825QR9", "55901234567", "fernando.castillo@gmail.com"),
    ("Veronica Moreno Jimenez",    "MOJV880112ST0", "55012345678", "veronica.moreno@gmail.com"),
    ("Eduardo Vargas Nunez",       "VANE950630UV1", "55123456780", "eduardo.vargas@gmail.com"),
    ("Patricia Romero Aguilar",    "ROAP920445WX2", "55234567801", "patricia.romero@gmail.com"),
    ("Alejandro Cruz Perez",       "CUPA870918YZ3", "55345678012", "alejandro.cruz@gmail.com"),
    ("Isabella Jimenez Salinas",   "JISI940307AB4", "55456780123", "isabella.jimenez@gmail.com"),
]

_ALPHANUM = string.ascii_uppercase + string.digits


def _rand(n: int) -> str:
    return "".join(random.choices(_ALPHANUM, k=n))


def _gen_curp(used: set) -> str:
    while True:
        c = _rand(18)
        if c not in used:
            used.add(c)
            return c


def _gen_ref(used: set) -> str:
    while True:
        r = "MD" + _rand(15)
        if r not in used:
            used.add(r)
            return r


def _gen_motor(used: set) -> str:
    while True:
        m = _rand(11)
        if m not in used:
            used.add(m)
            return m


# ======================================================================== #
# Load reference data                                                        #
# ======================================================================== #

async def load_reference_data(db):
    dealerships = (await db.execute(select(Dealership))).scalars().all()
    if not dealerships:
        raise RuntimeError("No dealerships found — run seed.py first.")

    vm_id  = next((d.dealership_id for d in dealerships if "VIA MORELOS"  in d.name.upper()), None)
    iz_id  = next((d.dealership_id for d in dealerships if "ZARAGOZA"     in d.name.upper()), None)
    tlp_id = next((d.dealership_id for d in dealerships if "TLALPIZAHUAC" in d.name.upper()), None)

    if not vm_id or not iz_id or not tlp_id:
        raise RuntimeError(f"Missing dealership. Found: {[d.name for d in dealerships]}")

    catalog_rows = (await db.execute(select(MotorcycleCatalog))).scalars().all()
    if not catalog_rows:
        raise RuntimeError("No motorcycle catalog entries — run seed.py first.")

    catalog = [
        {
            "model_id":       c.model_id,
            "canonical_name": c.canonical_name,
            "full_price":     c.full_price,
            "discount_price": c.discount_price,
        }
        for c in catalog_rows
    ]

    color_rows        = (await db.execute(select(Color))).scalars().all()
    color_name_to_id  = {c.name: c.color_id for c in color_rows}

    efectivo = (await db.execute(
        select(PaymentMethod).where(PaymentMethod.name == "Efectivo")
    )).scalar_one_or_none()
    if not efectivo:
        raise RuntimeError("PaymentMethod 'Efectivo' not found — run seed.py first.")

    return vm_id, iz_id, tlp_id, catalog, color_name_to_id, efectivo.method_id


# ======================================================================== #
# Seed 14 clients                                                            #
# ======================================================================== #

async def seed_clients(db) -> list:
    """Returns list of client_ids in insertion order (index 0-13)."""
    used_curps = set()
    client_ids = []

    for nombre, rfc, phone, email in CLIENTS_DATA:
        curp = _gen_curp(used_curps)

        event = Event(
            event_type   = EventName.client_registration.value,
            initiated_by = 2,
            status       = EventStatus.complete,
            started_at   = datetime.now(timezone.utc).replace(tzinfo=None),
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
            clave_de_elector    = rfc,
            email               = email,
            phone               = phone,
            front_submission_id = front_sub.submission_id,
            back_submission_id  = back_sub.submission_id,
            event_id            = event.event_id,
            registered_by       = 2,
        )
        db.add(client)
        await db.flush()
        client_ids.append(client.client_id)

    await db.commit()
    print(f"[OK] Inserted {len(client_ids)} clients")
    return client_ids


# ======================================================================== #
# Seed 120 motorcycles                                                       #
# ======================================================================== #

async def seed_motorcycles(db, vm_id, iz_id, tlp_id, catalog, color_name_to_id) -> dict:
    """Returns {dealership_id: [moto_dict, ...]} for all seeded motos."""
    used_refs   = set()
    used_motors = set()
    inserted    = 0
    motos_by_dealership = {vm_id: [], iz_id: [], tlp_id: []}

    for did in [vm_id, iz_id, tlp_id]:
        for _ in range(40):
            entry          = random.choice(catalog)
            canonical_name = entry["canonical_name"]
            color          = random.choice(VALID_COLORS[canonical_name])
            ref            = _gen_ref(used_refs)
            motor          = _gen_motor(used_motors)

            moto = Motorcycle(
                model_id         = entry["model_id"],
                dealership_id    = did,
                color            = color,
                status           = MotorcycleStatus.in_stock,
                reference_number = ref,
                motor_number     = motor,
            )
            db.add(moto)
            await db.flush()

            motos_by_dealership[did].append({
                "motorcycle_id":  moto.motorcycle_id,
                "model_id":       entry["model_id"],
                "canonical_name": canonical_name,
                "full_price":     entry["full_price"],
                "discount_price": entry["discount_price"],
            })

            inserted += 1
            if inserted % 20 == 0:
                await db.commit()

    await db.commit()
    print(f"[OK] Inserted {inserted} motorcycles (40 per dealership, all in_stock)")
    return motos_by_dealership


# ======================================================================== #
# Seed 6 reservations                                                        #
# ======================================================================== #

async def seed_reservations(
    db, vm_id, iz_id, tlp_id,
    client_ids, color_name_to_id, motos_by_dealership, efectivo_method_id,
):
    inserted      = 0
    motos_locked  = 0
    sales_created = 0
    used_moto_ids = set()

    # clients 0-1 → Via Morelos, 2-3 → Ignacio Zaragoza, 4-5 → Tlalpizahuac
    plan = [
        (vm_id,  [client_ids[0], client_ids[1]]),
        (iz_id,  [client_ids[2], client_ids[3]]),
        (tlp_id, [client_ids[4], client_ids[5]]),
    ]

    for did, res_client_ids in plan:
        available = [m for m in motos_by_dealership[did] if m["motorcycle_id"] not in used_moto_ids]

        for client_id in res_client_ids:
            moto_info = random.choice(available)
            available = [m for m in available if m["motorcycle_id"] != moto_info["motorcycle_id"]]
            used_moto_ids.add(moto_info["motorcycle_id"])

            canonical_name = moto_info["canonical_name"]
            color_name     = random.choice(VALID_COLORS[canonical_name])
            color_id       = color_name_to_id[color_name]
            deposit_amount = round(random.uniform(2000.0, 8000.0), 2)
            total_price    = moto_info["discount_price"] if DISCOUNTS_ACTIVE else moto_info["full_price"]

            reservation = Reservation(
                client_id      = client_id,
                model_id       = moto_info["model_id"],
                dealership_id  = did,
                deposit_amount = deposit_amount,
                status         = ReservationStatus.active,
                created_by     = 2,
                event_id       = None,
                created_at     = datetime.now(timezone.utc).replace(tzinfo=None),
            )
            db.add(reservation)
            await db.flush()

            reservation.status = ReservationStatus.assigned

            db.add(ReservationColor(
                reservation_id = reservation.reservation_id,
                color_id       = color_id,
                priority       = 1,
            ))

            result = await db.execute(
                select(Motorcycle).where(Motorcycle.motorcycle_id == moto_info["motorcycle_id"])
            )
            moto                = result.scalar_one()
            moto.status         = MotorcycleStatus.in_stock_reserved
            moto.reservation_id = reservation.reservation_id
            motos_locked       += 1

            await db.flush()

            sale = Sale(
                motorcycle_id   = moto_info["motorcycle_id"],
                client_id       = client_id,
                vendor_id       = 2,
                dealership_id   = did,
                total_price     = total_price,
                amount_verified = 0.0,
                status          = SaleStatus.open.value,
            )
            db.add(sale)
            await db.flush()

            payment_event = PaymentEvent(
                sale_id         = sale.sale_id,
                event_type      = "reservation",
                status          = "pending",
                expected_amount = deposit_amount,
                created_by      = 2,
            )
            db.add(payment_event)
            await db.flush()

            db.add(PaymentItem(
                payment_event_id = payment_event.payment_event_id,
                amount           = deposit_amount,
                method_id        = efectivo_method_id,
                status           = "pending",
            ))

            inserted      += 1
            sales_created += 1

            if inserted % 2 == 0:
                await db.commit()

    await db.commit()
    print(f"[OK] Inserted {inserted} reservations (2 Via Morelos, 2 Ignacio Zaragoza, 2 Tlalpizahuac)")
    print(f"[OK] {motos_locked} motos set to in_stock_reserved")
    print(f"[OK] {sales_created} Sale + PaymentEvent + PaymentItem records created")


# ======================================================================== #
# Entry point                                                                #
# ======================================================================== #

async def seed_load_test():
    async with AsyncSessionLocal() as db:
        print("\nLoad-test seeding...\n")

        vm_id, iz_id, tlp_id, catalog, color_name_to_id, efectivo_method_id = \
            await load_reference_data(db)

        client_ids          = await seed_clients(db)
        motos_by_dealership = await seed_motorcycles(db, vm_id, iz_id, tlp_id, catalog, color_name_to_id)
        await seed_reservations(
            db, vm_id, iz_id, tlp_id,
            client_ids, color_name_to_id, motos_by_dealership, efectivo_method_id,
        )

        print()


if __name__ == "__main__":
    asyncio.run(seed_load_test())
