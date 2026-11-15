"""Farmer input categories → documented numbers (FAO-56 / project constants).

Every category maps to a number used by scoring or filtering. Values that come
from published tables carry ``needs_expert_review=True`` until a domain expert
signs them off for the demo regions.
"""

from __future__ import annotations

from typing import Any, Literal

# ---------------------------------------------------------------------------
# Water access
# ---------------------------------------------------------------------------

WaterCategory = Literal[
    "rain_only",
    "some_irrigation",
    "fully_irrigated",
    "not_sure",
]

# Engine WaterAccess used inside scoring (not_sure → rainfed).
WATER_ACCESS_MAP: dict[str, str] = {
    "rain_only": "rainfed",
    "some_irrigation": "limited",
    "fully_irrigated": "irrigated",
    "not_sure": "rainfed",
}

WATER_LABELS: dict[str, str] = {
    "rain_only": "Rain only",
    "some_irrigation": "Some irrigation (only in dry spells)",
    "fully_irrigated": "Fully irrigated",
    "not_sure": "Not sure",
}

WATER_HINT = "Do you water this field, or rely on rain?"
WATER_HELP = (
    "Example: if you only irrigate during a dry spell once or twice a season, "
    "choose “Some irrigation”. If canals or wells cover the whole season, "
    "choose “Fully irrigated”."
)
WATER_WHY = (
    "We use this to drop crops that need a full irrigation season when you are "
    "rain-only, and to score water use fairly."
)

# Limited irrigation: documented fractional water allowance added to rainfed
# baseline before GRACE penalty (see score_water). needs_expert_review: True
LIMITED_IRRIGATION_ALLOWANCE = 0.12  # +0.12 on [0,1] water score; expert review
LIMITED_IRRIGATION_ALLOWANCE_META = {
    "value": LIMITED_IRRIGATION_ALLOWANCE,
    "needs_expert_review": True,
    "source": "Project constant — small documented lift for dry-spell irrigation",
}

# Crops that require irrigation under rain-only / not-sure water access.
# Filter uses this set; rice is the primary irrigated cereal in demos.
NEEDS_IRRIGATION_CROP_IDS = frozenset({"rice", "cotton"})

# ---------------------------------------------------------------------------
# Soil type — FAO-56 Table 19 (Allen et al. 1998) total available water
# ---------------------------------------------------------------------------

SoilCategory = Literal["sandy", "loamy", "silty", "clay", "not_sure"]

# Engine SoilType used elsewhere.
SOIL_TYPE_MAP: dict[str, str] = {
    "sandy": "sand",
    "loamy": "loam",
    "silty": "silt",
    "clay": "clay",
    "not_sure": "loam",
}

SOIL_LABELS: dict[str, str] = {
    "sandy": "Sandy",
    "loamy": "Loamy",
    "silty": "Silty",
    "clay": "Clay",
    "not_sure": "Not sure",
}

SOIL_HINT = (
    "Rub moist soil between your fingers: gritty = sandy, smooth like flour = silty, "
    "sticky and holds a shape = clay, a mix = loamy."
)
SOIL_HELP = (
    "Example: if a moist ribbon of soil feels gritty and falls apart, pick Sandy. "
    "If it feels sticky and holds a long ribbon, pick Clay."
)
SOIL_WHY = (
    "Soil feel tells us how much rain the ground can store between showers, "
    "and how easily water soaks in."
)

# Total available water (TAW) midpoints from FAO-56 Table 19 ranges (mm water / m soil).
# Sand 50–100 → 75; Loam 120–180 → 150; Silt loam 130–190 → 160; Clay 120–180 → 150.
# Citation: Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998). Crop evapotranspiration
# — Guidelines for computing crop water requirements. FAO Irrigation and Drainage Paper 56.
SOIL_AWC_MM_PER_M: dict[str, float] = {
    "sandy": 75.0,
    "loamy": 150.0,
    "silty": 160.0,
    "clay": 150.0,
    "not_sure": 150.0,  # treated as loamy
}

# Typical basic infiltration rates (mm/h) by texture class — order-of-magnitude
# guidance consistent with FAO/NRCS texture guidance (not a site measurement).
SOIL_INFILTRATION_MM_H: dict[str, float] = {
    "sandy": 25.0,
    "loamy": 13.0,
    "silty": 7.0,
    "clay": 2.5,
    "not_sure": 13.0,
}

SOIL_TEXTURE_META = {
    "source": (
        "Allen et al. 1998 FAO-56 Table 19 (TAW mm/m midpoints); "
        "infiltration order-of-magnitude"
    ),
    "needs_expert_review": True,
}

# Reference AWC for normalizing soil storage into a [0,1] water-score blend.
SOIL_AWC_REFERENCE_MM_PER_M = 150.0
# Blend weight: mostly crop water balance, small soil-storage adjustment.
WATER_SOIL_BLEND = 0.15

# ---------------------------------------------------------------------------
# Goal importance → weights
# ---------------------------------------------------------------------------

GoalKey = Literal[
    "water",
    "forage",
    "nitrogen",
    "erosion",
    "organic_matter",
    "market",
]

GoalImportance = Literal[0, 1, 2]  # Not important / Important / Very important

GOAL_KEYS: tuple[GoalKey, ...] = (
    "water",
    "forage",
    "nitrogen",
    "erosion",
    "organic_matter",
    "market",
)

GOAL_LABELS: dict[str, str] = {
    "water": "Use less water",
    "forage": "Animal feed (forage)",
    "nitrogen": "Add nitrogen naturally",
    "erosion": "Reduce erosion",
    "organic_matter": "Build organic matter",
    "market": "Good market for the crops",
}

GOAL_HINTS: dict[str, str] = {
    "water": "Is water scarce or expensive for you?",
    "forage": "Do you keep animals that could eat or graze a crop?",
    "nitrogen": "Do you want to rely less on fertiliser?",
    "erosion": "Does your soil wash or blow away?",
    "organic_matter": "Do you want healthier, darker, richer soil over time?",
    "market": "Do you need the crops to sell well?",
}

# One plain sentence per goal — what the score means for a farmer (not the formula).
GOAL_PLAIN: dict[str, str] = {
    "water": "Favours rotations that need less irrigation or hold more rain in the soil.",
    "forage": "Favours crops animals can graze or eat — only when you say this matters.",
    "nitrogen": "Favours legumes that put nitrogen back into the soil for the next crop.",
    "erosion": "Favours cover that keeps soil from washing or blowing when fields are bare.",
    "organic_matter": "Favours residues and roots that build darker, richer soil over years.",
    "market": "Favours crops that usually sell more easily in typical markets.",
}

GOAL_MEASURED: dict[str, str] = {
    "water": (
        "Crop water demand (FAO-56 ET0 from NASA POWER × crop coefficient) minus "
        "effective rain (NASA POWER + GPM IMERG), plus irrigation need, adjusted by "
        "soil available water capacity (FAO-56 texture)."
    ),
    "forage": (
        "Forage score from crops.json forage_value; counts only when this goal is "
        "Important or Very important."
    ),
    "nitrogen": (
        "Nitrogen score from legumes in the rotation (crops.json nitrogen_fixing)."
    ),
    "erosion": (
        "Bare months (Sentinel-2 NDVI) × slope (SRTM) × heavy-rain months, reduced by "
        "crop cover."
    ),
    "organic_matter": (
        "Residue, root depth and months of soil cover (crops.json + Sentinel-2 bare months)."
    ),
    "market": "Market score from crops.json market_tier.",
}

# Farmer-facing block intros (UI).
FIELD_CONFIRM_HINT = (
    "This is the polygon satellites watch — drawn on the map or opened from a demo."
)
CROPS_CONFIRM_HINT = (
    "Satellites already spotted your growing seasons. Confirm the crop in each season — "
    "change only if that is wrong."
)
CROPS_WHY = "Your current crops are the baseline. Every option below is compared to this."
GOALS_HINT = (
    "Tap how much each goal matters. Options that match your answers rise in the ranking."
)
GOALS_WHY = "We re-score every rotation as soon as you change a goal — nothing to submit."
TWO_YEAR_LABEL = "My main crops take two years (for example maize, then soybean)"
TWO_YEAR_HELP = (
    "Turn this on when two cash crops share one summer season across years. "
    "Leave it off when two seasons fit in one year (for example rice then wheat)."
)
MONTHS_EXPANDER_LABEL = "Adjust months"

IMPORTANCE_LABELS: dict[int, str] = {
    0: "Not important",
    1: "Important",
    2: "Very important",
}

EQUAL_WEIGHTS_NOTE = (
    "All goals set to Not important — using equal weights so options can still be ranked."
)

# Planting/harvest month edit tolerance before adding a data gap.
MONTH_SHIFT_DATA_GAP_THRESHOLD = 1

# Fixed risks listed on every strategy card (brief).
STANDARD_LOCAL_RISKS = [
    "Check machinery and labour needs for this rotation locally",
    "Confirm seed availability in your area",
    "Check local prices and buyers before changing crops",
    "Review pest and herbicide carryover with a local adviser",
]

# Demo field pre-filled answers (labelled demo defaults).
DEMO_FARM_ANSWERS: dict[str, dict[str, Any]] = {
    "iowa": {
        "water_category": "rain_only",
        "soil_category": "loamy",
        "goals": {
            "water": 1,
            "forage": 0,
            "nitrogen": 1,
            "erosion": 1,
            "organic_matter": 1,
            "market": 2,
        },
        "label": "Demo answers — Central Iowa",
    },
    "uk": {
        "water_category": "rain_only",
        "soil_category": "clay",
        "goals": {
            "water": 1,
            "forage": 0,
            "nitrogen": 1,
            "erosion": 2,
            "organic_matter": 1,
            "market": 1,
        },
        "label": "Demo answers — Cambridgeshire",
    },
    "punjab": {
        "water_category": "fully_irrigated",
        "soil_category": "loamy",
        "goals": {
            "water": 2,
            "forage": 1,
            "nitrogen": 1,
            "erosion": 1,
            "organic_matter": 1,
            "market": 2,
        },
        "label": "Demo answers — Punjab",
    },
}


def resolve_water_access(category: str) -> tuple[str, list[str]]:
    """Return (engine WaterAccess, data_gaps)."""
    gaps: list[str] = []
    cat = category if category in WATER_ACCESS_MAP else "not_sure"
    if cat == "not_sure":
        gaps.append("Water source marked Not sure — treated as rain only")
    return WATER_ACCESS_MAP[cat], gaps


def resolve_soil_category(category: str) -> tuple[str, float, float, list[str]]:
    """Return (engine soil type, AWC mm/m, infiltration mm/h, data_gaps)."""
    gaps: list[str] = []
    cat = category if category in SOIL_AWC_MM_PER_M else "not_sure"
    if cat == "not_sure":
        gaps.append("Soil type marked Not sure — treated as loamy (FAO-56 default)")
    return (
        SOIL_TYPE_MAP[cat],
        float(SOIL_AWC_MM_PER_M[cat]),
        float(SOIL_INFILTRATION_MM_H[cat]),
        gaps,
    )


def normalize_goal_weights(
    importance: dict[str, int],
) -> tuple[dict[str, float], str | None]:
    """Map 0/1/2 importance → weights that sum to 1. All-zero → equal + note."""
    raw = {k: int(importance.get(k, 0)) for k in GOAL_KEYS}
    total = sum(raw.values())
    if total <= 0:
        equal = 1.0 / len(GOAL_KEYS)
        return {k: equal for k in GOAL_KEYS}, EQUAL_WEIGHTS_NOTE
    return {k: raw[k] / total for k in GOAL_KEYS}, None


def forage_goal_active(importance: dict[str, int] | None) -> bool:
    """Forage score counts only when Animal feed is Important or Very important."""
    if not importance:
        return False
    return int(importance.get("forage", 0)) >= 1
