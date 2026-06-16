import sys
import os
import asyncio
import random
import string
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from database import AsyncSessionLocal
from config import DISCOUNTS_ACTIVE
from models.client import Client
from models.credit_institution import CreditInstitution
from models.color import Color
from models.dealership import Dealership
from models.event import Event, EventName, EventStatus, SlotName
from models.manual_status_change import ManualStatusChange
from models.motorcycle import Motorcycle, MotorcycleStatus
from models.motorcycle_catalog import MotorcycleCatalog
from models.payment_event import PaymentEvent
from models.payment_item import PaymentItem
from models.payment_method import PaymentMethod
from models.reservation import Reservation, ReservationStatus
from models.reservation_color import ReservationColor
from models.sale import Sale, SaleStatus
from models.submission import Submission, SubmissionStatus
from models.user import User

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

# Three vendors per dealership, ordered to match [vm_id, iz_id, tlp_id].
VENDOR_NAMES_BY_DEALERSHIP = [
    ["Sergio Beltran Ramos",  "Diana Lozano Vega",     "Raul Espinoza Mora"],      # BAJAJ VIA MORELOS
    ["Andrea Salas Nieto",    "Hugo Martinez Pena",    "Claudia Rios Fuentes"],    # BAJAJ IGNACIO ZARAGOZA
    ["Oscar Navarro Leon",    "Paola Cervantes Gil",   "Ivan Delgado Soto"],       # BAJAJ TLALPIZAHUAC
]

CANCEL_REASONS = [
    "Cliente desistio de la compra",
    "Pago no completado a tiempo",
    "Cliente no localizable",
    "Cambio de modelo solicitado",
    "Financiamiento rechazado",
    "Cliente encontro un mejor precio",
    "Documentacion incompleta",
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
            initiated_by = 1,
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
            registered_by       = 1,
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
                vendor_id       = 1,
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
                created_by      = 1,
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
# Seed verified sales for contract testing                                   #
# ======================================================================== #

async def seed_verified_sales(db, vm_id, efectivo_method_id):
    terminal_banamex_method = (await db.execute(
        select(PaymentMethod).where(PaymentMethod.name == "Terminal Banamex")
    )).scalar_one_or_none()
    if not terminal_banamex_method:
        raise RuntimeError("PaymentMethod 'Terminal Banamex' not found.")
    terminal_banamex_method_id = terminal_banamex_method.method_id

    financiera_method = (await db.execute(
        select(PaymentMethod).where(PaymentMethod.name == "Financiera")
    )).scalar_one_or_none()
    if not financiera_method:
        raise RuntimeError("PaymentMethod 'Financiera' not found.")
    financiera_method_id = financiera_method.method_id

    first_credit_institution = (await db.execute(
        select(CreditInstitution).limit(1)
    )).scalar_one_or_none()
    if not first_credit_institution:
        raise RuntimeError("No CreditInstitution found.")
    first_credit_institution_id = first_credit_institution.credit_institution_id

    motos_result = await db.execute(
        select(Motorcycle)
        .options(joinedload(Motorcycle.model))
        .where(
            Motorcycle.dealership_id == vm_id,
            Motorcycle.status == MotorcycleStatus.in_stock,
        )
        .limit(3)
    )
    motos = motos_result.unique().scalars().all()
    if len(motos) < 3:
        raise RuntimeError(f"Not enough in_stock motos at Via Morelos. Found {len(motos)}.")
    moto1, moto2, moto3 = motos[0], motos[1], motos[2]

    used_curps = set()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    async def _make_client(nombre, rfc, phone, email):
        curp = _gen_curp(used_curps)
        event = Event(
            event_type   = EventName.client_registration.value,
            initiated_by = 2,
            status       = EventStatus.complete,
            started_at   = now,
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
            registered_by       = 4,
        )
        db.add(client)
        await db.flush()
        return client

    # ── Client 1 — Al Contado with prior Reservation ─────────────────────
    client1 = await _make_client(
        "Diego Armando Solis Vargas", "SOVD910315HM2", "55119988776", "diego.solis@gmail.com"
    )
    total1 = moto1.model.full_price
    sale1 = Sale(
        motorcycle_id   = moto1.motorcycle_id,
        client_id       = client1.client_id,
        vendor_id       = 1,
        dealership_id   = vm_id,
        total_price     = total1,
        amount_verified = total1,
        status          = SaleStatus.verified.value,
        created_at      = now,
    )
    db.add(sale1)
    await db.flush()

    ev1_res = PaymentEvent(
        sale_id         = sale1.sale_id,
        event_type      = "reservation",
        status          = "verified",
        expected_amount = 5000.0,
        created_by      = 1,
        created_at      = now,
    )
    db.add(ev1_res)
    await db.flush()
    db.add(PaymentItem(
        payment_event_id = ev1_res.payment_event_id,
        amount           = 5000.0,
        method_id        = efectivo_method_id,
        status           = "verified",
        created_at       = now,
    ))

    ev1_cto = PaymentEvent(
        sale_id         = sale1.sale_id,
        event_type      = "al_contado",
        status          = "verified",
        expected_amount = total1 - 5000.0,
        created_by      = 1,
        created_at      = now,
    )
    db.add(ev1_cto)
    await db.flush()
    db.add(PaymentItem(
        payment_event_id = ev1_cto.payment_event_id,
        amount           = total1 - 5000.0,
        method_id        = efectivo_method_id,
        status           = "verified",
        created_at       = now,
    ))
    moto1.status = MotorcycleStatus.sale_in_progress
    await db.flush()

    # ── Client 2 — Enganche with prior Reservation ────────────────────────
    client2 = await _make_client(
        "Lorena Isabel Mora Fuentes", "MOFL940822MN3", "55229877665", "lorena.mora@gmail.com"
    )
    total2 = moto2.model.full_price
    sale2 = Sale(
        motorcycle_id   = moto2.motorcycle_id,
        client_id       = client2.client_id,
        vendor_id       = 1,
        dealership_id   = vm_id,
        total_price     = total2,
        amount_verified = total2,
        status          = SaleStatus.verified.value,
        created_at      = now,
    )
    db.add(sale2)
    await db.flush()

    ev2_res = PaymentEvent(
        sale_id         = sale2.sale_id,
        event_type      = "reservation",
        status          = "verified",
        expected_amount = 3000.0,
        created_by      = 1,
        created_at      = now,
    )
    db.add(ev2_res)
    await db.flush()
    db.add(PaymentItem(
        payment_event_id = ev2_res.payment_event_id,
        amount           = 3000.0,
        method_id        = efectivo_method_id,
        status           = "verified",
        created_at       = now,
    ))

    ev2_eng = PaymentEvent(
        sale_id         = sale2.sale_id,
        event_type      = "enganche",
        status          = "verified",
        expected_amount = 18000.0,
        created_by      = 1,
        created_at      = now,
    )
    db.add(ev2_eng)
    await db.flush()
    db.add(PaymentItem(
        payment_event_id = ev2_eng.payment_event_id,
        amount           = 10000.0,
        method_id        = efectivo_method_id,
        status           = "verified",
        created_at       = now,
    ))
    db.add(PaymentItem(
        payment_event_id = ev2_eng.payment_event_id,
        amount           = 8000.0,
        method_id        = terminal_banamex_method_id,
        status           = "verified",
        created_at       = now,
    ))

    financing_amount2 = total2 - 3000.0 - 10000.0 - 8000.0
    ev2_fin = PaymentEvent(
        sale_id         = sale2.sale_id,
        event_type      = "financing",
        status          = "verified",
        expected_amount = financing_amount2,
        created_by      = 1,
        created_at      = now,
    )
    db.add(ev2_fin)
    await db.flush()
    db.add(PaymentItem(
        payment_event_id = ev2_fin.payment_event_id,
        amount           = financing_amount2,
        method_id        = financiera_method_id,
        financiera_id    = first_credit_institution_id,
        status           = "verified",
        created_at       = now,
    ))
    moto2.status = MotorcycleStatus.sale_in_progress
    await db.flush()

    # ── Client 3 — Al Contado only (no reservation) ───────────────────────
    client3 = await _make_client(
        "Hector Emmanuel Ruiz Avila", "RUAH881107KL4", "55339766554", "hector.ruiz@gmail.com"
    )
    total3 = moto3.model.full_price
    sale3 = Sale(
        motorcycle_id   = moto3.motorcycle_id,
        client_id       = client3.client_id,
        vendor_id       = 1,
        dealership_id   = vm_id,
        total_price     = total3,
        amount_verified = total3,
        status          = SaleStatus.verified.value,
        created_at      = now,
    )
    db.add(sale3)
    await db.flush()

    ev3_cto = PaymentEvent(
        sale_id         = sale3.sale_id,
        event_type      = "al_contado",
        status          = "verified",
        expected_amount = total3,
        created_by      = 1,
        created_at      = now,
    )
    db.add(ev3_cto)
    await db.flush()
    db.add(PaymentItem(
        payment_event_id = ev3_cto.payment_event_id,
        amount           = total3,
        method_id        = efectivo_method_id,
        status           = "verified",
        created_at       = now,
    ))
    moto3.status = MotorcycleStatus.sale_in_progress
    await db.flush()

    await db.commit()
    print("[OK] Inserted 3 clients with verified sales for contract testing")


# ======================================================================== #
# Seed vendors (3 per dealership) for the owner dashboard                     #
# ======================================================================== #

async def seed_vendors(db, ordered_dealership_ids) -> dict:
    """Create 3 `vendor`-role users per dealership.

    Returns {dealership_id: [user_id, ...]}. Idempotent: reuses any vendor that
    already exists (matched by email).
    """
    from services.auth import hash_password

    vendors_by_dealership = {}
    created = 0

    for idx, did in enumerate(ordered_dealership_ids):
        ids = []
        for name in VENDOR_NAMES_BY_DEALERSHIP[idx]:
            slug  = name.lower().replace(" ", ".")
            email = f"{slug}@bajaj.com"

            existing = (await db.execute(
                select(User).where(User.email == email)
            )).scalar_one_or_none()
            if existing:
                ids.append(existing.user_id)
                continue

            user = User(
                name            = name,
                email           = email,
                username        = slug,
                hashed_password = hash_password("test123"),
                role            = "vendor",
                dealership_id   = did,
                is_active       = True,
                created_by      = 2,
            )
            db.add(user)
            await db.flush()
            ids.append(user.user_id)
            created += 1

        vendors_by_dealership[did] = ids

    await db.commit()
    print(f"[OK] Inserted {created} vendors (3 per dealership)")
    return vendors_by_dealership


# ======================================================================== #
# Seed owner-dashboard activity (sales, reservations, cancellations)         #
# ======================================================================== #

async def seed_dashboard_activity(
    db, ordered_dealership_ids, vendors_by_dealership,
    client_ids, catalog, color_name_to_id, efectivo_method_id,
):
    """Populate every owner-dashboard variable, per dealership, per vendor.

    Generates, for each vendor, a spread of:
      • complete  sales  → summary.sold        / vendor.sold
      • open/verified    → summary.in_progress / vendor.in_progress
      • reservations     → summary.reserved    / vendor.reservations
      • sale_cancelled   → cancelled table     / vendor.cancelled
        (with a motorcycle → "Venta Cancelada"; without → "Reserva")

    All `created_at` values land inside the current calendar month so they fall
    within the dashboard's default [first-of-month → today] window.
    """
    now = datetime.now()

    def ts():
        """Random naive datetime within the current month, up to `now`."""
        return now - timedelta(
            days    = random.randint(0, max(0, now.day - 1)),
            hours   = random.randint(0, 23),
            minutes = random.randint(0, 59),
        )

    totals = {"sold": 0, "in_progress": 0, "reserved": 0, "cancelled": 0}

    for did in ordered_dealership_ids:
        vendor_ids = vendors_by_dealership[did]

        # Fresh pool of unsold units for this dealership.
        moto_pool = (await db.execute(
            select(Motorcycle)
            .options(joinedload(Motorcycle.model))
            .where(
                Motorcycle.dealership_id == did,
                Motorcycle.status == MotorcycleStatus.in_stock,
            )
        )).unique().scalars().all()
        moto_pool = list(moto_pool)

        def take_moto():
            return moto_pool.pop() if moto_pool else None

        for vendor_id in vendor_ids:
            # ── Completed sales (sold) ───────────────────────────────────
            for _ in range(random.randint(3, 6)):
                moto = take_moto()
                if not moto:
                    break
                total   = moto.model.full_price
                created = ts()
                db.add(Sale(
                    motorcycle_id   = moto.motorcycle_id,
                    client_id       = random.choice(client_ids),
                    vendor_id       = vendor_id,
                    dealership_id   = did,
                    total_price     = total,
                    amount_verified = total,
                    status          = SaleStatus.complete.value,
                    created_at      = created,
                ))
                moto.status = MotorcycleStatus.sold
                totals["sold"] += 1

            # ── Sales in progress (open / verified) ──────────────────────
            for _ in range(random.randint(1, 3)):
                moto = take_moto()
                if not moto:
                    break
                total   = moto.model.full_price
                created = ts()
                status  = random.choice([SaleStatus.open.value, SaleStatus.verified.value])
                db.add(Sale(
                    motorcycle_id   = moto.motorcycle_id,
                    client_id       = random.choice(client_ids),
                    vendor_id       = vendor_id,
                    dealership_id   = did,
                    total_price     = total,
                    amount_verified = round(total * 0.3, 2) if status == SaleStatus.verified.value else 0.0,
                    status          = status,
                    created_at      = created,
                ))
                moto.status = MotorcycleStatus.sale_in_progress
                totals["in_progress"] += 1

            # ── Live reservations (active / assigned) ────────────────────
            for _ in range(random.randint(1, 3)):
                entry    = random.choice(catalog)
                created  = ts()
                deposit  = round(random.uniform(2000.0, 8000.0), 2)
                reservation = Reservation(
                    client_id      = random.choice(client_ids),
                    model_id       = entry["model_id"],
                    dealership_id  = did,
                    deposit_amount = deposit,
                    status         = random.choice([ReservationStatus.active, ReservationStatus.assigned]),
                    created_by     = vendor_id,
                    event_id       = None,
                    created_at     = created,
                )
                db.add(reservation)
                await db.flush()

                color_name = random.choice(VALID_COLORS[entry["canonical_name"]])
                db.add(ReservationColor(
                    reservation_id = reservation.reservation_id,
                    color_id       = color_name_to_id[color_name],
                    priority       = 1,
                ))
                totals["reserved"] += 1

            # ── Cancelled sales (with a motorcycle → "Venta Cancelada") ──
            for _ in range(random.randint(0, 2)):
                moto = take_moto()
                if not moto:
                    break
                created = ts()
                sale = Sale(
                    motorcycle_id   = moto.motorcycle_id,
                    client_id       = random.choice(client_ids),
                    vendor_id       = vendor_id,
                    dealership_id   = did,
                    total_price     = moto.model.full_price,
                    amount_verified = 0.0,
                    status          = SaleStatus.refunded.value,
                    created_at      = created,
                )
                db.add(sale)
                await db.flush()
                db.add(ManualStatusChange(
                    event_type    = "sale_cancelled",
                    motorcycle_id = moto.motorcycle_id,
                    sale_id       = sale.sale_id,
                    reason        = random.choice(CANCEL_REASONS),
                    performed_by  = vendor_id,
                    created_at    = created,
                ))
                moto.status = MotorcycleStatus.in_stock  # released back to stock
                totals["cancelled"] += 1

            # ── Cancelled reservation (no motorcycle → "Reserva") ────────
            if random.random() < 0.6:
                entry   = random.choice(catalog)
                created = ts()
                sale = Sale(
                    motorcycle_id   = None,
                    client_id       = random.choice(client_ids),
                    vendor_id       = vendor_id,
                    dealership_id   = did,
                    total_price     = entry["full_price"],
                    amount_verified = 0.0,
                    status          = SaleStatus.refunded.value,
                    created_at      = created,
                )
                db.add(sale)
                await db.flush()
                db.add(ManualStatusChange(
                    event_type   = "sale_cancelled",
                    sale_id      = sale.sale_id,
                    reason       = random.choice(CANCEL_REASONS),
                    performed_by = vendor_id,
                    created_at   = created,
                ))
                totals["cancelled"] += 1

        await db.commit()

    print(
        "[OK] Dashboard activity: "
        f"{totals['sold']} sold, {totals['in_progress']} in progress, "
        f"{totals['reserved']} reservations, {totals['cancelled']} cancellations"
    )


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

        # ── Verified sales for contract testing ──────────────────────────────────
        await seed_verified_sales(db, vm_id, efectivo_method_id)

        # ── Owner-dashboard data: vendors + per-vendor activity per dealership ────
        ordered_dealership_ids = [vm_id, iz_id, tlp_id]
        vendors_by_dealership  = await seed_vendors(db, ordered_dealership_ids)
        await seed_dashboard_activity(
            db, ordered_dealership_ids, vendors_by_dealership,
            client_ids, catalog, color_name_to_id, efectivo_method_id,
        )

        print()


if __name__ == "__main__":
    asyncio.run(seed_load_test())
