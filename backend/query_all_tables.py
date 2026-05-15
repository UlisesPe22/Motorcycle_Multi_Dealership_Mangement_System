import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models.user                        import User
from models.event                       import EventType, EventSlotDefinition, Event
from models.submission                  import Submission
from models.ai_analysis_log             import AIAnalysisLog
from models.client                      import Client
from models.dealership                  import Dealership
from models.motorcycle_catalog          import MotorcycleCatalog
from models.motorcycle_model_code       import MotorcycleModelCode
from models.purchase_document           import PurchaseDocument
from models.order_confirmation_document import OrderConfirmationDocument
from models.motorcycle                  import Motorcycle


# ======================================================================== #
# Display helpers                                                           #
# ======================================================================== #

def header(title: str):
    width = 60
    print(f"\n{'═' * width}")
    print(f"  {title}")
    print(f"{'═' * width}")


def row_sep():
    print(f"  {'─' * 56}")


def field(label: str, value, width: int = 26):
    label_str = f"{label}:".ljust(width)
    val_str   = str(value) if value is not None else "NULL"
    if len(val_str) > 60:
        val_str = val_str[:57] + "..."
    print(f"  {label_str} {val_str}")


# ======================================================================== #
# Users                                                                     #
# ======================================================================== #

def show_users(db):
    header("USERS")
    rows = db.query(User).order_by(User.user_id).all()
    if not rows:
        print("  (empty)")
        return
    for r in rows:
        field("user_id",    r.user_id)
        field("name",       r.name)
        field("role",       r.role)
        field("created_at", r.created_at)
        row_sep()


# ======================================================================== #
# Dealerships                                                               #
# ======================================================================== #

def show_dealerships(db):
    header("DEALERSHIPS")
    rows = db.query(Dealership).order_by(Dealership.dealership_id).all()
    if not rows:
        print("  (empty)")
        return
    for r in rows:
        field("dealership_id", r.dealership_id)
        field("name",          r.name)
        field("address",       r.address)
        row_sep()


# ======================================================================== #
# Event Types                                                               #
# ======================================================================== #

def show_event_types(db):
    header("EVENT TYPES")
    rows = db.query(EventType).order_by(EventType.event_type_id).all()
    if not rows:
        print("  (empty)")
        return
    for r in rows:
        field("event_type_id",  r.event_type_id)
        field("name",           r.name)
        field("required_slots", r.required_slots)
        field("description",    r.description)
        row_sep()


# ======================================================================== #
# Event Slot Definitions                                                    #
# ======================================================================== #

def show_slot_definitions(db):
    header("EVENT SLOT DEFINITIONS")
    rows = db.query(EventSlotDefinition).order_by(
        EventSlotDefinition.event_type_id,
        EventSlotDefinition.slot_number
    ).all()
    if not rows:
        print("  (empty)")
        return
    for r in rows:
        field("slot_def_id",   r.slot_def_id)
        field("event_type_id", r.event_type_id)
        field("slot_number",   r.slot_number)
        field("slot_name",     r.slot_name)
        field("description",   r.description)
        row_sep()


# ======================================================================== #
# Events                                                                    #
# ======================================================================== #

def show_events(db):
    header("EVENTS")
    rows = db.query(Event).order_by(Event.event_id.desc()).all()
    if not rows:
        print("  (empty)")
        return
    for r in rows:
        field("event_id",           r.event_id)
        field("event_type_id",      r.event_type_id)
        field("initiated_by",       r.initiated_by)
        field("status",             r.status)
        field("started_at",         r.started_at)
        field("completed_at",       r.completed_at)
        field("linked_entity_type", r.linked_entity_type)
        field("linked_entity_id",   r.linked_entity_id)
        row_sep()


# ======================================================================== #
# Submissions                                                               #
# ======================================================================== #

def show_submissions(db):
    header("SUBMISSIONS")
    rows = db.query(Submission).order_by(Submission.submission_id.desc()).all()
    if not rows:
        print("  (empty)")
        return
    for r in rows:
        field("submission_id",    r.submission_id)
        field("event_id",         r.event_id)
        field("slot_name",        r.slot_name)
        field("slot_number",      r.slot_number)
        field("status",           r.status)
        field("detected_side",    r.gemini_detected_side)
        field("raw_file_path",    r.raw_file_path)
        field("normalised_path",  r.normalised_image_path)
        field("rejection_reason", r.rejection_reason)
        field("submitted_at",     r.submitted_at)
        field("created_at",       r.created_at)
        row_sep()


# ======================================================================== #
# AI Analysis Log                                                           #
# ======================================================================== #

def show_ai_logs(db):
    header("AI ANALYSIS LOG")
    rows = db.query(AIAnalysisLog).order_by(AIAnalysisLog.log_id.desc()).all()
    if not rows:
        print("  (empty)")
        return
    for r in rows:
        field("log_id",        r.log_id)
        field("submission_id", r.submission_id)
        field("step_name",     r.step_name)
        field("model_version", r.model_version)
        field("confidence",    f"{r.confidence:.2f}" if r.confidence is not None else "NULL")
        field("success",       r.success)
        field("created_at",    r.created_at)

        if r.parsed_result:
            print(f"\n  parsed_result:")
            formatted = json.dumps(r.parsed_result, indent=4, ensure_ascii=False)
            for line in formatted.split("\n"):
                print(f"    {line}")
        else:
            field("parsed_result", "NULL")
        row_sep()


# ======================================================================== #
# Clients                                                                   #
# ======================================================================== #

def show_clients(db):
    header("CLIENTS")
    rows = db.query(Client).order_by(Client.client_id.desc()).all()
    if not rows:
        print("  (empty)")
        return
    for r in rows:
        field("client_id",           r.client_id)
        field("nombre_completo",     r.nombre_completo)
        field("curp",                r.curp)
        field("clave_de_elector",    r.clave_de_elector)
        field("fecha_nacimiento",    r.fecha_nacimiento)
        field("domicilio",           r.domicilio)
        field("front_submission_id", r.front_submission_id)
        field("back_submission_id",  r.back_submission_id)
        field("event_id",            r.event_id)
        field("registered_by",       r.registered_by)
        field("registered_at",       r.registered_at)
        row_sep()


# ======================================================================== #
# Motorcycle Catalog                                                        #
# ======================================================================== #

def show_motorcycle_catalog(db):
    header("MOTORCYCLE CATALOG")
    rows = db.query(MotorcycleCatalog).order_by(
        MotorcycleCatalog.canonical_name,
        MotorcycleCatalog.year
    ).all()
    if not rows:
        print("  (empty)")
        return
    for r in rows:
        field("model_id",       r.model_id)
        field("canonical_name", r.canonical_name)
        field("year",           r.year)
        field("full_price",     r.full_price)
        row_sep()


# ======================================================================== #
# Motorcycle Model Codes                                                    #
# ======================================================================== #

def show_motorcycle_model_codes(db):
    header("MOTORCYCLE MODEL CODES")
    rows = db.query(MotorcycleModelCode).order_by(
        MotorcycleModelCode.model_id,
        MotorcycleModelCode.code_id
    ).all()
    if not rows:
        print("  (empty)")
        return
    for r in rows:
        field("code_id",     r.code_id)
        field("model_id",    r.model_id)
        field("modelo_code", r.modelo_code)
        row_sep()


# ======================================================================== #
# Purchase Documents                                                        #
# ======================================================================== #

def show_purchase_documents(db):
    header("PURCHASE DOCUMENTS")
    rows = db.query(PurchaseDocument).order_by(
        PurchaseDocument.purchase_document_id.desc()
    ).all()
    if not rows:
        print("  (empty)")
        return
    for r in rows:
        field("purchase_document_id", r.purchase_document_id)
        field("submission_id",        r.submission_id)
        field("dealership_id",        r.dealership_id)
        field("order_date",           r.order_date)
        field("total_units",          r.total_units)
        field("normalised_file_path", r.normalised_file_path)
        field("created_at",           r.created_at)
        row_sep()


# ======================================================================== #
# Order Confirmation Documents                                              #
# ======================================================================== #

def show_order_confirmation_documents(db):
    header("ORDER CONFIRMATION DOCUMENTS")
    rows = db.query(OrderConfirmationDocument).order_by(
        OrderConfirmationDocument.order_confirmation_document_id.desc()
    ).all()
    if not rows:
        print("  (empty)")
        return
    for r in rows:
        field("order_confirmation_document_id", r.order_confirmation_document_id)
        field("submission_id",                  r.submission_id)
        field("dealership_id",                  r.dealership_id)
        field("total_units",                    r.total_units)
        field("created_at",                     r.created_at)
        row_sep()


# ======================================================================== #
# Motorcycles                                                               #
# ======================================================================== #

def show_motorcycles(db):
    header("MOTORCYCLES")
    rows = db.query(Motorcycle).order_by(Motorcycle.motorcycle_id.desc()).all()
    if not rows:
        print("  (empty)")
        return
    for r in rows:
        field("motorcycle_id",             r.motorcycle_id)
        field("model_id",                  r.model_id)
        field("purchase_document_id",      r.purchase_document_id)
        field("order_confirmation_id",     r.order_confirmation_id)
        field("delivery_confirmation_id",  r.delivery_confirmation_id)
        field("dealership_id",             r.dealership_id)
        field("reference_number",          r.reference_number)
        field("motor_number",              r.motor_number)
        field("color",                     r.color)
        field("status",                    r.status)
        field("created_at",               r.created_at)
        row_sep()


# ======================================================================== #
# Menu                                                                      #
# ======================================================================== #

def run():
    db = SessionLocal()
    try:
        print("\n  What do you want to inspect?")
        print("  1  — Users")
        print("  2  — Dealerships")
        print("  3  — Event Types")
        print("  4  — Event Slot Definitions")
        print("  5  — Events")
        print("  6  — Submissions")
        print("  7  — AI Analysis Logs")
        print("  8  — Clients")
        print("  9  — Motorcycle Catalog")
        print("  10 — Motorcycle Model Codes")
        print("  11 — Purchase Documents")
        print("  12 — Order Confirmation Documents")
        print("  13 — Motorcycles")
        print("  0  — ALL TABLES")
        print()

        choice = input("  Enter number: ").strip()

        if choice == "1":
            show_users(db)
        elif choice == "2":
            show_dealerships(db)
        elif choice == "3":
            show_event_types(db)
        elif choice == "4":
            show_slot_definitions(db)
        elif choice == "5":
            show_events(db)
        elif choice == "6":
            show_submissions(db)
        elif choice == "7":
            show_ai_logs(db)
        elif choice == "8":
            show_clients(db)
        elif choice == "9":
            show_motorcycle_catalog(db)
        elif choice == "10":
            show_motorcycle_model_codes(db)
        elif choice == "11":
            show_purchase_documents(db)
        elif choice == "12":
            show_order_confirmation_documents(db)
        elif choice == "13":
            show_motorcycles(db)
        elif choice == "0":
            show_users(db)
            show_dealerships(db)
            show_event_types(db)
            show_slot_definitions(db)
            show_events(db)
            show_submissions(db)
            show_ai_logs(db)
            show_clients(db)
            show_motorcycle_catalog(db)
            show_motorcycle_model_codes(db)
            show_purchase_documents(db)
            show_order_confirmation_documents(db)
            show_motorcycles(db)
        else:
            print("  Invalid choice.")

        print()

    finally:
        db.close()


if __name__ == "__main__":
    run()