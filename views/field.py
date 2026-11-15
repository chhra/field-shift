"""Field view: numbered advisory-report story."""

from __future__ import annotations

import html
import io
from pathlib import Path

import streamlit as st
from fieldshift.cache import read_json
from fieldshift.engine.candidates import season_label
from fieldshift.engine.inputs_config import (
    DEMO_FARM_ANSWERS,
    MONTH_SHIFT_DATA_GAP_THRESHOLD,
    QUESTIONS,
    SOIL_HELP,
    SOIL_TILES,
    WATER_HELP,
    WATER_TILES,
    default_goal_order,
    rank_goal_weights,
    resolve_soil_category,
    resolve_water_access,
)
from fieldshift.engine.slots import crops_for_slot
from fieldshift.engine.tiers import recommendation_sentence
from fieldshift.geo import polygon_area_ha
from fieldshift.models import (
    FieldConditions,
    GoalImportanceSet,
    PriorityWeights,
    ScenarioParams,
    StrategyRequest,
)
from fieldshift.services import (
    demo_data_through,
    generate_strategies,
    get_timelapse,
    get_validation,
    load_demo_conditions,
    load_field_features,
    using_mock_data,
)
from PIL import Image
from streamlit_folium import st_folium
from ui.charts import conditions_figure, conditions_takeaway
from ui.components import (
    fact_chips,
    question,
    recommendation_banner,
    section,
)
from ui.explainers import FACT_HELP, chart_how_to_read
from ui.goal_rank import goal_ranking
from ui.map import field_map
from ui.mock_banner import show_mock_banner
from ui.source_caption import source_caption
from ui.strategy_cards import render_strategy_cards
from ui.year_strip import (
    is_cover_crop,
    month_range,
    months_from_text,
    rows_from_crops,
    year_strip_html,
)

_DEFAULT_ROTATION = {
    "iowa": ["maize", "soybean"],
    "uk": ["winter_wheat"],
    "punjab": ["rice", "winter_wheat"],
    "custom": ["maize", "soybean"],
}
# Fills extra "Crop N" slots when the farmer raises the count.
_TYPICAL_CROPS = {
    "iowa": ["maize", "soybean", "winter_wheat", "oats", "alfalfa", "red_clover"],
    "uk": ["winter_wheat", "barley", "canola", "field_pea", "oats", "spring_wheat"],
    "punjab": ["rice", "winter_wheat", "mung_bean", "maize", "cotton", "lentil"],
    "custom": ["maize", "soybean", "winter_wheat", "oats", "alfalfa", "red_clover"],
}
_DEFAULT_WATER = {
    "iowa": "rainfed",
    "uk": "rainfed",
    "punjab": "irrigated",
    "custom": "rainfed",
}
_MONTHS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_conditions(field_id: str) -> FieldConditions:
    return load_demo_conditions(field_id)


@st.cache_data(show_spinner=False)
def _cached_demo_conditions_figure(field_id: str, theme_ver: str = "design-v1") -> object:
    """Seasonal chart for demo fields — skip rebuild on unrelated widget reruns."""
    _ = theme_ver
    return conditions_figure(load_demo_conditions(field_id))


@st.cache_data(show_spinner=False)
def _gif_png_frames(path: str) -> list[bytes]:
    im = Image.open(path)
    out: list[bytes] = []
    for i in range(getattr(im, "n_frames", 1)):
        im.seek(i)
        buf = io.BytesIO()
        im.convert("RGB").save(buf, format="PNG")
        out.append(buf.getvalue())
    return out


def _demo_payload(field_id: str) -> dict:
    return read_json(f"demo_{field_id}.json", from_mock=False) or {}


if using_mock_data():
    show_mock_banner()

field_id = st.session_state.get("field_id", "iowa")
if field_id == "custom" and st.session_state.get("custom_conditions"):
    conditions = st.session_state["custom_conditions"]
else:
    try:
        conditions = _cached_conditions(field_id)
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.stop()

if (
    "current_rotation" not in st.session_state
    or st.session_state.get("_rotation_field") != field_id
):
    st.session_state["current_rotation"] = list(
        _DEFAULT_ROTATION.get(field_id, ["maize", "soybean"])
    )
    st.session_state["_rotation_field"] = field_id
_demo0 = DEMO_FARM_ANSWERS.get(field_id) or DEMO_FARM_ANSWERS["iowa"]
st.session_state.setdefault("water_category", _demo0["water_category"])
st.session_state.setdefault("soil_category", _demo0["soil_category"])
st.session_state.setdefault("rain_mult", 1.0)
st.session_state.setdefault("temp_offset", 0.0)

payload = _demo_payload(field_id)
ndvi_through = demo_data_through(field_id, "ndvi_s2")
rain_through = demo_data_through(field_id, "rain_best_mm")
grace_through = demo_data_through(field_id, "grace_lwe_cm")
power_through = demo_data_through(field_id, "power_t2m_c")
feat = conditions.features
grace = (payload.get("coverage") or {}).get("grace_trend") or {}
grace_cm = grace.get("trend_cm_per_yr")
grace_label = (
    f"{grace_cm:+.1f} cm/yr" if grace_cm is not None else (grace.get("detail") or "—")
)

st.markdown(
    '<p class="fs-eyebrow">FIELD REPORT</p>',
    unsafe_allow_html=True,
)
st.title(conditions.name)
st.caption(f"{conditions.climate_label} · {conditions.country or 'Custom field'}")

# --- 1. Your field (fragment: NDVI/RGB toggles must not re-run the whole page) ---
def _imagery_block() -> None:
    section(
        "Your field",
        "Satellite basemap with your polygon, plus a Sentinel-2 monthly timelapse.",
        step=1,
    )
    c_map, c_tl = st.columns([1, 1], gap="large")
    with c_map:
        fmap = field_map(conditions.polygon)
        # Display-only map — skip returning draw state (much faster on reruns).
        st_folium(
            fmap,
            height=360,
            use_container_width=True,
            key=f"field-map-{field_id}",
            returned_objects=[],
        )
    with c_tl:
        mode = st.radio(
            "Imagery product",
            ["ndvi", "rgb"],
            format_func=lambda x: (
                "Plant greenness (NDVI)" if x == "ndvi" else "True color (RGB)"
            ),
            horizontal=True,
            key=f"tl-mode-{field_id}",
        )
        play = st.toggle("Autoplay GIF", value=True, key=f"tl-play-{field_id}")
        tl = get_timelapse(field_id, index=mode)
        if tl.get("path") and Path(tl["path"]).exists():
            if play:
                # Autoplay uses the GIF as-is — do not decode every frame.
                st.image(tl["path"], use_container_width=True)
                st.caption("Autoplay · monthly cloud-masked composites")
            else:
                frames = _gif_png_frames(tl["path"])
                idx = st.slider(
                    "Month frame",
                    0,
                    max(0, len(frames) - 1),
                    min(7, max(0, len(frames) - 1)),
                    key=f"tl-slider-{field_id}-{mode}",
                )
                st.image(frames[idx], use_container_width=True)
                st.caption(
                    "Scrub months manually — labels are burned into each frame"
                )
            source_caption(
                "Sentinel-2 NDVI" if mode == "ndvi" else "Sentinel-2 RGB",
                ndvi_through,
            )
        else:
            st.info(tl.get("message", "Timelapse not available yet."))


if hasattr(st, "fragment"):

    @st.fragment  # type: ignore[attr-defined]
    def imagery_fragment() -> None:
        _imagery_block()

    imagery_fragment()
else:
    _imagery_block()

# --- 2. What the satellites see ---
section(
    "What the satellites see",
    "Key facts first, then the seasonal pattern across a typical year.",
    step=2,
)
if feat.frost_free_days:
    frost_value = f"{feat.frost_free_days:.0f} days"
elif conditions.climate_label and "subtropical" in conditions.climate_label.lower():
    frost_value = "Rarely frosts"
else:
    frost_value = "Not estimated yet"

chips = [
    {
        "label": "Bare soil window",
        "value": feat.bare_months_label.split("(")[0].strip()
        if feat.bare_months_label
        else "Not estimated yet",
        "meaning": FACT_HELP["bare"],
        "help": (
            f"source: Sentinel-2 plant greenness · data through "
            f"{ndvi_through or 'latest available'}"
        ),
    },
    {
        "label": "Frost-free days",
        "value": frost_value,
        "meaning": FACT_HELP["frost"],
        "help": (
            f"source: NASA POWER temperature · data through "
            f"{power_through or 'latest available'}"
        ),
    },
    {
        "label": "Rain (mm/yr)",
        "value": f"≈ {feat.rain_annual_mm:.0f} mm"
        if feat.rain_annual_mm
        else "Not estimated yet",
        "meaning": FACT_HELP["rain"],
        "help": (
            f"source: Best available rainfall · data through "
            f"{rain_through or 'latest available'}"
        ),
    },
    {
        "label": "Regional water storage",
        "value": grace_label if grace_label and grace_label != "—" else "Not estimated yet",
        "meaning": FACT_HELP["grace"],
        "help": (
            f"source: GRACE water storage · data through "
            f"{grace_through or 'latest available'}"
        ),
    },
]
fact_chips(chips)

with st.expander("How to read this chart", expanded=False):
    st.markdown(chart_how_to_read())

st.markdown(
    f'<p class="fs-chart-takeaway">{conditions_takeaway(conditions)}</p>',
    unsafe_allow_html=True,
)
_chart = (
    conditions_figure(conditions)
    if field_id == "custom"
    else _cached_demo_conditions_figure(field_id)
)
st.plotly_chart(
    _chart,
    use_container_width=True,
    config={"displayModeBar": False},
    key=f"conditions-chart-{field_id}",
)
st.caption(
    "Plant greenness (line) · Rain mm (bars) · Water balance (dashed). "
    "Tan shade ≈ usually bare · light red ≈ growing-season stress."
)
source_caption(
    "Sentinel-2 / SMAP / Best available rainfall / water balance",
    rain_through,
)

anoms = payload.get("anomalies") or {}
with st.expander("Stress & anomalies (SI model)"):
    vulns = anoms.get("vulnerable_seasons") or []
    if vulns:
        for v in vulns:
            m = v.get("calendar_month")
            label = _MONTHS[m - 1] if isinstance(m, int) and 1 <= m <= 12 else m
            st.write(
                f"• Calendar month **{label}** flagged "
                f"{v.get('n_flags', 1)}× in the record"
            )
    else:
        st.write("No recurring growing-season anomaly months in the SI output.")
    st.caption(feat.stress_months_label)
    if anoms.get("uncertainty"):
        st.info(anoms["uncertainty"])
    source_caption("IsolationForest SI model", ndvi_through)

# --- 3–5. Farm inputs + options (one fragment: a click re-scores cards,
# it does not rebuild the map, timelapse or seasonal chart above) ---
def _farm_block() -> None:
    # --- 3. About your farm ---
    section(
        "About your farm",
        "Five quick questions. Satellites filled in what they could; change anything "
        "that is wrong.",
        step=3,
    )


    demo_answers = DEMO_FARM_ANSWERS.get(field_id) or DEMO_FARM_ANSWERS["iowa"]
    if st.session_state.get("_farm_inputs_field") != field_id:
        st.session_state["_farm_inputs_field"] = field_id
        st.session_state["water_category"] = demo_answers["water_category"]
        st.session_state["soil_category"] = demo_answers["soil_category"]
        st.session_state[f"goal-order-{field_id}"] = default_goal_order(
            demo_answers["goals"]
        )
        st.session_state["_demo_banner"] = demo_answers["label"]

    if st.session_state.get("_demo_banner") and field_id in DEMO_FARM_ANSWERS:
        st.markdown(
            f'<p class="fs-farm-banner">Starting from <strong>'
            f'{st.session_state["_demo_banner"]}</strong> — change anything that '
            f"does not match your farm.</p>",
            unsafe_allow_html=True,
        )

    try:
        engine_feats = load_field_features(
            field_id, current_rotation=st.session_state["current_rotation"]
        )
    except FileNotFoundError:
        engine_feats = {}

    question(1, *QUESTIONS["field"])
    try:
        area = f", about {polygon_area_ha(conditions.polygon):.0f} ha"
    except Exception:
        area = ""
    st.markdown(
        f'<p class="fs-farm-confirm"><span class="fs-tick" aria-hidden="true">✓</span>'
        f"<span>Satellites are watching <strong>{html.escape(conditions.name)}</strong>"
        f"{area}</span></p>",
        unsafe_allow_html=True,
    )

    question(2, *QUESTIONS["crops"])

    preferred = list(st.session_state["current_rotation"]) or list(
        _DEFAULT_ROTATION.get(field_id, ["maize", "soybean"])
    )
    prev_cash = [c for c in preferred if not is_cover_crop(c)] or ["maize"]
    prev_cover = next((c for c in preferred if is_cover_crop(c)), None)

    count_key = f"ncrops-{field_id}"
    if count_key not in st.session_state:
        st.session_state[count_key] = min(6, len(prev_cash))
    n_crops = st.radio(
        "How many crops are in your rotation?",
        [1, 2, 3, 4, 5, 6],
        horizontal=True,
        key=count_key,
        help=(
            "Count each main crop once, in the order you grow them. "
            "Leave cover crops out: there is a separate picker below."
        ),
    )

    cash_options = [
        o
        for o in crops_for_slot({"kind": "cash"}, engine_feats, always_allow=prev_cash)
        if o["enabled"]
    ]
    cash_ids = [o["id"] for o in cash_options]
    crop_names = {o["id"]: o["name"] for o in cash_options}
    fill_order = [
        c for c in _TYPICAL_CROPS.get(field_id, []) + cash_ids if c in cash_ids
    ]
    cash_rot: list[str] = []
    crop_cols = st.columns(min(3, n_crops))
    for i in range(n_crops):
        if i < len(prev_cash) and prev_cash[i] in cash_ids:
            default = prev_cash[i]
        else:
            taken = cash_rot + prev_cash[:n_crops]
            default = next((c for c in fill_order if c not in taken), cash_ids[0])
        with crop_cols[i % len(crop_cols)]:
            cash_rot.append(
                st.selectbox(
                    f"Crop {i + 1}",
                    cash_ids,
                    index=cash_ids.index(default),
                    format_func=lambda c: crop_names.get(c, c),
                    key=f"crop-{field_id}-{i}",
                )
            )

    try:
        feats_now = load_field_features(field_id, current_rotation=cash_rot)
    except FileNotFoundError:
        feats_now = engine_feats
    fallow = list(
        (feats_now.get("phenology") or {}).get("fallow_months")
        or (feats_now.get("bare_months") or {}).get("months")
        or []
    )
    cover_options = [
        o
        for o in crops_for_slot(
            {"kind": "cover", "months": fallow},
            feats_now,
            always_allow=[prev_cover] if prev_cover else [],
        )
        if o["enabled"]
    ]
    cover_ids = ["(none)"] + [o["id"] for o in cover_options]
    cover_names = {o["id"]: o["name"] for o in cover_options}
    cover_col, _ = st.columns([1, 2])
    with cover_col:
        cover_pick = st.selectbox(
            "Cover crop in the bare months",
            cover_ids,
            index=cover_ids.index(prev_cover) if prev_cover in cover_ids else 0,
            format_func=lambda c: "No cover crop" if c == "(none)" else cover_names.get(c, c),
            key=f"cover-{field_id}",
            help="Optional. Pick one only if you sow something while the field would be bare.",
        )
    cover_crop = None if cover_pick == "(none)" else cover_pick

    plant_overrides: dict[str, int] = {}
    harvest_overrides: dict[str, int] = {}
    month_gaps: list[str] = []
    calendar_items: list[tuple[str, list[int]]] = []
    with st.expander("Adjust planting or harvest months", expanded=False):
        st.caption("Satellites suggest these months. Change them only if they are wrong.")
        for i, crop in enumerate(cash_rot):
            detected = months_from_text(season_label(crop, feats_now)) or list(range(5, 11))
            det_plant, det_harvest = detected[0], detected[-1]
            c_name, c_plant, c_harvest = st.columns([1.2, 1, 1])
            c_name.markdown(f"**{i + 1}. {crop_names.get(crop, crop)}**")
            plant = c_plant.selectbox(
                "Plant",
                list(range(1, 13)),
                index=det_plant - 1,
                format_func=lambda m: _MONTHS[m - 1],
                key=f"plant-{field_id}-{i}-{crop}",
            )
            harvest = c_harvest.selectbox(
                "Harvest",
                list(range(1, 13)),
                index=det_harvest - 1,
                format_func=lambda m: _MONTHS[m - 1],
                key=f"harvest-{field_id}-{i}-{crop}",
            )
            name = crop_names.get(crop, crop)
            if abs(int(plant) - det_plant) > MONTH_SHIFT_DATA_GAP_THRESHOLD:
                month_gaps.append(
                    f"Planting month for {name} moved >"
                    f"{MONTH_SHIFT_DATA_GAP_THRESHOLD} month from satellite detection"
                )
                plant_overrides[crop] = int(plant)
            if abs(int(harvest) - det_harvest) > MONTH_SHIFT_DATA_GAP_THRESHOLD:
                month_gaps.append(
                    f"Harvest month for {name} moved >"
                    f"{MONTH_SHIFT_DATA_GAP_THRESHOLD} month from satellite detection"
                )
                harvest_overrides[crop] = int(harvest)
            calendar_items.append((crop, month_range(int(plant), int(harvest))))
    if cover_crop:
        calendar_items.append((cover_crop, fallow))

    new_rot = cash_rot + ([cover_crop] if cover_crop else [])
    st.session_state["current_rotation"] = new_rot

    st.markdown(
        '<p class="fs-year-title">Your farming year</p>'
        + year_strip_html(rows_from_crops(calendar_items), legend=True),
        unsafe_allow_html=True,
    )

    question(3, *QUESTIONS["water"])
    water_keys = list(WATER_TILES.keys())
    st.session_state["water_category"] = st.radio(
        "Water source",
        water_keys,
        index=water_keys.index(st.session_state.get("water_category", "rain_only")),
        format_func=lambda k: WATER_TILES[k],
        horizontal=True,
        key=f"water-cat-{field_id}",
        help=WATER_HELP,
        label_visibility="collapsed",
    )

    question(4, *QUESTIONS["soil"])
    soil_keys = list(SOIL_TILES.keys())
    st.session_state["soil_category"] = st.radio(
        "Soil type",
        soil_keys,
        index=soil_keys.index(st.session_state.get("soil_category", "loamy")),
        format_func=lambda k: SOIL_TILES[k],
        horizontal=True,
        key=f"soil-cat-{field_id}",
        help=SOIL_HELP,
        label_visibility="collapsed",
    )

    question(5, *QUESTIONS["goals"])
    order = goal_ranking(field_id, default_goal_order(demo_answers["goals"]))
    weights_map, goal_importance, equal_note = rank_goal_weights(order)

    water_access, water_gaps = resolve_water_access(st.session_state["water_category"])
    soil_type, _awc, _inf, soil_gaps = resolve_soil_category(
        st.session_state["soil_category"]
    )
    input_gaps = water_gaps + soil_gaps + month_gaps
    if field_id in DEMO_FARM_ANSWERS:
        input_gaps.append(DEMO_FARM_ANSWERS[field_id]["label"])
    input_penalty = bool(water_gaps or soil_gaps)

    # --- 4 climate + 5 options ---
    def _options_block() -> None:
        section(
            "What if the weather changes?",
            "Optional, and not a forecast: see which options still hold up if rain "
            "or heat shifted.",
            step=4,
        )
        rain_opts = [
            (":material/rainy_light: Drier, −20%", 0.8),
            ("As now", 1.0),
            (":material/rainy_heavy: Wetter, +20%", 1.2),
        ]
        temp_opts = [
            ("As now", 0.0),
            (":material/thermometer: +1 °C", 1.0),
            (":material/thermometer_add: +2 °C", 2.0),
        ]
        rain_labels = [r[0] for r in rain_opts]
        temp_labels = [t[0] for t in temp_opts]
        c_rain, c_temp = st.columns(2)
        with c_rain:
            question(None, "If yearly rain changed")
            rain_pick = st.radio(
                "Rainfall",
                rain_labels,
                index=1,
                horizontal=True,
                key=f"rain-cat-{field_id}",
                help="Example: Drier means about one-fifth less rain than a typical year here.",
                label_visibility="collapsed",
            )
            st.session_state["rain_mult"] = dict(rain_opts)[rain_pick]
        with c_temp:
            question(None, "If seasons ran warmer")
            temp_pick = st.radio(
                "Temperature",
                temp_labels,
                index=0,
                horizontal=True,
                key=f"temp-cat-{field_id}",
                help="Example: +2 °C means warmer seasons on top of today’s climate.",
                label_visibility="collapsed",
            )
            st.session_state["temp_offset"] = dict(temp_opts)[temp_pick]

        climate_shifted = (
            abs(float(st.session_state["rain_mult"]) - 1.0) > 1e-6
            or float(st.session_state["temp_offset"]) > 1e-6
        )

        section(
            "Your options",
            "Each option shows its farming year and the same six goal scores.",
            step=5,
        )
        req = StrategyRequest(
            current_rotation=st.session_state["current_rotation"],
            water_category=st.session_state["water_category"],
            soil_category=st.session_state["soil_category"],
            soil_type=soil_type,  # type: ignore[arg-type]
            water_access=water_access,  # type: ignore[arg-type]
            goal_importance=GoalImportanceSet(**goal_importance),
            weights=PriorityWeights(**weights_map),
            scenario=ScenarioParams(
                rain_mult=float(st.session_state["rain_mult"]),
                temp_offset=float(st.session_state["temp_offset"]),
            ),
            plant_month_overrides=plant_overrides,
            harvest_month_overrides=harvest_overrides,
            input_data_gaps=input_gaps,
            input_confidence_penalty=input_penalty,
            equal_weights_note=equal_note,
        )
        result = generate_strategies(field_id, req)
        cards = result.strategies
        if cards:
            recommendation_banner(recommendation_sentence(cards))
            render_strategy_cards(cards, show_climate_delta=climate_shifted)


    _options_block()


if hasattr(st, "fragment"):
    st.fragment(_farm_block)()  # type: ignore[attr-defined]
else:
    _farm_block()

# --- 6. Reliability ---
section(
    "How reliable is this?",
    "Where the numbers come from, and where human judgment still matters.",
    step=6,
)

val = get_validation(field_id)
through = payload.get("data_through") or {}
if through:
    lines = [
        f"- **{k}**: data through {v}"
        for k, v in list(through.items())[:8]
    ]
    st.markdown("**Dataset coverage**\n\n" + "\n".join(lines))
cc = None
if val.cross_checks:
    cc = val.cross_checks.get("imerg_vs_power_rain")
elif payload.get("cross_checks"):
    cc = payload["cross_checks"].get("imerg_vs_power_rain")
if cc and cc.get("r") is not None:
    st.write(
        f"Cross-check: IMERG vs POWER monthly rain **r = {cc['r']:.2f}** "
        f"(n = {cc.get('n_months', '—')} months)."
    )
    source_caption("IMERG + NASA POWER", rain_through)
st.info(
    "This tool **supports, not replaces**, your judgment and local expertise. "
    "Confidence badges reflect data coverage and SI uncertainty — not yield guarantees."
)
st.caption(
    "NASA & partners: Sentinel-2 (ESA/Copernicus), SMAP, IMERG, POWER, ERA5-Land, "
    "GRACE/FO, SRTM. Field Shift · NASA Space Apps 2026."
)
