"""
event.py — SQLAlchemy models for the event system.

This file defines one table:

  Event — a single live instance of a business process.
          Created when a user starts an action (e.g. clicks
          "Register Client"). Groups all its submissions.

  event_type stores the EventName value as a plain VARCHAR string —
  no separate event_types catalogue table, no FK.

Slot definitions (which documents belong to each event type) live in
config.EVENT_SLOT_DEFINITIONS — a hardcoded dict, not a DB table.

State machine for EventStatus:
  in_progress → complete
  in_progress → rejected
  in_progress → abandoned

An event reaches 'complete' only when ALL child submissions reach 'complete'
AND all cross-validation checks pass. The pipeline service is responsible for
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
    Stored as a plain string in Event.event_type — not as a DB enum type.
    Used in application code so we never compare against bare strings.
    """
    client_registration      = "client_registration"
    sale_validation          = "sale_validation"
    delivery_confirmation    = "delivery_confirmation"
    order_confirmation       = "order_confirmation"
    purchase_order           = "purchase_order"
    motorcycle_reservation   = "motorcycle_reservation"
    registrar_vendedor       = "registrar_vendedor"


class SlotName(str, enum.Enum):
    """
    All possible document slot names across all event types.
    Defined here because slots are part of the event system definition.
    Also imported by submission.py which uses it as a column type.

    Slot names are intentionally descriptive of the document expected,
    not of their position (slot_1, slot_2), so the pipeline can use
    slot_name to know what kind of document to expect without a join.
    """
    id_front             = "id_front"
    id_back              = "id_back"
    contract             = "contract"
    delivery_table       = "delivery_table"
    order_table          = "order_table"
    purchase_order_table = "purchase_order_table"


# ======================================================================== #
# Event                                                                     #
# ======================================================================== #

class Event(Base):
    """
    A single live instance of a business process.

    Created the moment a user starts an action (e.g. clicks "Register Client").
    Groups all related Submission rows under one parent record.

    event_type stores the EventName value as a plain string
    (e.g. "client_registration", "purchase_order"). There is no
    separate event_types catalogue table.

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
    # Event type — stored as plain string (EventName value)               #
    # ------------------------------------------------------------------ #
    event_type = Column(String, nullable=False)

    # ------------------------------------------------------------------ #
    # Foreign keys                                                         #
    # ------------------------------------------------------------------ #
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
            f"type={self.event_type} "
            f"status={self.status}>"
        )
