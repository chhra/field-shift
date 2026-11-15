"""UK rotation model: the team's rule-based model on the Rothamsted Broadbalk field.

Farmer inputs -> team_model/app_adapter.py -> team_model/model.py -> three rotations
(current, Option A, Option B), each with benefits, risks, local checks and
information gaps. Kept separate from the Field page, which uses fieldshift/engine.
"""

from __future__ import annotations

import json

import streamlit as st
from fieldshift.engine.inputs_config import (
    QUESTIONS,
    default_goal_order,
)
from team_model import app_adapter, model
from ui.components import fact_chips, hero, question, recommendation_banner, section
from ui.goal_rank import goal_ranking
from ui.strategy_cards import render_uk_option_plans

_MONTHS = model.MONTHS
_DEFAULT_ROTATION = [
    "Winter wheat",
    "Winter barley",
    "Winter oilseed rape",
    "Spring field beans",
    "Spring barley",
    "Sugar beet",
]
_STATION_SUMMARY = model.DATA_DIR / "processed" / "climate" / "station_vs_nasa_rain_summary.json"


@st.cache_data(show_spinner="Scoring rotations…")
def _run(
    current: tuple[str, ...],
    goal_order: tuple[str, ...],
    water: str,
    soil: str,
    warming_c: float,
    lat: float | None = None,
    lon: float | None = None,
) -> dict:
    """Run the model (cached: the same answers give the same result instantly)."""
    return app_adapter.recommend_for_app(
        list(current),
        water=water,
        soil=soil,
        warming_c=warming_c,
        lat=lat,
        lon=lon,
        goal_order=list(goal_order),
    )


@st.cache_data(show_spinner="Fetching NASA POWER climate for your location…")
def _location_data(lat: float, lon: float):
    """Crops + live NASA POWER farm climate for an entered UK point (cached)."""
    return app_adapter.load_location_data(lat, lon)


def _months(ms: list[int]) -> str:
    """[10, 11, 12, 1] -> "Oct–Jan" when consecutive, else "Oct, Nov, Jan"."""
    if not ms:
        return "none"
    # a run of months (even one wrapping the new year, e.g. Oct-Jan) has exactly
    # one month whose previous month is not in the list: that is where it starts
    starts = [m for m in ms if ((m - 2) % 12) + 1 not in ms]
    if len(starts) == 1 and len(ms) > 1:
        first = starts[0]
        ordered = sorted(ms, key=lambda m: (m - first) % 12)
        return f"{_MONTHS[ordered[0] - 1]}–{_MONTHS[ordered[-1] - 1]}"
    return ", ".join(_MONTHS[m - 1] for m in sorted(ms))


# ----------------------------------------------------------------------------
# Header and the field
# ----------------------------------------------------------------------------

# Location: a point the farmer entered on Home, or Rothamsted Broadbalk by default.
_lat = st.session_state.get("ukm_lat")
_lon = st.session_state.get("ukm_lon")
location_error: str | None = None
at_location = False

if _lat is not None and _lon is not None:
    try:
        crops, _successors, farm, weather = _location_data(float(_lat), float(_lon))
        at_location = True
    except ValueError as err:  # outside the UK box
        location_error = str(err)
        crops, _successors, farm, weather = app_adapter.load_data()
    except RuntimeError as err:  # NASA POWER unavailable
        location_error = (
            f"NASA POWER could not be reached ({err}). "
            "Showing Rothamsted Broadbalk instead."
        )
        crops, _successors, farm, weather = app_adapter.load_data()
else:
    crops, _successors, farm, weather = app_adapter.load_data()

real_farm = weather is not None
# Effective coords passed to scoring: only when the live location actually loaded.
eff_lat = float(_lat) if at_location else None
eff_lon = float(_lon) if at_location else None

hero(
    "UK rotation model",
    "Three crop rotations for one UK field: yours, a recommended option, and an alternative.",
    sub="Compare the options side by side. Scores stay behind the scenes.",
    mode_label=(
        f"Your field · {float(_lat):.3f}, {float(_lon):.3f}"
        if at_location
        else "Rothamsted Broadbalk"
        if real_farm
        else "Test climate"
    ),
    live=real_farm,
)

if location_error:
    st.warning(location_error)

section(
    "The field",
    (
        f"Your field at {float(_lat):.3f}, {float(_lon):.3f}, from NASA POWER daily "
        f"climate ({farm.get('years', '')}). The UK crop rules are applied to this "
        "location's weather — check them against local experience."
        if at_location
        else "Broadbalk at Rothamsted Research, Harpenden: the world's longest-running "
        "farm experiment, so the tool can be checked against real records."
        if real_farm
        else "The NASA climate files were not found, so a made-up test climate is used."
    ),
    step=1,
)

chips = [
    {
        "label": "Rain a year",
        "value": f"{farm['annual_rain_mm']} mm",
        "meaning": f"Wettest for bare soil: {_months(farm['wet_months'])}",
        "help": "NASA POWER" if real_farm else "Test value",
    },
    {
        "label": "Dry months",
        "value": _months(farm["dry_months"]),
        "meaning": "Rain is less than evaporation",
        "help": "NASA POWER, Hargreaves ET0" if real_farm else "Test value",
    },
]
if real_farm:
    chips += [
        {
            "label": "Summer rain",
            "value": f"{farm['summer_rain_recent_mm']:.0f} mm",
            "meaning": f"Was {farm['summer_rain_earlier_mm']:.0f} mm in {farm['earlier_period']}",
            "help": f"NASA POWER, Jun–Aug, {farm['recent_period']}",
        },
        {
            "label": "Hot days a year",
            "value": f"{farm['hot_days_recent']:.0f}",
            "meaning": f"Was {farm['hot_days_earlier']:.0f} in {farm['earlier_period']}",
            "help": f"Days of 25 °C or more, {farm['recent_period']}",
        },
    ]
fact_chips(chips)

if real_farm and _STATION_SUMMARY.exists():
    station = json.loads(_STATION_SUMMARY.read_text(encoding="utf-8"))
    near = station["nasa_point"]["distance_to_station_km"] < 30 and abs(
        station["nasa_point"]["latitude"] - float(farm["latitude"])
    ) < 0.01
    if near:
        agree = station["monthly_agreement_corrected_station"]
        wet = station["wettest_10pct_of_months"]
        with st.expander("How the satellite data compares with the rain gauge on this farm"):
            st.markdown(
                f"NASA POWER rainfall is a model and satellite estimate averaged over a grid "
                f"cell about 50 km wide. Rothamsted has measured rain with a gauge on this "
                f"farm since 1853. Over {station['period']} "
                f"({station['months_compared']} months):\n\n"
                f"- **Average:** NASA {station['mean_annual_rain_mm']['nasa_power']} mm a year, "
                f"gauge {station['mean_annual_rain_mm']['station_corrected']} mm "
                f"({agree['bias_pct']:+}%).\n"
                f"- **Month to month:** correlation {agree['correlation']}, typical error "
                f"{agree['mean_abs_error_mm']} mm.\n"
                f"- **Extremes are smoothed:** in the wettest tenth of months NASA shows "
                f"{wet['nasa_mean_mm']} mm against the gauge's {wet['station_mean_mm']} mm "
                f"({wet['nasa_vs_station_pct']:+}%).\n\n"
                f"So the wet-month erosion risk below is more likely understated than overstated."
            )
            st.caption(station["station_source"])

# ----------------------------------------------------------------------------
# Farmer inputs
# ----------------------------------------------------------------------------

section(
    "Your farm",
    "Five questions. Answer “Not sure” where you don't know: the tool will say what it "
    "could not check.",
    step=2,
)

question(
    1,
    QUESTIONS["crops"][0],
    "One main crop per harvest year, in order. A ley counts once and stays 3 years. "
    "Leave cover crops out: the tool adds them where the soil would be bare.",
)
n_crops = st.radio(
    "How many crops are in your rotation?",
    [1, 2, 3, 4, 5, 6],
    index=2,
    horizontal=True,
    key="ukm-n",
)
choices = app_adapter.crop_choices(crops)
current: list[str] = []
cols = st.columns(min(3, n_crops))
for i in range(n_crops):
    with cols[i % len(cols)]:
        current.append(
            st.selectbox(
                f"Crop {i + 1}",
                choices,
                index=choices.index(_DEFAULT_ROTATION[i]),
                key=f"ukm-crop-{i}",
            )
        )

question(2, *QUESTIONS["water"])
water = st.radio(
    "Water source",
    list(model.WATER_SOURCES),
    format_func=lambda k: model.WATER_SOURCES[k],
    horizontal=True,
    key="ukm-water",
    label_visibility="collapsed",
)

question(3, *QUESTIONS["soil"])
soil_keys = list(model.SOIL_TYPES)
soil = st.radio(
    "Soil type",
    soil_keys,
    index=soil_keys.index("loamy"),
    format_func=lambda k: model.SOIL_TYPES[k],
    horizontal=True,
    key="ukm-soil",
    label_visibility="collapsed",
)

question(4, *QUESTIONS["goals"])
goal_order = goal_ranking("ukm", default_goal_order(app_adapter.DEFAULT_GOALS))

question(None, "What if seasons ran warmer?")
st.caption(
    "Not a forecast. Every day in the NASA record is made this much warmer, "
    "then heat stress and frost are worked out again for each crop."
)
warming = st.radio(
    "Warming",
    [0.0, 1.0, 2.0],
    format_func=lambda v: "Today" if v == 0 else f"+{v:g} °C",
    horizontal=True,
    key="ukm-warm",
    label_visibility="collapsed",
)

# ----------------------------------------------------------------------------
# Results
# ----------------------------------------------------------------------------

section(
    "Your options",
    "Your rotation, the recommended option, and an alternative — compare them like plans.",
    step=3,
)

try:
    out = _run(
        tuple(current),
        tuple(goal_order),
        water,
        soil,
        float(warming),
        eff_lat,
        eff_lon,
    )
except ValueError as err:
    st.error(str(err))
    st.stop()

results = out["results"]
base = results[0]

if len(results) > 1:
    best = results[1]
    years = best["years"]
    year_word = "year" if years == 1 else "years"
    recommendation_banner(
        f"{best['rotation']} ({years} {year_word}) is the recommended option "
        f"for your priorities, ahead of your current rotation."
    )
else:
    st.info(base["reasons"][-1] if base["reasons"] else "No alternative rotation was found.")

render_uk_option_plans(results)

# ----------------------------------------------------------------------------
# Reliability
# ----------------------------------------------------------------------------

section(
    "How reliable is this?",
    "This tool supports your judgement and your agronomist's. It does not replace them.",
    step=4,
)
st.markdown(
    "- **Rules, not predictions.** Options are compared with each other. They are not "
    "yield or profit forecasts.\n"
    "- **Approximate values.** Sowing months, crop roles, forage and residue levels, and the "
    "ranking rules are our estimates and need checking against AHDB guidance.\n"
    "- **Frost limits are harsh.** FAO EcoCrop gives one killing temperature per species; "
    "UK varieties are often hardier, so frost warnings for barley, clover and ryegrass are "
    "likely overstated.\n"
    "- **Satellite scale.** NASA POWER describes a grid cell about 50 km wide, not your "
    "field. Ground frost and local downpours can differ.\n"
    + (
        ""
        if real_farm
        else "- **Test climate in use.** Heat stress and daily frost were not checked.\n"
    )
)
with st.expander("Data sources"):
    for what, source in app_adapter.DATA_SOURCES:
        st.markdown(f"- **{what}:** {source}")
