import streamlit as st
from ui.config import go_to
from ui.components import page_header


def page_placeholder(title: str, page_key: str):
    page_header("Sistema", title)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f"""
        <div class="placeholder-box">
            <div class="placeholder-title">En construcción</div>
            <div class="placeholder-msg">
                Esta sección estará disponible próximamente.<br>
                Estamos trabajando en ello.
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Volver al Panel Principal", key=f"btn_back_{page_key}", type="primary"):
            go_to("main")
