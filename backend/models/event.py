"""
event.py — SQLAlchemy models for the event system.

This file defines three tightly coupled tables:

  1. EventType           — catalogue of business process types
                           (client_registration, sale_validation, etc.)
                           Seeded once, never changed at runtime.

  2. EventSlotDefinition — defines which document slots belong to each
                           event type and in what order.
                           e.g. client_registration requires:
                             slot 1 → id_front
                             slot 2 → id_back

  3. Event               — a single live instance of a business process.
                           Created when a user starts an action (e.g. clicks
                           "Register Client"). Groups all its submissions.

Relationships:
  EventType         ──< EventSlotDefinition  (one type, many slot definitions)
  EventType         ──< Event                (one type, many live events)
  Event             ──< Submission           (one event, many submissions)
                        (Submission is defined in submission.py)

State machine for EventStatus:
  in_progress → complete
  in_progress → rejected
  in_progress → abandoned

An event reaches 'complete' only when ALL child submissions reach 'complete'
AND all cross-validation checks pass (same INE version on front and back,
MRZ fields match front fields). The pipeline service is responsible for
advancing this status — the model itself does not enforce it.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, DateTime,
    ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship

from database import Base


# ======================================================================== #
# Enums                                                                     #
# ======================================================================== #

class EventStatus(str, enum.Enum):
    """
    Lifecycle states for a live Event instance.
    (str, enum.Enum) allows FastAPI to serialise these directly to JSON
    without extra conversion — every value IS a plain string.
    """
    in_progress = "in_progress"
    complete    = "complete"
    rejected    = "rejected"
    abandoned   = "abandoned"


class EventName(str, enum.Enum):
    """
    The set of business processes the system supports.
    Mirrors the seeded rows in event_types.name.
    Used in application code so we never compare against bare strings.
    """
    client_registration   = "client_registration"
    sale_validation       = "sale_validation"
    delivery_confirmation = "delivery_confirmation"
    order_confirmation    = "order_confirmation"
    purchase_order        = "purchase_order"


class SlotName(str, enum.Enum):
    """
    All possible document slot names across all event types.
    Defined here because slots are part of the event system definition.
    Also imported by submission.py which uses it as a column type.

    Slot names are intentionally descriptive of the document expected,
    not of their position (slot_1, slot_2), so the pipeline can use
    slot_name to know what kind of document to expect without a join.
    """
    id_front       = "id_front"
    id_back        = "id_back"
    contract       = "contract"
    delivery_table = "delivery_table"
    order_table    = "order_table"
    purchase_order_table = "purchase_order_table"


# ======================================================================== #
# EventType                                                                 #
# ======================================================================== #

class EventType(Base):
    """
    Catalogue table. One row per supported business process type.
    Seeded at startup and never modified at runtime.

    required_slots tells the event creation service how many Submission
    rows to generate when a new Event of this type is created.
    It must match the number of EventSlotDefinition rows for this type.
    """
    __tablename__ = "event_types"

    event_type_id = Column(Integer, primary_key=True, autoincrement=True)

    name = Column(
        SAEnum(EventName, name="event_name_enum"),
        nullable=False,
        unique=True
    )
    required_slots = Column(Integer, nullable=False)
    description    = Column(String, nullable=True)

    # ------------------------------------------------------------------ #
    # Relationships                                                        #
    # ------------------------------------------------------------------ #
    slot_definitions = relationship(
        "EventSlotDefinition",
        back_populates="event_type",
        cascade="all, delete-orphan",
        order_by="EventSlotDefinition.slot_number"
        # Ordered so iterating slot_definitions always gives slot 1, 2, 3...
    )

    events = relationship(
        "Event",
        back_populates="event_type"
    )

    def __repr__(self) -> str:
        return f"<EventType id={self.event_type_id} name={self.name}>"


# ======================================================================== #
# EventSlotDefinition                                                       #
# ======================================================================== #

class EventSlotDefinition(Base):
    """
    Defines the document slots that make up one event type.
    Think of this as the template/schema for what documents are required.

    Example rows for client_registration (event_type_id=1):
      slot_number=1  slot_name=id_front  description="Front of INE"
      slot_number=2  slot_name=id_back   description="Back of INE"

    When a new Event is created, the pipeline service reads these rows
    and creates one Submission row per slot definition. The slot_name
    on the Submission tells the Gemini prompt what document to expect
    ("I am expecting id_front — confirm this is the front of a Mexican INE").
    """
    __tablename__ = "event_slot_definitions"

    slot_def_id   = Column(Integer, primary_key=True, autoincrement=True)

    event_type_id = Column(
        Integer,
        ForeignKey("event_types.event_type_id"),
        nullable=False
    )
    slot_number = Column(Integer, nullable=False)   # 1-based ordering
    slot_name   = Column(
        SAEnum(SlotName, name="slot_name_enum"),
        nullable=False
    )
    description = Column(String, nullable=True)

    # ------------------------------------------------------------------ #
    # Relationships                                                        #
    # ------------------------------------------------------------------ #
    event_type = relationship("EventType", back_populates="slot_definitions")

    def __repr__(self) -> str:
        return (
            f"<EventSlotDefinition "
            f"event_type={self.event_type_id} "
            f"slot={self.slot_number} "
            f"name={self.slot_name}>"
        )


# ======================================================================== #
# Event                                                                     #
# ======================================================================== #

class Event(Base):
    """
    A single live instance of a business process.

    Created the moment a user starts an action (e.g. clicks "Register Client").
    Groups all related Submission rows under one parent record.

    The pipeline enforces this rule before advancing to Phase 2:
      ALL submissions WHERE event_id = this event_id
      must have status = 'matched'
      AND gemini_detected_version must be identical across all submissions
      (front and back must be the same INE version).

    linked_entity_type / linked_entity_id form a polymorphic FK pattern.
    After a client_registration completes and a Client record is created,
    linked_entity_type = 'CLIENT' and linked_entity_id = that client's PK.
    This avoids adding a column per entity type to this table.
    """
    __tablename__ = "events"

    # ------------------------------------------------------------------ #
    # Primary key                                                          #
    # ------------------------------------------------------------------ #
    event_id = Column(Integer, primary_key=True, autoincrement=True)

    # ------------------------------------------------------------------ #
    # Foreign keys                                                         #
    # ------------------------------------------------------------------ #
    event_type_id = Column(
        Integer,
        ForeignKey("event_types.event_type_id"),
        nullable=False
    )
    initiated_by = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=False
    )

    # ------------------------------------------------------------------ #
    # Status                                                               #
    # ------------------------------------------------------------------ #
    status = Column(
        SAEnum(EventStatus, name="event_status_enum"),
        nullable=False,
        default=EventStatus.in_progress
    )

    # ------------------------------------------------------------------ #
    # Timestamps                                                           #
    # ------------------------------------------------------------------ #
    started_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True   # NULL until the event reaches a terminal state
    )

    # ------------------------------------------------------------------ #
    # Polymorphic link to the business entity this event produced.        #
    # NULL on creation — the entity does not exist yet.                   #
    # ------------------------------------------------------------------ #
    linked_entity_type = Column(String, nullable=True)
    linked_entity_id   = Column(Integer, nullable=True)

    # ------------------------------------------------------------------ #
    # Relationships                                                        #
    # ------------------------------------------------------------------ #
    event_type = relationship("EventType", back_populates="events")

    submissions = relationship(
        "Submission",
        back_populates="event",
        cascade="all, delete-orphan"
        # Deleting an event removes all its submissions and,
        # via submission's own cascade, all their AI analysis logs.
    )

    def __repr__(self) -> str:
        return (
            f"<Event id={self.event_id} "
            f"type={self.event_type_id} "
            f"status={self.status}>"
        )