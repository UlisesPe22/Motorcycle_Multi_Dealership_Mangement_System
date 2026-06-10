"""
token_service.py — confirmation token helpers for the email verification flow.

Two token families:
  - client activation tokens  -> stored on unconfirmed_clients rows
  - payment confirmation tokens -> stored in payment_confirmation_tokens

Tokens are opaque URL-safe random strings. Expiry is TOKEN_EXPIRY_MINUTES
from creation (pulled from config).
"""

import secrets
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import TOKEN_EXPIRY_MINUTES
from models.unconfirmed_client import UnconfirmedClient
from models.payment_confirmation_token import PaymentConfirmationToken


def new_token() -> str:
    """Return a fresh opaque URL-safe token string."""
    return secrets.token_urlsafe(32)


def expiry_from_now() -> datetime:
    """Return the absolute expiry timestamp for a freshly minted token."""
    return datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRY_MINUTES)


async def generate_client_token(db: AsyncSession, pending_client_id: int) -> str:
    """
    Generate (or refresh) the confirmation token for an unconfirmed client.
    Stores the token + expiry on the UnconfirmedClient row and returns the
    raw token string. The caller is responsible for committing.
    """
    result = await db.execute(
        select(UnconfirmedClient).where(
            UnconfirmedClient.pending_client_id == pending_client_id
        )
    )
    pending = result.scalar_one_or_none()
    if pending is None:
        raise ValueError(f"UnconfirmedClient {pending_client_id} not found")

    token = new_token()
    pending.confirmation_token = token
    pending.token_expires_at   = expiry_from_now()
    pending.status             = "pending"
    await db.flush()
    return token


async def generate_payment_token(db: AsyncSession, payment_event_id: int) -> str:
    """
    Create or refresh the PaymentConfirmationToken for a PaymentEvent and
    return the raw token string.

    payment_event_id is UNIQUE in the schema, so there is at most one row per
    event. On a resend we refresh that single row in place: the previous token
    string is overwritten and therefore invalidated, and status is reset to
    'pending'. The caller is responsible for committing.
    """
    result = await db.execute(
        select(PaymentConfirmationToken).where(
            PaymentConfirmationToken.payment_event_id == payment_event_id
        )
    )
    token_row = result.scalar_one_or_none()

    token = new_token()
    if token_row is None:
        token_row = PaymentConfirmationToken(
            payment_event_id    = payment_event_id,
            token               = token,
            expires_at          = expiry_from_now(),
            status              = "pending",
            verification_source = "email",
        )
        db.add(token_row)
    else:
        token_row.token        = token
        token_row.expires_at   = expiry_from_now()
        token_row.status       = "pending"
        token_row.confirmed_at = None
    await db.flush()
    return token


async def get_unconfirmed_client_by_token(
    db: AsyncSession, token: str
) -> UnconfirmedClient | None:
    """Return the UnconfirmedClient row matching this token, or None."""
    result = await db.execute(
        select(UnconfirmedClient).where(
            UnconfirmedClient.confirmation_token == token
        )
    )
    return result.scalar_one_or_none()


async def get_payment_token_by_token(
    db: AsyncSession, token: str
) -> PaymentConfirmationToken | None:
    """Return the PaymentConfirmationToken row matching this token, or None."""
    result = await db.execute(
        select(PaymentConfirmationToken).where(
            PaymentConfirmationToken.token == token
        )
    )
    return result.scalar_one_or_none()
