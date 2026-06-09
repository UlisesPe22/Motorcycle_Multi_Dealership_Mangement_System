import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config import MAIL_HOST, MAIL_PORT, MAIL_FROM, MAIL_FROM_NAME


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
