import requests
import streamlit as st

from ui.config import API, go_to
from ui.components import page_header


def _clear_reservation_state():
    for key in [
        "reservation_ran", "reservation_success", "reservation_message",
        "reservation_dealership", "reservation_client",
        "reservation_model", "reservation_colors", "reservation_amount",
    ]:
        st.session_state.pop(key, None)


def _show_reservation_result():
    success  = st.session_state.get("reservation_success", False)
    message  = st.session_state.get("reservation_message", "")
    assigned = st.session_state.get("reservation_assigned", False)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if success:
            extra = ""
            if assigned:
                extra = "<br><small>⭐ Motocicleta en stock asignada automáticamente.</small>"
            else:
                extra = "<br><small>En espera de motocicleta disponible.</small>"
            st.markdown(f"""
            <div class="status-bi status-bi-success">
                <div class="status-bi-tag status-bi-tag-success">Correcto</div>
                <div class="status-bi-title">Reservación Registrada</div>
                <div class="status-bi-msg">{message}{extra}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="status-bi status-bi-error">
                <div class="status-bi-tag status-bi-tag-error">Error</div>
                <div class="status-bi-title">Error al Registrar</div>
                <div class="status-bi-msg">{message}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("OK — Volver al Menú Principal", type="primary", key="btn_ok_reservation"):
            _clear_reservation_state()
            go_to("main")


def page_reservation():
    page_header("Reservaciones", "Registrar Reservación")

    if st.session_state.get("reservation_ran"):
        _show_reservation_result()
        return

    # ------------------------------------------------------------------ #
    # Data loading                                                         #
    # ------------------------------------------------------------------ #
    try:
        resp_dealerships = requests.get(f"{API}/reservations/dealerships")
        dealerships = resp_dealerships.json() if resp_dealerships.status_code == 200 else []
    except requests.exceptions.ConnectionError:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.error("No se puede conectar al servidor.")
            if st.button("← Volver", key="btn_back_res_conn_error_d"):
                go_to("main")
        return

    try:
        resp_clients = requests.get(f"{API}/reservations/clients")
        clients = resp_clients.json() if resp_clients.status_code == 200 else []
    except requests.exceptions.ConnectionError:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.error("No se puede conectar al servidor.")
            if st.button("← Volver", key="btn_back_res_conn_error_c"):
                go_to("main")
        return

    try:
        resp_models = requests.get(f"{API}/reservations/models")
        models = resp_models.json() if resp_models.status_code == 200 else []
    except requests.exceptions.ConnectionError:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.error("No se puede conectar al servidor.")
            if st.button("← Volver", key="btn_back_res_conn_error_m"):
                go_to("main")
        return

    # ------------------------------------------------------------------ #
    # Form                                                                 #
    # ------------------------------------------------------------------ #
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="bi-card">', unsafe_allow_html=True)

        # ── Section 1: Sucursal ─────────────────────────────────────────
        st.markdown('<div class="card-section">Sucursal</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="upload-label">Selecciona la sucursal de la reservación</div>',
            unsafe_allow_html=True,
        )
        dealership_options = ["Seleccionar sucursal..."] + [d["name"] for d in dealerships]
        selected_dealership = st.selectbox(
            "Sucursal",
            options=dealership_options,
            key="reservation_dealership",
            label_visibility="collapsed",
        )

        st.markdown('<hr class="card-divider">', unsafe_allow_html=True)

        # ── Section 2: Cliente ──────────────────────────────────────────
        st.markdown('<div class="card-section">Cliente</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="upload-label">Selecciona el cliente que realiza la reservación</div>',
            unsafe_allow_html=True,
        )
        client_options = ["Seleccionar cliente..."] + [
            f"{c['nombre_completo']} — CURP: {c['curp']}" for c in clients
        ]
        selected_client = st.selectbox(
            "Cliente",
            options=client_options,
            key="reservation_client",
            label_visibility="collapsed",
        )

        st.markdown('<hr class="card-divider">', unsafe_allow_html=True)

        # ── Section 3: Modelo ───────────────────────────────────────────
        st.markdown('<div class="card-section">Modelo de Motocicleta</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="upload-label">Selecciona el modelo que desea reservar</div>',
            unsafe_allow_html=True,
        )
        model_label_to_obj = {
            f"{m['canonical_name']} — {m['year']}": m for m in models
        }
        model_options = ["Seleccionar modelo..."] + list(model_label_to_obj.keys())
        selected_model_label = st.selectbox(
            "Modelo",
            options=model_options,
            key="reservation_model",
            label_visibility="collapsed",
        )

        st.markdown('<hr class="card-divider">', unsafe_allow_html=True)

        # ── Section 4: Colores (prioridad) ──────────────────────────────
        st.markdown('<div class="card-section">Colores de Preferencia</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="upload-label">Selecciona uno o más colores en orden de preferencia</div>',
            unsafe_allow_html=True,
        )

        selected_model_obj = model_label_to_obj.get(selected_model_label)
        available_colors = selected_model_obj["colors"] if selected_model_obj else []

        selected_colors = st.multiselect(
            "Colores",
            options=available_colors,
            key="reservation_colors",
            label_visibility="collapsed",
            disabled=(not available_colors),
        )

        if selected_colors:
            priority_lines = "  ".join(
                f"**{i+1}.** {c}" for i, c in enumerate(selected_colors)
            )
            st.caption(f"Prioridad: {priority_lines}")
        elif not available_colors and selected_model_obj:
            st.caption("Este modelo no tiene colores registrados en el catálogo.")
        else:
            st.caption("Selecciona un modelo para ver colores disponibles.")

        st.markdown('<hr class="card-divider">', unsafe_allow_html=True)

        # ── Section 5: Monto ────────────────────────────────────────────
        st.markdown('<div class="card-section">Monto de Reservación</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="upload-label">Monto del depósito de reservación en pesos mexicanos</div>',
            unsafe_allow_html=True,
        )
        deposit_amount = st.number_input(
            "Monto",
            min_value=0.0,
            value=0.0,
            step=100.0,
            format="%.2f",
            key="reservation_amount",
            label_visibility="collapsed",
        )

        st.markdown("</div>", unsafe_allow_html=True)

        # ── Buttons ─────────────────────────────────────────────────────
        no_dealership = selected_dealership == "Seleccionar sucursal..."
        no_client     = selected_client     == "Seleccionar cliente..."
        no_model      = selected_model_label == "Seleccionar modelo..."
        no_colors     = len(selected_colors) == 0
        send_disabled = no_dealership or no_client or no_model or no_colors or deposit_amount <= 0

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("← Volver", key="btn_back_reservation"):
                _clear_reservation_state()
                go_to("main")
        with btn_col2:
            if st.button(
                "Registrar Reservación",
                key="btn_send_reservation",
                type="primary",
                disabled=send_disabled,
            ):
                # Resolve IDs from selected labels
                dealership_id = next(
                    (d["dealership_id"] for d in dealerships if d["name"] == selected_dealership),
                    None,
                )
                client_id = next(
                    (c["client_id"] for c in clients if c["nombre_completo"] in selected_client),
                    None,
                )
                model_id = selected_model_obj["model_id"] if selected_model_obj else None

                status_placeholder = st.empty()
                status_placeholder.info("Registrando reservación...")

                try:
                    resp = requests.post(
                        f"{API}/reservations/create",
                        json={
                            "client_id":      client_id,
                            "model_id":       model_id,
                            "dealership_id":  dealership_id,
                            "colors":         selected_colors,
                            "deposit_amount": float(deposit_amount),
                        },
                    )
                    if resp.status_code != 200:
                        st.session_state.reservation_ran     = True
                        st.session_state.reservation_success = False
                        st.session_state.reservation_message = f"Error del servidor: {resp.text}"
                        st.session_state.reservation_assigned = False
                    else:
                        result = resp.json()
                        if not result.get("success"):
                            st.session_state.reservation_ran     = True
                            st.session_state.reservation_success = False
                            st.session_state.reservation_message = result.get("message", "Error desconocido.")
                            st.session_state.reservation_assigned = False
                        else:
                            st.session_state.reservation_ran      = True
                            st.session_state.reservation_success  = True
                            st.session_state.reservation_message  = result["message"]
                            st.session_state.reservation_assigned = result.get("assigned", False)
                except Exception as e:
                    st.session_state.reservation_ran     = True
                    st.session_state.reservation_success = False
                    st.session_state.reservation_message = str(e)
                    st.session_state.reservation_assigned = False
                st.rerun()
