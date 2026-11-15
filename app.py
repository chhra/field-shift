"""Field Shift — Streamlit entrypoint with top navigation (no sidebar)."""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Field Shift",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from ui.theme import inject_nav_active, inject_theme  # noqa: E402

inject_theme()

home = st.Page("views/home.py", title="Home", icon="🌾", default=True)
field = st.Page("views/field.py", title="Field", icon="🗺️", url_path="field")
how = st.Page(
    "views/how_it_works.py",
    title="How it works",
    icon="📖",
    url_path="how-it-works",
)

# No tab for the UK model: the Home demo and UK coordinates open it.
uk_model = st.Page(
    "views/uk_model.py",
    title="UK model",
    icon="🌱",
    url_path="uk-model",
)

pg = st.navigation([home, field, uk_model, how], position="hidden")

# Current page key for the green underline (url_path is "" on Home)
active_path = (getattr(pg, "url_path", None) or "") or ""
inject_nav_active(active_path)

# Single row: brand + tabs share one baseline
b, n1, n2, n3, _pad = st.columns([1.35, 0.7, 0.7, 1.2, 2.0], gap="small")
with b:
    st.markdown('<p class="fs-brand">Field Shift</p>', unsafe_allow_html=True)
with n1:
    st.page_link(home, label="Home", use_container_width=False)
with n2:
    st.page_link(field, label="Field", use_container_width=False)
with n3:
    st.page_link(how, label="How it works", use_container_width=False)

st.markdown('<div class="fs-topnav-rule" aria-hidden="true"></div>', unsafe_allow_html=True)

pg.run()
