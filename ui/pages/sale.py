import requests
import streamlit as st

from ui.config import API, go_to
from ui.components import page_header


def _clear_sale_state():
    keys = [
        "sale_ran", "sale_success", "sale_message",
        "sale_contract_id", "sale_contract_number", "sale_has_solicitud",
        "sale_client", "sale_motorcycle", "sale_sale_type",
        "sale_payment_method", "sale_downpayment", "sale_institution",
        "sale_payment_bank", "sale_reference_name", "sale_reference_phone",
        "sale_reference_relation", "sale_buyer_colonia", "sale_buyer_cp",
        "sale_buyer_municipio", "sale_buyer_estado",
        "sale_motos_data",
    ]
    for k in keys:
        st.session_state.pop(k, None)


def _show_sale_result():
    success         = st.session_state.get("sale_success", False)
    message         = st.session_state.get("sale_message", "")
    contract_id     = st.session_state.get("sale_contract_id")
    contract_number = st.session_state.get("sale_contract_number", "")
    has_solicitud   = st.session_state.get("sale_has_solicitud", False)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if success:
            st.markdown(f"""
            <div class="status-bi status-bi-success">
                <div class="status-bi-tag status-bi-tag-success">Correcto</div>
                <div class="status-bi-title">Venta Registrada</div>
                <div class="status-bi-msg">Contrato: {contract_number}<br>{message}</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            try:
                resp = requests.get(
                    f"{API}/sales/{contract_id}/download/contrato",
                    timeout=10,
                )
                st.download_button(
                    label="⬇ Descargar Contrato",
                    data=resp.content,
                    file_name=f"{contract_number}_contrato.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="btn_dl_contrato",
                )
            except Exception:
                st.warning("No se pudo descargar el contrato.")

            if has_solicitud:
                try:
                    resp2 = requests.get(
                        f"{API}/sales/{contract_id}/download/solicitud",
                        timeout=10,
                    )
                    st.download_button(
                        label="⬇ Descargar Solicitud de Crédito",
                        data=resp2.content,
                        file_name=f"{contract_number}_solicitud.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="btn_dl_solicitud",
                    )
                except Exception:
                    st.warning("No se pudo descargar la solicitud de crédito.")

        else:
            st.markdown(f"""
            <div class="status-bi status-bi-error">
                <div class="status-bi-tag status-bi-tag-error">Error</div>
                <div class="status-bi-title">Error en la Venta</div>
                <div class="status-bi-msg">{message}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("OK — Volver al Menú Principal", key="btn_ok_sale", type="primary"):
            _clear_sale_state()
            go_to("main")


def page_sale():
    page_header("Ventas", "Iniciar Venta")
    st.markdown(
        '<div class="upload-label" style="margin-bottom:1rem;">'
        'Registra una nueva venta de motocicleta</div>',
        unsafe_allow_html=True,
    )

    if st.session_state.get("sale_ran"):
        _show_sale_result()
        return

    # ------------------------------------------------------------------ #
    # Data loading — fresh every page load                                 #
    # ------------------------------------------------------------------ #
    try:
        clients      = requests.get(f"{API}/sales/clients").json()
        institutions = requests.get(f"{API}/sales/credit-institutions").json()
    except requests.exceptions.ConnectionError:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.error("No se puede conectar al servidor.")
            if st.button("← Volver", key="btn_back_sale_conn"):
                go_to("main")
        return

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="bi-card">', unsafe_allow_html=True)

        # ── Section 1: Tipo de Venta ────────────────────────────────────
        st.markdown('<div class="card-section">Tipo de Venta</div>', unsafe_allow_html=True)
        st.radio(
            "Tipo de Venta",
            options=["Al Contado", "A Crédito"],
            key="sale_sale_type",
            horizontal=True,
            label_visibility="collapsed",
        )

        st.markdown('<hr class="card-divider">', unsafe_allow_html=True)

        # ── Section 2: Cliente ──────────────────────────────────────────
        st.markdown('<div class="card-section">Cliente</div>', unsafe_allow_html=True)
        client_options = ["Seleccionar cliente..."] + [
            f"{c['nombre_completo']} — CURP: {c['curp']}" for c in clients
        ]
        st.selectbox(
            "Cliente",
            options=client_options,
            key="sale_client",
            label_visibility="collapsed",
        )
        selected_client = st.session_state.get("sale_client", "Seleccionar cliente...")

        st.markdown('<hr class="card-divider">', unsafe_allow_html=True)

        # ── Section 3: Motocicleta ──────────────────────────────────────
        st.markdown('<div class="card-section">Motocicleta</div>', unsafe_allow_html=True)

        motos      = []
        moto_price = None

        if selected_client == "Seleccionar cliente...":
            st.info("Selecciona un cliente primero.")
        else:
            client_id = None
            for c in clients:
                if f"{c['nombre_completo']} — CURP: {c['curp']}" == selected_client:
                    client_id = c["client_id"]
                    break

            try:
                motos = requests.get(
                    f"{API}/sales/motorcycles?client_id={client_id}"
                ).json()
            except Exception:
                motos = []

            st.session_state.sale_motos_data = motos

            moto_options = ["Seleccionar motocicleta..."] + [
                f"{'⭐ ' if m['pre_selected'] else ''}"
                f"{m['model']} {m['year']} — {m['color']} — "
                f"{m['dealership']} — ${m['price']:,.2f}"
                for m in motos
            ]

            # Auto-select pre_selected if still on default
            for m in motos:
                if m["pre_selected"]:
                    option_str = (
                        f"⭐ {m['model']} {m['year']} — {m['color']} — "
                        f"{m['dealership']} — ${m['price']:,.2f}"
                    )
                    if st.session_state.get(
                        "sale_motorcycle", "Seleccionar motocicleta..."
                    ) == "Seleccionar motocicleta...":
                        st.session_state.sale_motorcycle = option_str
                    break

            st.selectbox(
                "Motocicleta",
                options=moto_options,
                key="sale_motorcycle",
                label_visibility="collapsed",
            )

            selected_motorcycle = st.session_state.get(
                "sale_motorcycle", "Seleccionar motocicleta..."
            )
            if selected_motorcycle != "Seleccionar motocicleta...":
                for m in motos:
                    opt = (
                        f"{'⭐ ' if m['pre_selected'] else ''}"
                        f"{m['model']} {m['year']} — {m['color']} — "
                        f"{m['dealership']} — ${m['price']:,.2f}"
                    )
                    if opt == selected_motorcycle:
                        moto_price = m["price"]
                        break
                if moto_price is not None:
                    st.caption(f"Precio: ${moto_price:,.2f}")

        st.markdown('<hr class="card-divider">', unsafe_allow_html=True)

        # ── Section 4: Método de Pago ───────────────────────────────────
        st.markdown('<div class="card-section">Método de Pago</div>', unsafe_allow_html=True)
        st.selectbox(
            "Método de Pago",
            options=["Transferencia", "Efectivo"],
            key="sale_payment_method",
            label_visibility="collapsed",
        )

        # ── Section 5: Datos de Crédito ─────────────────────────────────
        sale_type_val = st.session_state.get("sale_sale_type", "Al Contado")
        if sale_type_val == "A Crédito":
            st.markdown('<hr class="card-divider">', unsafe_allow_html=True)
            st.markdown('<div class="card-section">Datos de Crédito</div>', unsafe_allow_html=True)

            st.markdown('<div class="upload-label">Enganche</div>', unsafe_allow_html=True)
            downpayment = st.number_input(
                "Enganche",
                min_value=0.01,
                step=100.0,
                format="%.2f",
                key="sale_downpayment",
                label_visibility="collapsed",
            )
            if moto_price is not None and downpayment:
                pendiente = moto_price - downpayment
                st.caption(f"Pendiente: ${pendiente:,.2f}")
                if downpayment >= moto_price:
                    st.warning("El enganche es mayor o igual al precio de la motocicleta.")

            st.markdown('<div class="upload-label">Institución Financiera</div>',
                        unsafe_allow_html=True)
            institution_options = ["Seleccionar institución..."] + [
                i["name"] for i in institutions
            ]
            st.selectbox(
                "Institución Financiera",
                options=institution_options,
                key="sale_institution",
                label_visibility="collapsed",
            )

            st.markdown('<div class="upload-label">Banco</div>', unsafe_allow_html=True)
            st.text_input(
                "Banco",
                placeholder="Nombre del banco",
                key="sale_payment_bank",
                label_visibility="collapsed",
            )

            st.markdown('<hr class="card-divider">', unsafe_allow_html=True)
            st.markdown('<div class="card-section">Referencia Personal</div>',
                        unsafe_allow_html=True)
            r1, r2, r3 = st.columns(3)
            with r1:
                st.text_input("Nombre", key="sale_reference_name")
            with r2:
                st.text_input("Teléfono", key="sale_reference_phone")
            with r3:
                st.text_input("Parentesco", key="sale_reference_relation")

            st.markdown('<hr class="card-divider">', unsafe_allow_html=True)
            st.markdown('<div class="card-section">Domicilio del Cliente (para solicitud)</div>',
                        unsafe_allow_html=True)
            st.caption("Estos datos son necesarios para generar la solicitud de crédito.")

            d1, d2 = st.columns(2)
            with d1:
                st.text_input("Colonia", key="sale_buyer_colonia")
            with d2:
                st.text_input("Código Postal", key="sale_buyer_cp")

            d3, d4 = st.columns(2)
            with d3:
                st.text_input("Alcaldía / Municipio", key="sale_buyer_municipio")
            with d4:
                st.text_input("Estado", key="sale_buyer_estado")

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        # ── Disabled logic ───────────────────────────────────────────────
        no_client = selected_client == "Seleccionar cliente..."
        no_moto   = st.session_state.get(
            "sale_motorcycle", "Seleccionar motocicleta..."
        ) == "Seleccionar motocicleta..."

        send_disabled = no_client or no_moto

        if sale_type_val == "A Crédito":
            dp      = st.session_state.get("sale_downpayment") or 0
            inst    = st.session_state.get("sale_institution", "Seleccionar institución...")
            r_name  = (st.session_state.get("sale_reference_name") or "").strip()
            r_phone = (st.session_state.get("sale_reference_phone") or "").strip()
            r_rel   = (st.session_state.get("sale_reference_relation") or "").strip()
            colonia = (st.session_state.get("sale_buyer_colonia") or "").strip()
            cp      = (st.session_state.get("sale_buyer_cp") or "").strip()
            mun     = (st.session_state.get("sale_buyer_municipio") or "").strip()
            estado  = (st.session_state.get("sale_buyer_estado") or "").strip()

            send_disabled = send_disabled or (
                dp <= 0
                or inst == "Seleccionar institución..."
                or not r_name
                or not r_phone
                or not r_rel
                or not colonia
                or not cp
                or not mun
                or not estado
            )

        # ── Buttons ──────────────────────────────────────────────────────
        btn1, btn2 = st.columns(2)
        with btn1:
            if st.button("← Volver", key="btn_back_sale"):
                _clear_sale_state()
                go_to("main")

        with btn2:
            if st.button(
                "Registrar Venta ✓",
                key="btn_send_sale",
                type="primary",
                disabled=send_disabled,
            ):
                # Resolve IDs
                client_label = st.session_state.get("sale_client", "")
                submit_client_id = None
                for c in clients:
                    if f"{c['nombre_completo']} — CURP: {c['curp']}" == client_label:
                        submit_client_id = c["client_id"]
                        break

                moto_label = st.session_state.get("sale_motorcycle", "")
                submit_motorcycle_id = None
                for m in st.session_state.get("sale_motos_data", []):
                    opt = (
                        f"{'⭐ ' if m['pre_selected'] else ''}"
                        f"{m['model']} {m['year']} — {m['color']} — "
                        f"{m['dealership']} — ${m['price']:,.2f}"
                    )
                    if opt == moto_label:
                        submit_motorcycle_id = m["motorcycle_id"]
                        break

                inst_name = st.session_state.get("sale_institution", "")
                submit_institution_id = None
                for i in institutions:
                    if i["name"] == inst_name:
                        submit_institution_id = i["credit_institution_id"]
                        break

                st_raw = st.session_state.get("sale_sale_type", "Al Contado")
                sale_type_body = "contado" if "Contado" in st_raw else "credito"

                pm_raw = st.session_state.get("sale_payment_method", "Transferencia")
                pm_body = "transferencia" if "Transferencia" in pm_raw else "efectivo"

                status_placeholder = st.empty()
                status_placeholder.info("Registrando venta...")

                try:
                    resp = requests.post(
                        f"{API}/sales/create",
                        json={
                            "client_id":              submit_client_id,
                            "motorcycle_id":          submit_motorcycle_id,
                            "sale_type":              sale_type_body,
                            "payment_method":         pm_body,
                            "payment_downpayment":    st.session_state.get("sale_downpayment"),
                            "payment_institution_id": submit_institution_id,
                            "payment_bank":           st.session_state.get("sale_payment_bank"),
                            "reference_name":         st.session_state.get("sale_reference_name"),
                            "reference_phone":        st.session_state.get("sale_reference_phone"),
                            "reference_relation":     st.session_state.get("sale_reference_relation"),
                            "buyer_colonia":          st.session_state.get("sale_buyer_colonia"),
                            "buyer_cp":               st.session_state.get("sale_buyer_cp"),
                            "buyer_municipio":        st.session_state.get("sale_buyer_municipio"),
                            "buyer_estado":           st.session_state.get("sale_buyer_estado"),
                        },
                        timeout=15,
                    )
                    result = resp.json()
                    if result.get("success"):
                        st.session_state.sale_ran             = True
                        st.session_state.sale_success         = True
                        st.session_state.sale_message         = result["message"]
                        st.session_state.sale_contract_id     = result["contract_id"]
                        st.session_state.sale_contract_number = result["contract_number"]
                        st.session_state.sale_has_solicitud   = result["has_solicitud"]
                    else:
                        st.session_state.sale_ran     = True
                        st.session_state.sale_success = False
                        st.session_state.sale_message = result.get("message", "Error desconocido.")
                except Exception as e:
                    st.session_state.sale_ran     = True
                    st.session_state.sale_success = False
                    st.session_state.sale_message = str(e)

                st.rerun()
