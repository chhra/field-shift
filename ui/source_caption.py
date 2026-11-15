"""Render `source: <dataset>` captions under numbers."""

from __future__ import annotations

import streamlit as st

from ui.glossary import friendly_source


def source_caption(dataset: str, data_through: str | None = None) -> None:
    """Show a small muted source caption under a metric or chart value."""
    label = friendly_source(dataset)
    if data_through:
        st.caption(f"source: {label} · data through {data_through}")
    else:
        st.caption(f"source: {label}")
