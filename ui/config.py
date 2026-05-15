import streamlit as st

API = "http://localhost:8000"


def go_to(page: str, **kwargs):
    st.session_state.page = page
    for k, v in kwargs.items():
        st.session_state[k] = v
    st.rerun()
