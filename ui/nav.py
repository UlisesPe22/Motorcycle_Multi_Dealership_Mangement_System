import streamlit as st
from ui.config import go_to

NAV_ITEMS = [
    ("main",                  "Panel Principal"),
    ("register",              "Registrar Cliente"),
    ("clients",               "Buscar Cliente"),
    ("order_registration",    "Orden de Compra"),
    ("order_confirmation",    "Orden de Traslado"),
    ("delivery_confirmation", "Registrar Entrega"),
    ("sale_validation",       "Validar Venta",      True),
    ("employee_registration", "Registrar Empleado", True),
]

_NAV_MAIN = [
    ("main",                  "⊞",  "Panel Principal"),
    ("register",              "+",  "Registrar Cliente"),
    ("clients",               "○",  "Buscar Cliente"),
    ("order_registration",    "≡",  "Orden de Compra"),
    ("order_confirmation",    "▷",  "Orden de Traslado"),
    ("delivery_confirmation", "✔",  "Registrar Entrega"),
]

_NAV_SOON = [
    ("sale_validation",       "◇",  "Validar Venta"),
    ("employee_registration", "◈",  "Registrar Empleado"),
]


def _clear_all_pipeline_state():
    keys_to_clear = [
        "pipeline_ran", "pipeline_success", "pipeline_message",
        "event_data", "upload_front", "upload_back",
        "purchase_ran", "purchase_success", "purchase_message",
        "order_conf_ran", "order_conf_success", "order_conf_message", "order_conf_confidence",
        "delivery_ran", "delivery_success", "delivery_message", "delivery_confidence",
    ]
    for k in keys_to_clear:
        st.session_state.pop(k, None)


def topbar():
    current = st.session_state.page

    with st.sidebar:
        st.markdown("""
        <div class="sidebar-brand">
            <div class="sidebar-brand-name">Moto Dealer</div>
            <div class="sidebar-brand-sub">Bajaj · Sistema de Gestión</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="sidebar-section">Operaciones</div>', unsafe_allow_html=True)

        for key, icon, label in _NAV_MAIN:
            if current == key:
                st.markdown(
                    f'<div class="sidebar-nav-active">{icon}&nbsp;&nbsp;{label}</div>',
                    unsafe_allow_html=True,
                )
            else:
                if st.button(f"{icon}  {label}", key=f"nav_{key}"):
                    _clear_all_pipeline_state()
                    go_to(key)

        st.markdown('<div class="sidebar-section">Próximamente</div>', unsafe_allow_html=True)

        for _, icon, label in _NAV_SOON:
            st.markdown(
                f'<div class="sidebar-nav-soon">{icon}&nbsp;&nbsp;{label}'
                f'<span class="soon-badge">Próx.</span></div>',
                unsafe_allow_html=True,
            )
