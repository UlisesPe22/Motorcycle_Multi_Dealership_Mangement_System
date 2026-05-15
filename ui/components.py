import streamlit as st


def page_header(section: str, title: str):
    st.markdown(f"""
    <div class="page-header">
        <div class="breadcrumb">Moto Dealer <span>/</span> {section}</div>
        <div class="page-title-bi">{title}</div>
    </div>
    <hr class="page-rule">
    """, unsafe_allow_html=True)


def status_box_html(state: str, tag: str, title: str, message: str, meta: str = "") -> str:
    meta_html = f'<div class="status-bi-meta">{meta}</div>' if meta else ""
    return f"""
    <div class="status-bi status-bi-{state}">
        <div class="status-bi-tag status-bi-tag-{state}">{tag}</div>
        <div class="status-bi-title">{title}</div>
        <div class="status-bi-msg">{message}</div>
        {meta_html}
    </div>
    """
