import requests
import streamlit as st

from ui.config import API, go_to
from ui.components import page_header, status_box_html


def _run_order_conf_pipeline(pdf_file):
    status_placeholder = st.empty()

    def show_status(message: str, state: str = "loading"):
        tag = {"loading": "Procesando", "success": "Correcto", "error": "Error"}[state]
        title = {
            "loading": "Procesando documento...",
            "success": "Confirmación registrada",
            "error":   "Error en la confirmación",
        }[state]
        status_placeholder.markdown(
            status_box_html(state, tag, title, message),
            unsafe_allow_html=True,
        )

    try:
        show_status("Creando evento de confirmación de orden...", "loading")
        resp = requests.post(f"{API}/events/", params={"event_type_name": "order_confirmation"})
        if resp.status_code != 200:
            raise RuntimeError(f"Error al crear el evento: {resp.text}")

        event_data  = resp.json()
        submissions = {s["slot_name"]: s["submission_id"] for s in event_data["submissions"]}
        sub_id      = submissions.get("order_table")
        if not sub_id:
            raise RuntimeError("No se encontró el slot de confirmación de orden.")

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

        st.session_state.order_conf_ran        = True
        st.session_state.order_conf_success    = True
        st.session_state.order_conf_message    = result["message"]
        st.session_state.order_conf_confidence = result.get("confidence")

    except Exception as e:
        st.session_state.order_conf_ran     = True
        st.session_state.order_conf_success = False
        st.session_state.order_conf_message = str(e)

    st.rerun()


def _show_order_conf_result():
    success    = st.session_state.get("order_conf_success", False)
    message    = st.session_state.get("order_conf_message", "")
    confidence = st.session_state.get("order_conf_confidence")
    confidence_str = f"{confidence:.0%}" if confidence is not None else "N/A"

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if success:
            st.markdown(f"""
            <div class="status-bi status-bi-success">
                <div class="status-bi-tag status-bi-tag-success">Correcto</div>
                <div class="status-bi-title">Confirmación Registrada</div>
                <div class="status-bi-msg">{message}</div>
                <div class="status-bi-meta">Confianza IA: {confidence_str}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="status-bi status-bi-error">
                <div class="status-bi-tag status-bi-tag-error">Error</div>
                <div class="status-bi-title">Error en la Confirmación</div>
                <div class="status-bi-msg">{message}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Volver al Panel Principal", type="primary", key="btn_ok_order_conf"):
            for key in ["order_conf_ran", "order_conf_success",
                        "order_conf_message", "order_conf_confidence"]:
                st.session_state.pop(key, None)
            go_to("main")


def page_order_confirmation():
    page_header("Inventario", "Registrar Orden de Traslado")

    if st.session_state.get("order_conf_ran"):
        _show_order_conf_result()
        return

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="bi-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-section">Aviso de Traslado</div>', unsafe_allow_html=True)
        st.markdown('<div class="upload-label">Archivo PDF del aviso de traslado</div>',
                    unsafe_allow_html=True)
        pdf_file = st.file_uploader(
            "Aviso de Traslado PDF",
            type=["pdf"],
            key="upload_order_conf_pdf",
            label_visibility="collapsed",
        )
        if pdf_file:
            st.success(f"Archivo cargado: {pdf_file.name}")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("Volver", key="btn_back_order_conf"):
                for key in ["order_conf_ran", "order_conf_success",
                            "order_conf_message", "order_conf_confidence"]:
                    st.session_state.pop(key, None)
                go_to("main")
        with btn_col2:
            if st.button(
                "Enviar y Procesar",
                key="btn_send_order_conf",
                disabled=pdf_file is None,
                type="primary",
            ):
                _run_order_conf_pipeline(pdf_file)
