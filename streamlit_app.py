import streamlit as st
from ui.styles import inject_styles
from ui.nav import topbar
from ui.pages import route

st.set_page_config(
    page_title="Moto Dealer — Bajaj",
    page_icon="🏍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "page" not in st.session_state:
    st.session_state.page = "main"

inject_styles()
topbar()
route(st.session_state.page)
