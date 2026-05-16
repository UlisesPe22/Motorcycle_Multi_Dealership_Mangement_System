import requests
import streamlit as st

from ui.config import API
from ui.components import page_header
from ui.pages.delivery import _fetch_dealerships

_STATUS_ES = {
    "purchased":         "Comprada",
    "incoming":          "En camino",
    "in_stock":          "En stock",
    "not_purchased":     "No comprada",
    "rejected":          "Rechazada",
    "sold":              "Vendida",
    "cancelled":         "Cancelada",
    "incoming_reserved": "En camino (Reservada)",
    "in_stock_reserved": "En stock (Reservada)",
}

_STATUS_BADGE = {
    "purchased":         ("#DBEAFE", "#1D4ED8"),
    "incoming":          ("#FEF3C7", "#92400E"),
    "in_stock":          ("#DCFCE7", "#15803D"),
    "not_purchased":     ("#F1F5F9", "#64748B"),
    "rejected":          ("#FEE2E2", "#DC2626"),
    "sold":              ("#CCFBF1", "#0D9488"),
    "cancelled":         ("#F1F5F9", "#94A3B8"),
    "incoming_reserved": ("#FEF3C7", "#92400E"),
    "in_stock_reserved": ("#DCFCE7", "#15803D"),
}

_RESERVED_STATUSES = {"incoming_reserved", "in_stock_reserved"}


def _v(val):
    if val in (None, "", "None", "null"):
        return "—"
    return str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _badge(raw: str) -> str:
    bg, fg = _STATUS_BADGE.get(raw, ("#F1F5F9", "#64748B"))
    label  = _STATUS_ES.get(raw, raw or "—")
    if raw in _RESERVED_STATUSES:
        label = f"⭐ {label}"
    return (
        f'<span style="background:{bg};color:{fg};font-size:0.67rem;font-weight:600;'
        f'padding:0.18rem 0.55rem;border-radius:20px;white-space:nowrap;'
        f'letter-spacing:0.02em;">{label}</span>'
    )


def _on_filter_change():
    st.session_state.moto_page     = 0
    st.session_state.moto_searched = True


def page_main():
    page_header("Inicio", "Panel Principal")

    ROWS_PER_PAGE = 13

    if "moto_page" not in st.session_state:
        st.session_state.moto_page = 0
    if "moto_searched" not in st.session_state:
        st.session_state.moto_searched = False
    if "moto_all_data" not in st.session_state:
        st.session_state.moto_all_data = None

    if st.session_state.moto_all_data is None:
        try:
            resp = requests.get(f"{API}/motorcycles/")
            if resp.status_code == 200:
                st.session_state.moto_all_data = resp.json()
            else:
                st.error(f"Error al cargar el inventario ({resp.status_code}).")
                return
        except requests.exceptions.ConnectionError:
            st.error("No se puede conectar al servidor. Asegúrate de que FastAPI esté corriendo.")
            return

    all_data = st.session_state.moto_all_data

    dealerships = _fetch_dealerships()
    suc_options = ["Todas"] + [d["name"] for d in dealerships]
    est_options = [
        "Todos",
        "Comprada",
        "En camino",
        "En stock",
        "No comprada",
        "Rechazada",
        "Vendida",
        "Cancelada",
        "En camino (Reservada)",
        "En stock (Reservada)",
    ]
    ALL_MODELS  = [
        "Dominar 250", "Dominar 400 UG", "Pulsar N125 Car",
        "Pulsar N125 FI CBS", "Pulsar N160", "Pulsar N160 Premium",
        "Pulsar N250 FI ABS", "Pulsar NS200", "Pulsar NS400Z", "Pulsar RS200",
    ]
    mod_options = ["Todos"] + ALL_MODELS

    st.markdown('<div class="bi-card" style="padding:1rem 1.75rem 1.1rem;">', unsafe_allow_html=True)
    f1, f2, f3, f4 = st.columns([2, 2, 2, 1])
    with f1:
        st.markdown('<div class="card-section">Estado</div>', unsafe_allow_html=True)
        sel_estado = st.selectbox(
            "Estado",
            options=est_options,
            key="moto_filter_estado",
            label_visibility="collapsed",
            on_change=_on_filter_change,
        )
    with f2:
        st.markdown('<div class="card-section">Modelo</div>', unsafe_allow_html=True)
        sel_modelo = st.selectbox(
            "Modelo",
            options=mod_options,
            key="moto_filter_modelo",
            label_visibility="collapsed",
            on_change=_on_filter_change,
        )
    with f3:
        st.markdown('<div class="card-section">Sucursal</div>', unsafe_allow_html=True)
        sel_sucursal = st.selectbox(
            "Sucursal",
            options=suc_options,
            key="moto_filter_sucursal",
            label_visibility="collapsed",
            on_change=_on_filter_change,
        )
    with f4:
        st.markdown('<div style="margin-top:1.45rem;"></div>', unsafe_allow_html=True)
        if st.button("Buscar", key="btn_buscar_moto", type="primary"):
            st.session_state.moto_page     = 0
            st.session_state.moto_searched = True
    st.markdown("</div>", unsafe_allow_html=True)

    if not st.session_state.moto_searched:
        return

    _ES_TO_RAW = {v: k for k, v in _STATUS_ES.items()}
    filtered = list(all_data)

    if sel_estado != "Todos":
        raw_key = _ES_TO_RAW.get(sel_estado)
        if raw_key:
            filtered = [m for m in filtered if m.get("status") == raw_key]

    if sel_modelo != "Todos":
        filtered = [m for m in filtered if m.get("model") == sel_modelo]

    if sel_sucursal != "Todas":
        filtered = [m for m in filtered if m.get("dealership") == sel_sucursal]

    total = len(filtered)

    total_pages = max(1, (total + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE)
    page        = max(0, min(st.session_state.moto_page, total_pages - 1))
    st.session_state.moto_page = page
    start       = page * ROWS_PER_PAGE
    end         = min(start + ROWS_PER_PAGE, total)
    page_rows   = filtered[start:end]

    if total == 0:
        st.markdown(
            '<div class="count-tag" style="background:#FEF2F2;color:#DC2626;">'
            'Sin resultados para los filtros seleccionados</div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f'<div class="count-tag">Mostrando {start + 1}–{end} de {total} motocicleta(s)</div>',
        unsafe_allow_html=True,
    )

    TH = (
        "padding:0.6rem 0.9rem;text-align:left;font-size:0.62rem;font-weight:700;"
        "text-transform:uppercase;letter-spacing:0.1em;color:#475569;"
        "border-bottom:2px solid #E2E8F0;white-space:nowrap;background:#F8FAFC;"
    )

    rows_html = ""
    for i, m in enumerate(page_rows):
        bg_row   = "#ffffff" if i % 2 == 0 else "#FAFBFC"
        td_base  = (
            f"padding:0.52rem 0.9rem;border-bottom:1px solid #F1F5F9;"
            f"font-size:0.82rem;color:#1A2332;vertical-align:middle;background:{bg_row};"
        )
        td_mono  = (
            f"padding:0.52rem 0.9rem;border-bottom:1px solid #F1F5F9;"
            f"font-size:0.75rem;color:#1A2332;vertical-align:middle;background:{bg_row};"
            f"font-family:'JetBrains Mono',monospace;"
        )
        td_badge = (
            f"padding:0.38rem 0.9rem;border-bottom:1px solid #F1F5F9;"
            f"vertical-align:middle;background:{bg_row};"
        )
        raw_st = m.get("status") or ""
        rows_html += (
            f'<tr>'
            f'<td style="{td_base}">{_v(m.get("model"))}</td>'
            f'<td style="{td_base}">{_v(m.get("year"))}</td>'
            f'<td style="{td_base}">{_v(m.get("color"))}</td>'
            f'<td style="{td_badge}">{_badge(raw_st)}</td>'
            f'<td style="{td_base}">{_v(m.get("dealership"))}</td>'
            f'<td style="{td_mono}">{_v(m.get("serie"))}</td>'
            f'<td style="{td_mono}">{_v(m.get("motor"))}</td>'
            f'</tr>'
        )

    header_html = "".join(
        f'<th style="{TH}">{h}</th>'
        for h in ["Modelo", "Año", "Color", "Estado", "Sucursal", "No. Serie", "No. Motor"]
    )

    table_html = (
        '<div style="background:#ffffff;border:1px solid #E8ECF0;border-radius:7px;'
        'overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.05);margin-bottom:0.75rem;">'
        '<div style="overflow-x:auto;">'
        '<table style="width:100%;border-collapse:collapse;font-family:\'Inter\',sans-serif;">'
        f'<thead><tr>{header_html}</tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        '</table></div></div>'
    )
    st.markdown(table_html, unsafe_allow_html=True)

    if total_pages > 1:
        p1, p2, p3 = st.columns([1, 3, 1])
        with p1:
            if st.button("← Anterior", key="moto_prev", disabled=(page == 0)):
                st.session_state.moto_page = page - 1
        with p2:
            st.markdown(
                f'<div style="text-align:center;font-size:0.78rem;color:#64748B;'
                f'padding-top:0.55rem;">Página {page + 1} de {total_pages}</div>',
                unsafe_allow_html=True,
            )
        with p3:
            if st.button("Siguiente →", key="moto_next", disabled=(page >= total_pages - 1)):
                st.session_state.moto_page = page + 1
