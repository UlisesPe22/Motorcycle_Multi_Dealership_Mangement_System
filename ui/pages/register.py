import requests
import streamlit as st
from PIL import Image

from ui.config import API, go_to
from ui.components import page_header, status_box_html


def _run_pipeline(front_file, back_file):
    status_placeholder = st.empty()

    def show_status(message: str, state: str = "loading"):
        tag = {"loading": "Procesando", "success": "Correcto", "error": "Error"}[state]
        title = {
            "loading": "Procesando documento...",
            "success": "Registro exitoso",
            "error":   "Error en el registro",
        }[state]
        status_placeholder.markdown(
            status_box_html(state, tag, title, message),
            unsafe_allow_html=True,
        )

    try:
        show_status("Creando evento de registro...", "loading")
        resp = requests.post(f"{API}/events/", params={"event_type_name": "client_registration"})
        if resp.status_code != 200:
            raise RuntimeError(f"Error al crear el evento: {resp.text}")

        event_data   = resp.json()
        submissions  = {s["slot_name"]: s["submission_id"] for s in event_data["submissions"]}
        front_sub_id = submissions["id_front"]
        back_sub_id  = submissions["id_back"]

        show_status("Validando frente del INE con IA...", "loading")
        front_file.seek(0)
        resp = requests.post(
            f"{API}/submissions/{front_sub_id}/upload",
            files={"file": (front_file.name, front_file, front_file.type)},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Error en frente: {resp.text}")
        front_result = resp.json()
        if not front_result["success"]:
            raise RuntimeError(front_result["message"])

        show_status("Validando reverso del INE con IA...", "loading")
        back_file.seek(0)
        resp = requests.post(
            f"{API}/submissions/{back_sub_id}/upload",
            files={"file": (back_file.name, back_file, back_file.type)},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Error en reverso: {resp.text}")
        back_result = resp.json()
        if not back_result["success"]:
            raise RuntimeError(back_result["message"])

        st.session_state.pipeline_ran     = True
        st.session_state.pipeline_success = True
        st.session_state.pipeline_message = back_result["message"]

    except Exception as e:
        st.session_state.pipeline_ran     = True
        st.session_state.pipeline_success = False
        st.session_state.pipeline_message = str(e)

    st.rerun()


def _show_pipeline_result():
    success = st.session_state.get("pipeline_success", False)
    message = st.session_state.get("pipeline_message", "")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if success:
            st.markdown(f"""
            <div class="status-bi status-bi-success">
                <div class="status-bi-tag status-bi-tag-success">Correcto</div>
                <div class="status-bi-title">Registro Exitoso</div>
                <div class="status-bi-msg">{message}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="status-bi status-bi-error">
                <div class="status-bi-tag status-bi-tag-error">Error</div>
                <div class="status-bi-title">Registro Fallido</div>
                <div class="status-bi-msg">{message}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Volver al Panel Principal", type="primary", key="btn_ok_result"):
            for key in ["pipeline_ran", "pipeline_success", "pipeline_message",
                        "event_data", "upload_front", "upload_back"]:
                st.session_state.pop(key, None)
            go_to("main")


def page_register():
    page_header("Clientes", "Registrar Cliente")

    if st.session_state.get("pipeline_ran"):
        _show_pipeline_result()
        return

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="bi-card">', unsafe_allow_html=True)

        st.markdown('<div class="card-section">Frente del INE</div>', unsafe_allow_html=True)
        st.markdown('<div class="upload-label">Parte frontal de la credencial de elector</div>',
                    unsafe_allow_html=True)
        front_file = st.file_uploader(
            "Frente del INE",
            type=["jpg", "jpeg", "png"],
            key="upload_front",
            label_visibility="collapsed",
        )
        if front_file:
            img = Image.open(front_file)
            st.image(img, caption="Vista previa — Frente", use_container_width=True)

        st.markdown('<hr class="card-divider">', unsafe_allow_html=True)

        st.markdown('<div class="card-section">Reverso del INE</div>', unsafe_allow_html=True)
        st.markdown('<div class="upload-label">Parte trasera de la credencial de elector</div>',
                    unsafe_allow_html=True)
        back_file = st.file_uploader(
            "Reverso del INE",
            type=["jpg", "jpeg", "png"],
            key="upload_back",
            label_visibility="collapsed",
        )
        if back_file:
            img = Image.open(back_file)
            st.image(img, caption="Vista previa — Reverso", use_container_width=True)

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("Volver", key="btn_back_register"):
                for key in ["pipeline_ran", "pipeline_success", "pipeline_message",
                            "event_data", "upload_front", "upload_back"]:
                    st.session_state.pop(key, None)
                go_to("main")
        with btn_col2:
            send_disabled = not (front_file and back_file)
            if st.button(
                "Enviar y Procesar",
                key="btn_send",
                disabled=send_disabled,
                type="primary",
            ):
                _run_pipeline(front_file, back_file)
