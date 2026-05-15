import streamlit as st


def inject_styles():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

*, *::before, *::after { box-sizing: border-box; }

html, body, .stApp {
    background-color: #F5F7FA;
    font-family: 'Inter', sans-serif;
    color: #1A2332;
}

/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.block-container {
    padding-top: 1.75rem !important;
    padding-bottom: 2rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    max-width: 100% !important;
}

/* ── Sidebar ──────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #16213E !important;
    min-width: 220px !important;
    max-width: 220px !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding: 0 !important;
    background-color: #16213E !important;
}
[data-testid="stSidebarContent"] {
    padding: 0 !important;
    background-color: #16213E !important;
}
[data-testid="stSidebarResizeHandle"] { display: none !important; }
button[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"] { display: none !important; }

/* Brand block */
.sidebar-brand {
    padding: 1.4rem 1.1rem 1.1rem 1.1rem;
    border-bottom: 1px solid rgba(255,255,255,0.07);
    margin-bottom: 0.25rem;
}
.sidebar-brand-name {
    font-size: 0.92rem;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: 0.01em;
    line-height: 1.2;
}
.sidebar-brand-sub {
    font-size: 0.61rem;
    color: rgba(255,255,255,0.32);
    letter-spacing: 0.11em;
    text-transform: uppercase;
    margin-top: 3px;
}

/* Section labels inside sidebar */
.sidebar-section {
    font-size: 0.57rem;
    font-weight: 600;
    color: rgba(255,255,255,0.26);
    letter-spacing: 0.15em;
    text-transform: uppercase;
    padding: 1.1rem 1.1rem 0.3rem 1.1rem;
}

/* Active nav item — rendered as HTML div, not a button */
.sidebar-nav-active {
    display: block;
    padding: 0.55rem 1.1rem;
    border-left: 3px solid #0A66C2;
    background: rgba(10,102,194,0.13);
    color: #60A5FA;
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.005em;
    font-family: 'Inter', sans-serif;
    line-height: 1.4;
}

/* Disabled "Próximamente" nav item */
.sidebar-nav-soon {
    display: block;
    padding: 0.55rem 1.1rem;
    border-left: 3px solid transparent;
    color: rgba(255,255,255,0.2);
    font-size: 0.8rem;
    font-weight: 400;
    letter-spacing: 0.005em;
    font-family: 'Inter', sans-serif;
    line-height: 1.4;
    cursor: default;
    user-select: none;
}
.soon-badge {
    display: inline-block;
    background: rgba(255,255,255,0.07);
    color: rgba(255,255,255,0.22);
    font-size: 0.52rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 0.1rem 0.35rem;
    border-radius: 3px;
    vertical-align: middle;
    margin-left: 0.4rem;
}

/* ── Page header (breadcrumb + rule) ──────────────────────────────────────── */
.page-header { margin-bottom: 0; }
.breadcrumb {
    font-size: 0.67rem;
    font-weight: 500;
    color: #94A3B8;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    margin-bottom: 0.25rem;
}
.breadcrumb span { color: #CBD5E1; margin: 0 0.3em; }
.page-title-bi {
    font-size: 1.2rem;
    font-weight: 600;
    color: #1A2332;
    margin-bottom: 0.85rem;
    letter-spacing: -0.015em;
}
.page-rule {
    border: none;
    border-top: 1px solid #E2E8F0;
    margin: 0 0 1.5rem 0;
}

/* ── White surface cards ──────────────────────────────────────────────────── */
.bi-card {
    background: #ffffff;
    border: 1px solid #E8ECF0;
    border-radius: 7px;
    padding: 1.75rem;
    margin-bottom: 1.25rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

/* ── Dashboard inventory placeholder ─────────────────────────────────────── */
.inventory-placeholder {
    background: #ffffff;
    border: 1.5px dashed #C8D3DC;
    border-radius: 7px;
    min-height: calc(75vh - 100px);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    margin-top: 0.5rem;
}
.inventory-placeholder-label {
    font-size: 0.7rem;
    font-weight: 700;
    color: #94A3B8;
    letter-spacing: 0.14em;
    text-transform: uppercase;
}
.inventory-placeholder-sub {
    font-size: 0.67rem;
    color: #C8D3DC;
    letter-spacing: 0.04em;
}

/* ── Card section headings ────────────────────────────────────────────────── */
.card-section {
    font-size: 0.61rem;
    font-weight: 700;
    color: #0A66C2;
    text-transform: uppercase;
    letter-spacing: 0.13em;
    margin-bottom: 0.6rem;
    padding-bottom: 0.45rem;
    border-bottom: 1px solid #EFF6FF;
}
.card-divider {
    border: none;
    border-top: 1px solid #F1F5F9;
    margin: 1.25rem 0;
}

/* ── Upload helper text ───────────────────────────────────────────────────── */
.upload-label {
    font-size: 0.74rem;
    font-weight: 500;
    color: #64748B;
    margin-bottom: 0.35rem;
}

/* ── Status boxes — left-border accent, no emoji primary ─────────────────── */
.status-bi {
    background: #ffffff;
    border: 1px solid #E8ECF0;
    border-left: 4px solid #94A3B8;
    border-radius: 6px;
    padding: 1.1rem 1.4rem;
    margin: 0.75rem auto;
    max-width: 560px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.status-bi-success { border-left-color: #16A34A !important; }
.status-bi-error   { border-left-color: #DC2626 !important; }
.status-bi-loading { border-left-color: #0A66C2 !important; }

.status-bi-tag {
    font-size: 0.57rem;
    font-weight: 700;
    letter-spacing: 0.13em;
    text-transform: uppercase;
    margin-bottom: 0.25rem;
}
.status-bi-tag-success { color: #16A34A; }
.status-bi-tag-error   { color: #DC2626; }
.status-bi-tag-loading { color: #0A66C2; }

.status-bi-title {
    font-size: 0.9rem;
    font-weight: 600;
    color: #1A2332;
    margin-bottom: 0.25rem;
}
.status-bi-msg {
    font-size: 0.8rem;
    color: #64748B;
    line-height: 1.55;
}
.status-bi-meta {
    font-size: 0.71rem;
    color: #94A3B8;
    margin-top: 0.45rem;
    font-family: 'JetBrains Mono', monospace;
}

/* ── Client record fields ─────────────────────────────────────────────────── */
.field-label {
    color: #94A3B8;
    font-size: 0.61rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    margin-bottom: 2px;
}
.field-value {
    color: #1A2332;
    font-size: 0.84rem;
    font-weight: 500;
    font-family: 'JetBrains Mono', monospace;
}

/* ── Client count tag ─────────────────────────────────────────────────────── */
.count-tag {
    display: inline-block;
    background: #EFF6FF;
    color: #0A66C2;
    font-size: 0.67rem;
    font-weight: 600;
    padding: 0.18rem 0.55rem;
    border-radius: 4px;
    margin-bottom: 1rem;
    letter-spacing: 0.04em;
}

/* ── Placeholder pages ────────────────────────────────────────────────────── */
.placeholder-box {
    background: #ffffff;
    border: 1.5px dashed #D1D9E0;
    border-radius: 7px;
    padding: 3.5rem 2rem;
    text-align: center;
    margin: 1.5rem auto;
    max-width: 460px;
}
.placeholder-title { color: #1A2332; font-size: 1rem; font-weight: 600; margin-bottom: 0.4rem; }
.placeholder-msg   { color: #94A3B8; font-size: 0.82rem; line-height: 1.5; }

/* ── Expander ─────────────────────────────────────────────────────────────── */
div[data-testid="stExpander"] {
    background: #ffffff !important;
    border: 1px solid #E8ECF0 !important;
    border-radius: 6px !important;
    margin-bottom: 0.5rem;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}

/* ── Primary button (general content area) ────────────────────────────────── */
div[data-testid="stButton"] > button[kind="primary"] {
    background: #0A66C2 !important;
    border: none !important;
    color: #ffffff !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    border-radius: 5px !important;
    padding: 0.45rem 1.25rem !important;
    transition: background 0.15s !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    background: #0858A8 !important;
}

/* ── Secondary button (general content area) ──────────────────────────────── */
div[data-testid="stButton"] > button:not([kind="primary"]) {
    background: #ffffff !important;
    border: 1px solid #D1D9E0 !important;
    color: #475569 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    border-radius: 5px !important;
    padding: 0.45rem 1.25rem !important;
    transition: all 0.15s !important;
}
div[data-testid="stButton"] > button:not([kind="primary"]):hover {
    border-color: #0A66C2 !important;
    color: #0A66C2 !important;
    background: #F0F7FF !important;
}

/* ── Sidebar button overrides — MUST come after general button rules ────────── */
[data-testid="stSidebar"] div[data-testid="stButton"] > button,
[data-testid="stSidebar"] div[data-testid="stButton"] > button:not([kind="primary"]) {
    width: 100% !important;
    background: transparent !important;
    border: none !important;
    border-left: 3px solid transparent !important;
    border-radius: 0 !important;
    color: rgba(255,255,255,0.5) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.8rem !important;
    font-weight: 400 !important;
    padding: 0.55rem 1.1rem !important;
    text-align: left !important;
    letter-spacing: 0.005em !important;
    transition: all 0.15s !important;
    min-height: unset !important;
    line-height: 1.4 !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover,
[data-testid="stSidebar"] div[data-testid="stButton"] > button:not([kind="primary"]):hover {
    background: rgba(255,255,255,0.05) !important;
    color: rgba(255,255,255,0.82) !important;
    border: none !important;
    border-left: 3px solid rgba(10,102,194,0.45) !important;
}

/* ── Inputs / selects ─────────────────────────────────────────────────────── */
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.85rem !important;
    border-radius: 5px !important;
}
div[data-baseweb="select"] {
    font-family: 'Inter', sans-serif !important;
    border-radius: 5px !important;
}

/* ── Divider ──────────────────────────────────────────────────────────────── */
hr { border: none; border-top: 1px solid #E8ECF0; margin: 1.25rem 0; }
</style>
""", unsafe_allow_html=True)
