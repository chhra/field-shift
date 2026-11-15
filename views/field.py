"""Field view: numbered advisory-report story."""

from __future__ import annotations

import io
from pathlib import Path

import streamlit as st
from fieldshift.cache import read_json
from fieldshift.engine.inputs_config import (
    CROPS_CONFIRM_HINT,
    CROPS_WHY,
    DEMO_FARM_ANSWERS,
    FIELD_CONFIRM_HINT,
    GOAL_HINTS,
    GOAL_KEYS,
    GOAL_LABELS,
    GOAL_PLAIN,
    GOALS_HINT,
    GOALS_WHY,
    IMPORTANCE_LABELS,
    MONTH_SHIFT_DATA_GAP_THRESHOLD,
    MONTHS_EXPANDER_LABEL,
    SOIL_HELP,
    SOIL_HINT,
    SOIL_LABELS,
    SOIL_WHY,
    TWO_YEAR_HELP,
    TWO_YEAR_LABEL,
    WATER_HELP,
    WATER_HINT,
    WATER_LABELS,
    WATER_WHY,
    normalize_goal_weights,
    resolve_soil_category,
    resolve_water_access,
)
from fieldshift.engine.slots import (
    crops_for_slot,
    default_rotation_for_slots,
    rotation_slots_from_features,
)
from fieldshift.engine.tiers import recommendation_sentence
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
    recommendation_banner,
    section,
    weights_bar,
)
from ui.explainers import FACT_HELP, chart_how_to_read
from ui.map import field_map
from ui.mock_banner import show_mock_banner
from ui.source_caption import source_caption
from ui.strategy_cards import render_strategy_cards

_DEFAULT_ROTATION = {
    "iowa": ["maize", "soybean"],
    "uk": ["winter_wheat"],
    "punjab": ["rice", "winter_wheat"],
    "custom": ["maize", "soybean"],
}
_DEFAULT_WATER = {
    "iowa": "rainfed",
    "uk": "rainfed",
    "punjab": "irrigated",
    "custom": "rainfed",
}
# Iowa maize→soy share one summer season → need a 2-year cycle.
# Punjab rice→wheat fill two seasons in one year → cycle_years=1.
_DEFAULT_CYCLE = {
    "iowa": 2,
    "uk": 1,
    "punjab": 1,
    "custom": 2,
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

# --- 3. About your farm ---
section(
    "About your farm",
    "Answer five short questions. Satellites already filled what they can — you confirm.",
    step=3,
)


demo_answers = DEMO_FARM_ANSWERS.get(field_id) or DEMO_FARM_ANSWERS["iowa"]
if st.session_state.get("_farm_inputs_field") != field_id:
    st.session_state["_farm_inputs_field"] = field_id
    st.session_state["water_category"] = demo_answers["water_category"]
    st.session_state["soil_category"] = demo_answers["soil_category"]
    st.session_state["cycle_years"] = int(_DEFAULT_CYCLE.get(field_id, 1))
    st.session_state[f"two-year-{field_id}"] = (
        int(_DEFAULT_CYCLE.get(field_id, 1)) == 2
    )
    for gk, gv in demo_answers["goals"].items():
        st.session_state[f"goal-{field_id}-{gk}"] = int(gv)
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

st.markdown(
    '<p class="fs-farm-step">1 · Your field</p>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<p class="fs-farm-q">{FIELD_CONFIRM_HINT}</p>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<p class="fs-farm-confirm">Watching: <strong>{conditions.name}</strong></p>',
    unsafe_allow_html=True,
)

st.markdown(
    '<p class="fs-farm-step">2 · What you grow now</p>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<p class="fs-farm-q">{CROPS_CONFIRM_HINT}</p>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<p class="fs-farm-why">{CROPS_WHY}</p>',
    unsafe_allow_html=True,
)

if f"two-year-{field_id}" not in st.session_state:
    st.session_state[f"two-year-{field_id}"] = (
        int(_DEFAULT_CYCLE.get(field_id, 1)) == 2
    )
two_year = st.checkbox(
    TWO_YEAR_LABEL,
    key=f"two-year-{field_id}",
    help=TWO_YEAR_HELP,
)
st.session_state["cycle_years"] = 2 if two_year else 1

slots = rotation_slots_from_features(
    engine_feats,
    max_cash=4,
    cycle_years=int(st.session_state["cycle_years"]),
)
preferred = list(st.session_state["current_rotation"]) or list(
    _DEFAULT_ROTATION.get(field_id, ["maize", "soybean"])
)
cash_slots = [s for s in slots if s.get("kind") == "cash"]
cover_slots = [s for s in slots if s.get("kind") == "cover"]
default_cash = default_rotation_for_slots(slots, preferred)
prev_covers = [c for c in preferred if c not in default_cash]
new_rot: list[str] = []
plant_overrides: dict[str, int] = {}
harvest_overrides: dict[str, int] = {}
month_gaps: list[str] = []
# One cover picker is enough — the bare window repeats each year.
cover_ui = cover_slots[:1]
if cover_ui:
    cover_ui[0] = {
        **cover_ui[0],
        "id": "cover_shared",
        "label": "Cover in bare window",
    }
all_slots = cash_slots + cover_ui
n_slot_cols = max(1, min(3, len(all_slots) or 1))
slot_cols = st.columns(n_slot_cols)
for i, slot in enumerate(all_slots):
    with slot_cols[i % len(slot_cols)]:
        options = crops_for_slot(slot, engine_feats, always_allow=preferred)
        enabled = [o for o in options if o["enabled"]]
        disabled_ids = {o["id"] for o in options if not o["enabled"]}
        labels = {
            o["id"]: (o["name"] if o["enabled"] else f"{o['name']} — {o['reason']}")
            for o in options
        }
        months = list(slot.get("months") or [])
        det_plant = int(months[0]) if months else 5
        det_harvest = int(months[-1]) if months else 10
        span = (
            f"{_MONTHS[det_plant - 1]}–{_MONTHS[det_harvest - 1]}"
            if months
            else "season from satellites"
        )
        kind_note = (
            "Bare window — optional cover crop"
            if slot.get("kind") == "cover"
            else f"Growing season · usually {span}"
        )
        st.markdown(
            f'<p class="fs-farm-slot-label"><strong>{slot["label"]}</strong>'
            f'<span class="fs-farm-slot-meta">{kind_note}</span></p>',
            unsafe_allow_html=True,
        )
        if slot.get("kind") == "cover":
            choices = ["(none)"] + [o["id"] for o in options]
            default_cover = next(
                (c for c in prev_covers if c in {o["id"] for o in enabled}),
                "(none)",
            )
            pick = st.selectbox(
                f"Crop for {slot['label']}",
                choices,
                index=choices.index(default_cover) if default_cover in choices else 0,
                format_func=lambda x, _l=labels: (
                    "No cover crop" if x == "(none)" else _l.get(x, x)
                ),
                key=f"slot-{field_id}-{slot['id']}",
                help=(
                    "Leave as “No cover crop” if the ground stays bare. "
                    "Pick a cover if you plant something in this empty window."
                ),
                label_visibility="collapsed",
            )
            if pick != "(none)" and pick not in disabled_ids:
                new_rot.append(pick)
        else:
            enabled_ids = [o["id"] for o in enabled] or [
                default_cash[min(i, len(default_cash) - 1)]
            ]
            cash_idx = sum(1 for s in all_slots[:i] if s.get("kind") == "cash")
            pref = (
                default_cash[cash_idx]
                if cash_idx < len(default_cash)
                else enabled_ids[0]
            )
            if pref not in enabled_ids:
                pref = enabled_ids[0]
            pick = st.selectbox(
                f"Is this the right crop for {slot['label']}?",
                enabled_ids + sorted(disabled_ids),
                index=enabled_ids.index(pref),
                format_func=lambda x, _l=labels: _l.get(x, x),
                key=f"slot-{field_id}-{slot['id']}",
                help=(
                    f"Satellites see green cover around {span}. "
                    "Change the crop only if that is not what you grow."
                ),
                label_visibility="collapsed",
            )
            if pick in disabled_ids:
                pick = pref
            new_rot.append(pick)

        plant = det_plant
        harvest = det_harvest
        with st.expander(MONTHS_EXPANDER_LABEL, expanded=False):
            st.caption(
                f"Satellites suggest plant {_MONTHS[det_plant - 1]}, "
                f"harvest {_MONTHS[det_harvest - 1]}. Change only if wrong."
            )
            m1, m2 = st.columns(2)
            with m1:
                plant = st.selectbox(
                    "When do you plant?",
                    list(range(1, 13)),
                    index=det_plant - 1,
                    format_func=lambda m: _MONTHS[m - 1],
                    key=f"plant-{field_id}-{slot['id']}",
                    help="Example: satellites show May but you plant in April.",
                )
            with m2:
                harvest = st.selectbox(
                    "When do you harvest?",
                    list(range(1, 13)),
                    index=det_harvest - 1,
                    format_func=lambda m: _MONTHS[m - 1],
                    key=f"harvest-{field_id}-{slot['id']}",
                    help="Example: you harvest in September instead of October.",
                )
        if abs(int(plant) - det_plant) > MONTH_SHIFT_DATA_GAP_THRESHOLD:
            month_gaps.append(
                f"Planting month for {slot['label']} moved >"
                f"{MONTH_SHIFT_DATA_GAP_THRESHOLD} month from satellite detection"
            )
            if new_rot:
                plant_overrides[new_rot[-1]] = int(plant)
        if abs(int(harvest) - det_harvest) > MONTH_SHIFT_DATA_GAP_THRESHOLD:
            month_gaps.append(
                f"Harvest month for {slot['label']} moved >"
                f"{MONTH_SHIFT_DATA_GAP_THRESHOLD} month from satellite detection"
            )
            if new_rot:
                harvest_overrides[new_rot[-1]] = int(harvest)

if not new_rot:
    new_rot = list(default_cash)
st.session_state["current_rotation"] = new_rot

st.markdown(
    '<p class="fs-farm-step">3 · Where your water comes from</p>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<p class="fs-farm-q">{WATER_HINT}</p>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<p class="fs-farm-why">{WATER_WHY}</p>',
    unsafe_allow_html=True,
)
water_keys = list(WATER_LABELS.keys())
st.session_state["water_category"] = st.radio(
    "Water source",
    water_keys,
    index=water_keys.index(st.session_state.get("water_category", "rain_only")),
    format_func=lambda k: WATER_LABELS[k],
    horizontal=True,
    key=f"water-cat-{field_id}",
    help=WATER_HELP,
    label_visibility="collapsed",
)

st.markdown(
    '<p class="fs-farm-step">4 · Your soil type</p>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<p class="fs-farm-q">{SOIL_HINT}</p>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<p class="fs-farm-why">{SOIL_WHY}</p>',
    unsafe_allow_html=True,
)
soil_keys = list(SOIL_LABELS.keys())
st.session_state["soil_category"] = st.radio(
    "Soil type",
    soil_keys,
    index=soil_keys.index(st.session_state.get("soil_category", "loamy")),
    format_func=lambda k: SOIL_LABELS[k],
    horizontal=True,
    key=f"soil-cat-{field_id}",
    help=SOIL_HELP,
    label_visibility="collapsed",
)

st.markdown(
    '<p class="fs-farm-step">5 · What matters to you</p>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<p class="fs-farm-q">{GOALS_HINT}</p>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<p class="fs-farm-why">{GOALS_WHY}</p>',
    unsafe_allow_html=True,
)
goal_importance: dict[str, int] = {}
gcols = st.columns(2)
for i, gk in enumerate(GOAL_KEYS):
    with gcols[i % 2]:
        st.markdown(
            f'<p class="fs-farm-goal-name">{GOAL_LABELS[gk]}</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<p class="fs-farm-q">{GOAL_HINTS[gk]}</p>',
            unsafe_allow_html=True,
        )
        if f"goal-{field_id}-{gk}" not in st.session_state:
            st.session_state[f"goal-{field_id}-{gk}"] = int(
                demo_answers["goals"].get(gk, 1)
            )
        goal_importance[gk] = st.radio(
            GOAL_LABELS[gk],
            [0, 1, 2],
            format_func=lambda v: IMPORTANCE_LABELS[int(v)],
            horizontal=True,
            key=f"goal-{field_id}-{gk}",
            help=f"{GOAL_HINTS[gk]} {GOAL_PLAIN[gk]}",
            label_visibility="collapsed",
        )
        st.markdown(
            f'<p class="fs-farm-why">{GOAL_PLAIN[gk]}</p>',
            unsafe_allow_html=True,
        )

weights_map, equal_note = normalize_goal_weights(goal_importance)
if equal_note:
    st.info(equal_note)
weights_bar(weights_map)

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
        "Optional check — not a forecast. We reuse today’s satellite record and "
        "ask: if rain or heat shifted, which rotations still look good for you?",
        step=4,
    )
    st.markdown(
        '<p class="fs-farm-why">Scores update right away. The map and timelapse '
        "stay the same.</p>",
        unsafe_allow_html=True,
    )
    rain_opts = [("Drier (−20%)", 0.8), ("Today", 1.0), ("Wetter (+20%)", 1.2)]
    temp_opts = [("Today", 0.0), ("+1 °C", 1.0), ("+2 °C", 2.0)]
    rain_labels = [r[0] for r in rain_opts]
    temp_labels = [t[0] for t in temp_opts]
    c_rain, c_temp = st.columns(2)
    with c_rain:
        st.markdown(
            '<p class="fs-farm-q">What if yearly rain changed?</p>',
            unsafe_allow_html=True,
        )
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
        st.markdown(
            '<p class="fs-farm-q">What if seasons ran warmer?</p>',
            unsafe_allow_html=True,
        )
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
        "Side-by-side comparison with the same six goal scores on every option.",
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


if hasattr(st, "fragment"):

    @st.fragment  # type: ignore[attr-defined]
    def options_fragment() -> None:
        _options_block()

    options_fragment()
else:
    _options_block()

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
