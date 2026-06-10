"""
email_service.py — transactional emails.

  - send_credentials_email          : new-user login credentials (pre-existing)
  - send_client_activation_email    : client clicks to activate their account
  - send_payment_confirmation_email : client clicks to confirm a declared payment

Uses aiosmtplib (already a project dependency, same pattern as
send_credentials_email) so sends are async and never block the event loop.
SMTP host/port/from come from config (Mailhog in dev).

build_moto_display() is shared with routers/payment_confirmation.py so the
confirmation email and the confirmation page describe the motorcycle identically.
"""

import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from config import MAIL_HOST, MAIL_PORT, MAIL_FROM, MAIL_FROM_NAME, PUBLIC_BASE_URL
from models.motorcycle import Motorcycle
from models.payment_event import PaymentEvent
from models.payment_item import PaymentItem
from models.reservation import Reservation, ReservationStatus
from models.reservation_color import ReservationColor
from models.sale import Sale
from models.user import User

BAJAJ_RED  = "#E31937"
FONT_STACK = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, "
    "sans-serif"
)

_EVENT_TYPE_LABEL = {
    "reservation": "Reservación",
    "al_contado":  "Al contado",
    "enganche":    "Enganche",
    "financing":   "Financiamiento",
}


async def send_credentials_email(
    to_email: str,
    name: str,
    username: str,
    password: str,
) -> None:
    """Sends login credentials to a newly registered user via Mailhog."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Bienvenido al Sistema Bajaj — Tus credenciales de acceso"
    msg["From"]    = f"{MAIL_FROM_NAME} <{MAIL_FROM}>"
    msg["To"]      = to_email

    body = f"""
Hola {name},

Tu cuenta ha sido creada en el Sistema de Gestión Bajaj.

Tus credenciales de acceso son:

  Usuario:    {username}
  Contraseña: {password}

Por favor guarda esta información en un lugar seguro.

Saludos,
Sistema Bajaj
"""
    msg.attach(MIMEText(body, "plain"))

    await aiosmtplib.send(
        msg,
        hostname=MAIL_HOST,
        port=MAIL_PORT,
        start_tls=False,
    )


# ====================================================================== #
# Low-level HTML send                                                     #
# ====================================================================== #

async def _send_html(to_address: str, subject: str, html_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{MAIL_FROM_NAME} <{MAIL_FROM}>"
    msg["To"]      = to_address
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    await aiosmtplib.send(
        msg,
        hostname=MAIL_HOST,
        port=MAIL_PORT,
        start_tls=False,
    )


def _fmt(amount: float) -> str:
    try:
        return f"${amount:,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def _cta_button(label: str, href: str) -> str:
    return (
        f'<a href="{href}" style="display:inline-block;background:{BAJAJ_RED};'
        f'color:#ffffff;text-decoration:none;font-weight:700;font-size:16px;'
        f'padding:14px 32px;border-radius:8px;letter-spacing:0.02em;">{label}</a>'
    )


def _shell(header_text: str, inner_html: str, footer_text: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:{FONT_STACK};">
  <div style="padding:24px;">
    <div style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 8px 24px rgba(0,0,0,0.10);">
      <div style="background:{BAJAJ_RED};padding:20px 28px;">
        <span style="color:#ffffff;font-size:20px;font-weight:800;letter-spacing:0.02em;">{header_text}</span>
      </div>
      <div style="padding:28px;">
        {inner_html}
      </div>
      <div style="padding:18px 28px;background:#f8fafc;border-top:1px solid #e2e8f0;">
        <span style="font-size:12px;color:#94a3b8;">{footer_text}</span>
      </div>
    </div>
  </div>
</body>
</html>"""


# ====================================================================== #
# Motorcycle display (shared with the confirmation router)               #
# ====================================================================== #

async def build_moto_display(db: AsyncSession, sale: Sale) -> str:
    """
    Human-readable description of the motorcycle attached to a sale.

    - If the sale has a motorcycle_id: "{model} {year} — VIN: {reference}".
    - If not (reservation-only sale): pull the model + preferred colors from the
      client's active reservation: "{model} {year} — color preferido: {a/b/c}".
    """
    if sale.motorcycle_id:
        result = await db.execute(
            select(Motorcycle)
            .options(joinedload(Motorcycle.model))
            .where(Motorcycle.motorcycle_id == sale.motorcycle_id)
        )
        moto = result.unique().scalar_one_or_none()
        if moto and moto.model:
            ref = moto.reference_number or moto.motor_number or "por asignar"
            return f"{moto.model.canonical_name} {moto.model.year} — VIN: {ref}"
        return "Motocicleta por asignar"

    result = await db.execute(
        select(Reservation)
        .options(
            joinedload(Reservation.model),
            selectinload(Reservation.colors).joinedload(ReservationColor.color),
        )
        .where(
            Reservation.client_id == sale.client_id,
            Reservation.status.in_([ReservationStatus.active, ReservationStatus.assigned]),
        )
        .order_by(Reservation.created_at.desc())
        .limit(1)
    )
    reservation = result.unique().scalar_one_or_none()
    if reservation and reservation.model:
        colors = [rc.color.name for rc in reservation.colors if rc.color]
        color_str = "/".join(colors) if colors else "por asignar"
        return (
            f"{reservation.model.canonical_name} {reservation.model.year} "
            f"— color preferido: {color_str}"
        )
    return "Modelo por asignar"


# ====================================================================== #
# Email 1: client activation                                              #
# ====================================================================== #

async def send_client_activation_email(pending_client, token: str) -> None:
    href = f"{PUBLIC_BASE_URL}/clients/activate?token={token}"
    inner = f"""
        <h2 style="margin:0 0 16px;font-size:20px;color:#0f172a;">
          Bienvenido/a, {pending_client.nombre_completo}
        </h2>
        <p style="margin:0 0 24px;color:#475569;font-size:15px;line-height:1.6;">
          Tu información ha sido registrada en nuestro sistema. Por favor confirma
          tu cuenta haciendo clic en el siguiente botón.
        </p>
        <div style="text-align:center;margin:0 0 8px;">
          {_cta_button("ACTIVAR MI CUENTA", href)}
        </div>
    """
    html = _shell(
        "Bajaj Motos",
        inner,
        "Este enlace expira en 1 hora. Si no solicitaste este registro, ignora este mensaje.",
    )
    await _send_html(pending_client.email, "Activa tu cuenta — Bajaj Motos", html)


# ====================================================================== #
# Email 2: payment confirmation                                           #
# ====================================================================== #

async def send_payment_confirmation_email(
    payment_event_id: int,
    db: AsyncSession,
    token: str,
) -> None:
    result = await db.execute(
        select(PaymentEvent)
        .options(
            selectinload(PaymentEvent.items).joinedload(PaymentItem.method),
            joinedload(PaymentEvent.sale).joinedload(Sale.client),
            joinedload(PaymentEvent.sale).joinedload(Sale.dealership),
        )
        .where(PaymentEvent.payment_event_id == payment_event_id)
    )
    event = result.unique().scalar_one_or_none()
    if event is None or event.sale is None:
        print(f"[email] payment_event {payment_event_id} or its sale not found; skipping email")
        return

    sale       = event.sale
    client     = sale.client
    dealership = sale.dealership
    if client is None or not client.email:
        print(f"[email] sale {sale.sale_id} has no client/email; skipping payment email")
        return

    vendor_result = await db.execute(
        select(User).where(User.user_id == sale.vendor_id)
    )
    vendor = vendor_result.scalar_one_or_none()
    vendor_name     = (vendor.name if vendor else None) or "—"
    dealership_name = dealership.name if dealership else "—"

    moto_display = await build_moto_display(db, sale)
    event_label  = _EVENT_TYPE_LABEL.get(event.event_type, event.event_type)

    # Build the payment table.
    rows_html = ""
    non_financing_total = 0.0
    for item in event.items:
        method_name = item.method.name if item.method else "—"
        if method_name == "Financiera":
            rows_html += (
                "<tr>"
                "<td style='padding:8px 0;border-bottom:1px solid #f1f5f9;'>Financiamiento</td>"
                "<td style='padding:8px 0;border-bottom:1px solid #f1f5f9;'>Financiera</td>"
                "<td style='padding:8px 0;border-bottom:1px solid #f1f5f9;text-align:right;color:#64748b;'>"
                f"{_fmt(item.amount)} <span style='font-size:12px;'>(financiado — no pagado hoy)</span></td>"
                "</tr>"
            )
        else:
            non_financing_total += item.amount
            rows_html += (
                "<tr>"
                f"<td style='padding:8px 0;border-bottom:1px solid #f1f5f9;'>{event_label}</td>"
                f"<td style='padding:8px 0;border-bottom:1px solid #f1f5f9;'>{method_name}</td>"
                f"<td style='padding:8px 0;border-bottom:1px solid #f1f5f9;text-align:right;font-weight:600;'>{_fmt(item.amount)}</td>"
                "</tr>"
            )

    href = f"{PUBLIC_BASE_URL}/payments/confirm?token={token}"
    inner = f"""
        <table style="width:100%;border-collapse:collapse;margin:0 0 20px;font-size:14px;color:#334155;">
          <tr>
            <td style="padding:4px 0;color:#94a3b8;width:38%;">Cliente</td>
            <td style="padding:4px 0;font-weight:600;">{client.nombre_completo}</td>
          </tr>
          <tr>
            <td style="padding:4px 0;color:#94a3b8;">Vendedor</td>
            <td style="padding:4px 0;font-weight:600;">{vendor_name}</td>
          </tr>
          <tr>
            <td style="padding:4px 0;color:#94a3b8;">Sucursal</td>
            <td style="padding:4px 0;font-weight:600;">{dealership_name}</td>
          </tr>
          <tr>
            <td style="padding:4px 0;color:#94a3b8;vertical-align:top;">Motocicleta</td>
            <td style="padding:4px 0;font-weight:600;">{moto_display}</td>
          </tr>
        </table>

        <table style="width:100%;border-collapse:collapse;margin:0 0 24px;font-size:14px;color:#334155;">
          <thead>
            <tr>
              <th style="text-align:left;padding:8px 0;border-bottom:2px solid #e2e8f0;color:#64748b;font-size:12px;text-transform:uppercase;">Concepto</th>
              <th style="text-align:left;padding:8px 0;border-bottom:2px solid #e2e8f0;color:#64748b;font-size:12px;text-transform:uppercase;">Método</th>
              <th style="text-align:right;padding:8px 0;border-bottom:2px solid #e2e8f0;color:#64748b;font-size:12px;text-transform:uppercase;">Monto</th>
            </tr>
          </thead>
          <tbody>
            {rows_html}
            <tr>
              <td colspan="2" style="padding:12px 0 0;font-weight:700;color:#0f172a;">Total a confirmar</td>
              <td style="padding:12px 0 0;text-align:right;font-weight:700;color:#0f172a;font-size:16px;">{_fmt(non_financing_total)}</td>
            </tr>
          </tbody>
        </table>

        <p style="margin:0 0 20px;color:#475569;font-size:15px;line-height:1.6;">
          Por favor confirma que los pagos anteriores son correctos haciendo clic
          en el siguiente botón.
        </p>
        <div style="text-align:center;">
          {_cta_button("CONFIRMAR MIS PAGOS", href)}
        </div>
    """
    html = _shell(
        f"Bajaj Motos — {dealership_name}",
        inner,
        "Este enlace expira en 1 hora.",
    )
    subject = f"Resumen de pago — {dealership_name} — {moto_display}"
    await _send_html(client.email, subject, html)
