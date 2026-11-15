"""Home view: NASA-style hero, demo fields, analyze-my-field."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st
from fieldshift.data.ee_client import init_ee
from fieldshift.geo import polygon_area_ha, polygon_from_point
from fieldshift.models import FieldConditions
from fieldshift.services import analyze_field, using_mock_data
from streamlit_folium import st_folium
from team_model.live_climate import in_uk
from ui.components import demo_field_cards, hero, section
from ui.map import field_map
from ui.mock_banner import show_mock_banner


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_analyze(polygon_json: str, name: str | None) -> FieldConditions:
    return analyze_field(json.loads(polygon_json), name=name)


status = init_ee()
live = bool(status.initialized and not status.demo_mode)

if using_mock_data():
    show_mock_banner()

hero(
    "Field Shift",
    "See what NASA satellites know about your field, and compare crop rotations "
    "that build soil and resilience.",
    sub="Decision support for farmers — supports, not replaces, your judgment.",
    mode_label="Live NASA data" if live else "Cached demo mode",
    live=live,
)

section(
    "Try the demo field",
    "Rothamsted Broadbalk — the world's longest-running field experiment, and the one "
    "field here with physical ground measurements: a rain gauge recording on this farm "
    "since 1853. Opens the UK rotation model, where NASA satellite rainfall is checked "
    "against that gauge.",
)
opened = demo_field_cards(
    [
        {
            "id": "broadbalk",
            "name": "Rothamsted Broadbalk",
            "climate": "Temperate oceanic — long-term experiment",
            "country": "United Kingdom · Harpenden",
            "rotation": "Winter wheat system",
            "thumb_path": None,
            "button_label": "Open the UK model",
        }
    ]
)
if opened:
    # Broadbalk card: clear any entered location so the model shows Rothamsted.
    st.session_state.pop("ukm_lat", None)
    st.session_state.pop("ukm_lon", None)
    st.switch_page("views/uk_model.py")

section(
    "Analyze my own field",
    "Draw a polygon, or enter coordinates — we’ll outline a field and map it for you.",
)
st.markdown(
    """
<div class="fs-home-steps">
  <div class="fs-home-step">
    <p class="fs-home-step-num">01 — Locate</p>
    <p class="fs-home-step-title">Find the field</p>
    <p class="fs-home-step-body">Draw on the map or enter lat/lon.</p>
  </div>
  <div class="fs-home-step">
    <p class="fs-home-step-num">02 — Describe</p>
    <p class="fs-home-step-title">Farm context</p>
    <p class="fs-home-step-body">Rotation, soil, water, priorities.</p>
  </div>
  <div class="fs-home-step">
    <p class="fs-home-step-num">03 — Compare</p>
    <p class="fs-home-step-title">See options</p>
    <p class="fs-home-step-body">Scored rotations with evidence.</p>
  </div>
</div>
    """,
    unsafe_allow_html=True,
)

locate = st.radio(
    "How do you want to locate the field?",
    ["Draw on map", "Enter coordinates"],
    horizontal=True,
    key="locate-mode",
)

drawn: dict[str, Any] | None = None
coord_poly: dict[str, Any] | None = None

if locate == "Enter coordinates":
    st.caption(
        "Enter the centre of your field. We build a square outline of the size you choose "
        "and show it on the map below."
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        lat = st.number_input(
            "Latitude",
            min_value=-90.0,
            max_value=90.0,
            value=52.205,
            step=0.001,
            format="%.5f",
            help="Degrees north (+) / south (−). Example: 52.205 for Cambridgeshire.",
            key="coord_lat",
        )
    with c2:
        lon = st.number_input(
            "Longitude",
            min_value=-180.0,
            max_value=180.0,
            value=0.085,
            step=0.001,
            format="%.5f",
            help="Degrees east (+) / west (−). Example: 0.085 near Cambridge, UK.",
            key="coord_lon",
        )
    with c3:
        size_ha = st.number_input(
            "Field size (ha)",
            min_value=1.0,
            max_value=5000.0,
            value=25.0,
            step=1.0,
            help="Approximate field area. We draw a square of this size around the point.",
            key="coord_size_ha",
        )

    coord_poly = polygon_from_point(float(lat), float(lon), float(size_ha))
    area = polygon_area_ha(coord_poly)
    st.markdown(
        f"**Field outline** · centre `{lat:.5f}, {lon:.5f}` · "
        f"≈ **{area:.1f} ha** square"
    )
    m = field_map(coord_poly, center=(float(lat), float(lon)), zoom=14, draw=False)
    st_folium(m, width=None, height=420, key=f"home-coords-{lat:.4f}-{lon:.4f}-{size_ha:.0f}")
    st.caption("Adjust the coordinates or size until the outline sits on your field.")
    if st.button(
        "Open the UK model for this location",
        type="primary",
        use_container_width=True,
        key="coords-to-ukm",
    ):
        if in_uk(float(lat), float(lon)):
            st.session_state["ukm_lat"] = float(lat)
            st.session_state["ukm_lon"] = float(lon)
            st.switch_page("views/uk_model.py")
        else:
            st.error(
                "The UK model only covers UK fields. Enter coordinates within the UK "
                "(roughly 49.5–61 °N, −8.7–2.1 °E)."
            )
else:
    m = field_map(draw=True, center=(42.0, -93.6), zoom=5)
    map_state = st_folium(m, width=None, height=400, key="home-draw")
    if map_state and map_state.get("last_active_drawing"):
        drawn = map_state["last_active_drawing"].get("geometry")
    if drawn:
        st.caption(
            f"Polygon captured · ≈ {polygon_area_ha(drawn):.1f} ha — ready to analyze."
        )

target_poly = coord_poly if locate == "Enter coordinates" else drawn
field_name = (
    f"Field @ {st.session_state.get('coord_lat', 0):.3f}, "
    f"{st.session_state.get('coord_lon', 0):.3f}"
    if locate == "Enter coordinates"
    else "Your field"
)

if not live:
    st.button("Live analysis unavailable (demo mode)", disabled=True)
else:
    ready = target_poly is not None
    label = (
        "Analyze field from coordinates"
        if locate == "Enter coordinates"
        else "Analyze drawn field"
    )
    clicked = st.button(label, disabled=not ready, type="primary")
    if clicked and target_poly is not None:
        try:
            progress = st.progress(0, text="Analyzing 10 years of NASA data (~60 s)")
            progress.progress(20, text="Querying Earth Engine & NASA POWER…")
            with st.spinner("Analyzing 10 years of NASA data (~60 s)"):
                conditions = _cached_analyze(
                    json.dumps(target_poly, sort_keys=True),
                    field_name,
                )
            progress.progress(100, text="Analysis complete")
            st.session_state["field_id"] = "custom"
            st.session_state["field_polygon"] = target_poly
            st.session_state["custom_conditions"] = conditions
            st.session_state["_rotation_field"] = "custom"
            st.session_state["current_rotation"] = ["maize", "soybean"]
            st.success("Opening your field report.")
            st.switch_page("views/field.py")
        except ValueError as exc:
            st.error(str(exc))
        except RuntimeError as exc:
            st.error(str(exc))
        except Exception as exc:  # noqa: BLE001
            st.error(
                f"Earth Engine / POWER analysis failed: {exc}. "
                "Check credentials and try a smaller cropland area."
            )
