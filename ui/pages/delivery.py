import requests
import streamlit as st
from PIL import Image

from ui.config import API, go_to
from ui.components import page_header, status_box_html


def _fetch_dealerships() -> list:
    try:
        resp = requests.get(f"{API}/delivery-confirmations/dealerships")
        if resp.status_code == 200:
            return resp.json()
        return []
    except requests.exceptions.ConnectionError:
        return []


def _run_delivery_pipeline(delivery_file, declared_count: int, dealership_id: int):
    status_placeholder = st.empty()

    def show_status(message: str, state: str = "loading"):
        tag = {"loading": "Procesando", "success": "Correcto", "error": "Error"}[state]
        title = {
            "loading": "Procesando documento...",
            "success": "Entrega confirmada",
            "error":   "Error en la entrega",
        }[state]
        status_placeholder.markdown(
            status_box_html(state, tag, title, message),
            unsafe_allow_html=True,
        )

    try:
        show_status("Procesando documento de entrega con IA...", "loading")
        delivery_file.seek(0)
        resp = requests.post(
            f"{API}/delivery-confirmations/upload",
            files={"file": (delivery_file.name, delivery_file, delivery_file.type)},
            data={"declared_count": declared_count, "dealership_id": dealership_id},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Error del servidor: {resp.text}")
        result = resp.json()
        if not result["success"]:
            raise RuntimeError(result["message"])

        st.session_state.delivery_ran     = True
        st.session_state.delivery_success = True
        st.session_state.delivery_message = result["message"]

    except Exception as e:
        st.session_state.delivery_ran     = True
        st.session_state.delivery_success = False
        st.session_state.delivery_message = str(e)

    st.rerun()


def _show_delivery_result():
    success = st.session_state.get("delivery_success", False)
    message = st.session_state.get("delivery_message", "")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if success:
            st.markdown(f"""
            <div class="status-bi status-bi-success">
                <div class="status-bi-tag status-bi-tag-success">Correcto</div>
                <div class="status-bi-title">Entrega Confirmada</div>
                <div class="status-bi-msg">{message}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="status-bi status-bi-error">
                <div class="status-bi-tag status-bi-tag-error">Error</div>
                <div class="status-bi-title">Error en la Entrega</div>
                <div class="status-bi-msg">{message}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Volver al Panel Principal", type="primary", key="btn_ok_delivery"):
            for key in ["delivery_ran", "delivery_success",
                        "delivery_message", "delivery_confidence"]:
                st.session_state.pop(key, None)
            go_to("main")


def page_delivery_confirmation():
    page_header("Entregas", "Registrar Entrega")

    if st.session_state.get("delivery_ran"):
        _show_delivery_result()
        return

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="bi-card">', unsafe_allow_html=True)

        st.markdown('<div class="card-section">Sucursal</div>', unsafe_allow_html=True)
        dealerships = _fetch_dealerships()
        if not dealerships:
            st.error("No se pudieron cargar las sucursales. Verifica que el servidor esté corriendo.")
            st.markdown("</div>", unsafe_allow_html=True)
            if st.button("Volver", key="btn_back_delivery_error"):
                go_to("main")
            return

        dealership_names    = [d["name"] for d in dealerships]
        selected_name       = st.selectbox(
            "Sucursal",
            options=dealership_names,
            key="delivery_dealership",
            label_visibility="collapsed",
        )
        selected_dealership = next((d for d in dealerships if d["name"] == selected_name), None)

        st.markdown('<hr class="card-divider">', unsafe_allow_html=True)

        st.markdown('<div class="card-section">Total de Motocicletas</div>', unsafe_allow_html=True)
        st.markdown('<div class="upload-label">Cantidad declarada en el documento de entrega</div>',
                    unsafe_allow_html=True)
        declared_count = st.number_input(
            "Total",
            min_value=1, max_value=100, value=1, step=1,
            key="delivery_count",
            label_visibility="collapsed",
        )

        st.markdown('<hr class="card-divider">', unsafe_allow_html=True)

        st.markdown('<div class="card-section">Documento de Entrega</div>', unsafe_allow_html=True)
        st.markdown('<div class="upload-label">Foto o PDF del documento de entrega física</div>',
                    unsafe_allow_html=True)
        delivery_file = st.file_uploader(
            "Documento de Entrega",
            type=["pdf", "jpg", "jpeg", "png"],
            key="upload_delivery_file",
            label_visibility="collapsed",
        )
        if delivery_file:
            if delivery_file.type == "application/pdf":
                st.success(f"PDF cargado: {delivery_file.name}")
            else:
                img = Image.open(delivery_file)
                st.image(img, caption="Vista previa", use_container_width=True)

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("Volver", key="btn_back_delivery"):
                for key in ["delivery_ran", "delivery_success",
                            "delivery_message", "delivery_confidence"]:
                    st.session_state.pop(key, None)
                go_to("main")
        with btn_col2:
            send_disabled = delivery_file is None or selected_dealership is None
            if st.button(
                "Enviar y Procesar",
                key="btn_send_delivery",
                disabled=send_disabled,
                type="primary",
            ):
                _run_delivery_pipeline(
                    delivery_file,
                    int(declared_count),
                    selected_dealership["dealership_id"],
                )
