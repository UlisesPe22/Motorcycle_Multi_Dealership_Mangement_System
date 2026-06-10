"""
confirmation_pages.py — server-rendered HTML pages for the confirmation links.

These are returned with FastAPI HTMLResponse. They are standalone, inline-CSS,
mobile-friendly cards in the Bajaj brand style. No JS, no external assets.
"""

BAJAJ_RED   = "#E31937"
GREEN       = "#22c55e"
ORANGE      = "#f97316"
FONT_STACK  = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, "
    "sans-serif"
)


def _fmt_mxn(amount: float) -> str:
    try:
        return f"${amount:,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def _page(icon: str, icon_color: str, title: str, body_html: str) -> str:
    """Shared shell for every confirmation page."""
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:{FONT_STACK};">
  <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;box-sizing:border-box;">
    <div style="background:#ffffff;max-width:480px;width:100%;border-radius:16px;box-shadow:0 10px 30px rgba(0,0,0,0.12);overflow:hidden;">
      <div style="height:6px;background:{BAJAJ_RED};"></div>
      <div style="padding:40px 32px;text-align:center;">
        <div style="width:72px;height:72px;border-radius:50%;background:{icon_color};margin:0 auto 24px;display:flex;align-items:center;justify-content:center;font-size:38px;color:#ffffff;line-height:1;">
          {icon}
        </div>
        <h1 style="margin:0 0 12px;font-size:24px;color:#0f172a;font-weight:700;">{title}</h1>
        {body_html}
      </div>
      <div style="padding:16px 32px;background:#f8fafc;border-top:1px solid #e2e8f0;text-align:center;">
        <span style="font-size:12px;color:#94a3b8;">Bajaj Motos</span>
      </div>
    </div>
  </div>
</body>
</html>"""


def render_payment_confirmed_page(
    client_name: str,
    moto_display: str,
    total_confirmed: float,
    dealership_name: str,
) -> str:
    body = f"""
        <p style="margin:0 0 8px;color:#475569;font-size:15px;">
          {client_name}
        </p>
        <p style="margin:0 0 20px;color:#64748b;font-size:14px;">
          {moto_display}
        </p>
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:12px;padding:18px;margin:0 0 20px;">
          <div style="font-size:13px;color:#15803d;margin-bottom:4px;">Total confirmado</div>
          <div style="font-size:28px;font-weight:700;color:#166534;">{_fmt_mxn(total_confirmed)} MXN</div>
        </div>
        <p style="margin:0;color:#64748b;font-size:14px;">
          Gracias por su confianza en Bajaj {dealership_name}.
        </p>
    """
    return _page("✓", GREEN, "¡Pago confirmado!", body)


def render_client_activated_page(client_name: str) -> str:
    body = f"""
        <p style="margin:0 0 12px;color:#475569;font-size:15px;">
          Bienvenido/a <strong>{client_name}</strong> al sistema Bajaj Motos.
        </p>
        <p style="margin:0;color:#64748b;font-size:14px;">
          Ya puedes realizar compras y reservaciones.
        </p>
    """
    return _page("✓", GREEN, "¡Cuenta activada!", body)


def render_token_expired_page() -> str:
    body = """
        <p style="margin:0 0 12px;color:#475569;font-size:15px;">
          Este enlace de confirmación ha expirado.
        </p>
        <p style="margin:0;color:#64748b;font-size:14px;">
          Por favor contacta a tu sucursal para reenviar el correo.
        </p>
    """
    return _page("⚠", ORANGE, "Enlace expirado", body)
