import requests
import streamlit as st

from ui.config import API, go_to
from ui.components import page_header, status_box_html


def _run_purchase_pipeline(pdf_file):
    status_placeholder = st.empty()

    def show_status(message: str, state: str = "loading"):
        tag = {"loading": "Procesando", "success": "Correcto", "error": "Error"}[state]
        title = {
            "loading": "Procesando documento...",
            "success": "Pedido registrado",
            "error":   "Error en el pedido",
        }[state]
        status_placeholder.markdown(
            status_box_html(state, tag, title, message),
            unsafe_allow_html=True,
        )

    try:
        show_status("Creando evento de pedido de compra...", "loading")
        resp = requests.post(f"{API}/events/", params={"event_type_name": "purchase_order"})
        if resp.status_code != 200:
            raise RuntimeError(f"Error al crear el evento: {resp.text}")

        event_data  = resp.json()
        submissions = {s["slot_name"]: s["submission_id"] for s in event_data["submissions"]}
        sub_id      = submissions.get("purchase_order_table") or submissions.get("order_table")
        if not sub_id:
            raise RuntimeError("No se encontró el slot de pedido de compra.")

        show_status("Procesando PDF con IA...", "loading")
        pdf_file.seek(0)
        resp = requests.post(
            f"{API}/submissions/{sub_id}/upload",
            files={"file": (pdf_file.name, pdf_file, "application/pdf")},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Error al procesar el PDF: {resp.text}")

        result = resp.json()
        if not result["success"]:
            raise RuntimeError(result["message"])

        st.session_state.purchase_ran     = True
        st.session_state.purchase_success = True
        st.session_state.purchase_message = result["message"]

    except Exception as e:
        st.session_state.purchase_ran     = True
        st.session_state.purchase_success = False
        st.session_state.purchase_message = str(e)

    st.rerun()


def _show_purchase_result():
    success = st.session_state.get("purchase_success", False)
    message = st.session_state.get("purchase_message", "")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if success:
            st.markdown(f"""
            <div class="status-bi status-bi-success">
                <div class="status-bi-tag status-bi-tag-success">Correcto</div>
                <div class="status-bi-title">Pedido Registrado</div>
                <div class="status-bi-msg">{message}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="status-bi status-bi-error">
                <div class="status-bi-tag status-bi-tag-error">Error</div>
                <div class="status-bi-title">Error en el Pedido</div>
                <div class="status-bi-msg">{message}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Volver al Panel Principal", type="primary", key="btn_ok_purchase"):
            for key in ["purchase_ran", "purchase_success", "purchase_message"]:
                st.session_state.pop(key, None)
            go_to("main")


def page_purchase_order():
    page_header("Inventario", "Registrar Orden de Compra")

    if st.session_state.get("purchase_ran"):
        _show_purchase_result()
        return

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="bi-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-section">Documento de Pedido de Compra</div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="upload-label">Archivo PDF del pedido de compra</div>',
                    unsafe_allow_html=True)
        pdf_file = st.file_uploader(
            "Pedido de Compra PDF",
            type=["pdf"],
            key="upload_purchase_pdf",
            label_visibility="collapsed",
        )
        if pdf_file:
            st.success(f"Archivo cargado: {pdf_file.name}")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("Volver", key="btn_back_purchase"):
                for key in ["purchase_ran", "purchase_success", "purchase_message"]:
                    st.session_state.pop(key, None)
                go_to("main")
        with btn_col2:
            if st.button(
                "Enviar y Procesar",
                key="btn_send_purchase",
                disabled=pdf_file is None,
                type="primary",
            ):
                _run_purchase_pipeline(pdf_file)
