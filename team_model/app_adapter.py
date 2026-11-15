"""
Bridge between the Streamlit app's farmer inputs and the rotation model.

The app (views/, fieldshift/) and the model (model.py) were built separately and
name things differently. This file is the ONE place that translates between
them, so when the app's inputs change, only this file needs updating.

What it translates
  goals        the app's six goals, rated 0-2  ->  the model's six priorities, 0-3
  water, soil  same answer options in both, passed straight through
  warming      the app's "what if seasons ran warmer" (+°C)  ->  warming_c
  crops        the app's crop ids (winter_wheat)  ->  the model's names (Winter wheat)

It only depends on model.py (and pandas), not on the app's packages, so it can
be tested on its own.
"""
from functools import lru_cache

from . import model

# -----------------------------------------------------------------------------
# GOALS -> PRIORITIES
# The challenge brief lists six farmer priorities. The app calls them "goals"
# and the model weights one score bucket with each.
#   app goal          model priority
# -----------------------------------------------------------------------------
GOAL_TO_PRIORITY = {
    "water": "water",                    # water use
    "forage": "forage",                  # forage value
    "nitrogen": "fertility",             # nitrogen-fixing potential
    "erosion": "soil",                   # erosion reduction
    "organic_matter": "organic_matter",  # organic matter improvement
    "market": "income",                  # market suitability
}

# The app rates each goal 0 / 1 / 2 (Not important / Important / Very important).
# The model was tuned with priorities 0-3 where 2 is "normal", so:
IMPORTANCE_TO_PRIORITY = {0: 0, 1: 2, 2: 3}

# The same defaults as the app's Field page (GoalImportanceSet in fieldshift/models.py).
DEFAULT_GOALS = {"water": 1, "forage": 0, "nitrogen": 1, "erosion": 1,
                 "organic_matter": 1, "market": 1}

# -----------------------------------------------------------------------------
# CROPS
# App crop id -> model crop name, for the crops that exist in both. The app has
# one "barley" and the model has two; winter barley is the commoner UK choice.
# App crops with no UK equivalent (soybean, rice, cotton...) are not listed.
# -----------------------------------------------------------------------------
APP_CROP_TO_MODEL = {
    "winter_wheat": "Winter wheat",
    "barley": "Winter barley",
    "oats": "Spring oats",
    "maize": "Maize",
    "canola": "Winter oilseed rape",
    "field_pea": "Spring peas",
    "red_clover": "Red clover ley",
    "cereal_rye_cover": "Rye (cover)",
}

# Where each kind of statement in the results comes from (for "evidence" tags).
DATA_SOURCES = [
    ("Farm climate, heat stress and frost", "NASA POWER daily data, 2000-2025 (MERRA-2)"),
    ("Crop climate limits", "FAO EcoCrop"),
    ("Heat-stress thresholds", "Published studies listed in data/raw/rotation/heat_thresholds.csv"),
    ("Sowing months, crop roles, forage and residue levels",
     "Approximate UK values in data/raw/rotation/crop_practices.csv (check against AHDB)"),
    ("Which crop follows which", "Successor matrix in data/raw/rotation/successor_matrix.csv"),
    ("Rain gauge check", "Rothamsted Meteorological Station: Perryman & Scott (2025), "
                         "DOI 10.23637/rmsTMArain1853-2024-01, CC BY 4.0"),
]


def priorities_from_goals(goals):
    """Turn the app's goal ratings into the model's priorities.

        priorities_from_goals({"water": 2, "forage": 0, "nitrogen": 1,
                               "erosion": 1, "organic_matter": 1, "market": 1})
        -> {"water": 3, "forage": 0, "fertility": 2, "soil": 2,
            "organic_matter": 2, "income": 2}

    Goals left out use the app's defaults. Raises ValueError for an unknown goal
    or a rating that isn't 0, 1 or 2.
    """
    unknown = set(goals) - set(GOAL_TO_PRIORITY)
    if unknown:
        raise ValueError(f"Unknown goal(s): {sorted(unknown)}. Valid: {', '.join(GOAL_TO_PRIORITY)}")
    out = {}
    for goal, priority in GOAL_TO_PRIORITY.items():
        rating = goals.get(goal, DEFAULT_GOALS[goal])
        if rating not in IMPORTANCE_TO_PRIORITY:
            raise ValueError(f"Goal {goal!r} must be rated 0, 1 or 2, not {rating!r}.")
        out[priority] = IMPORTANCE_TO_PRIORITY[rating]
    return out


def priorities_from_order(order):
    """Turn the farmer's goal ORDER (most important first) into the model's priorities.

    Same rank-sum shares as the Field page (with n goals listed, 1st counts n, 2nd n-1,
    ... last 1), scaled so 1st place gets 3, the model's "high", keeping every priority
    in the model's tuned 0-3 range. Goals left out get 0. An empty list uses the defaults.

        priorities_from_order(["erosion", "water"])
        -> {"water": 1.5, "forage": 0, "fertility": 0, "soil": 3.0,
            "organic_matter": 0, "income": 0}
    """
    order = list(dict.fromkeys(order))
    unknown = set(order) - set(GOAL_TO_PRIORITY)
    if unknown:
        valid = ", ".join(GOAL_TO_PRIORITY)
        raise ValueError(f"Unknown goal(s): {sorted(unknown)}. Valid: {valid}")
    if not order:
        return priorities_from_goals(DEFAULT_GOALS)
    n = len(order)
    out = {priority: 0 for priority in GOAL_TO_PRIORITY.values()}
    for i, goal in enumerate(order):
        out[GOAL_TO_PRIORITY[goal]] = round(3 * (n - i) / n, 2)
    return out


def crops_from_app_ids(crop_ids):
    """Turn the app's crop ids into the model's crop names.
    Raises ValueError listing any crop the model doesn't have."""
    missing = [c for c in crop_ids if c not in APP_CROP_TO_MODEL]
    if missing:
        raise ValueError(f"The UK model has no equivalent for: {missing}. "
                         f"Known: {', '.join(APP_CROP_TO_MODEL)}")
    return [APP_CROP_TO_MODEL[c] for c in crop_ids]


@lru_cache(maxsize=1)
def load_data():
    """Load the model's data once: (crops, successors, farm, weather).

    Uses the real farm climate if the NASA files exist, otherwise the model's
    FAKE_FARM with no daily weather (so heat stress and daily frost are skipped).
    This is the Rothamsted Broadbalk default, used when the farmer gives no
    coordinates (see load_location_data for an entered location).
    """
    crops, successors = model.load_crops(), model.load_successors()
    if model.FARM_FILE.exists() and model.WEATHER_FILE.exists():
        return crops, successors, model.load_farm(), model.load_weather()
    return crops, successors, dict(model.FAKE_FARM), None


@lru_cache(maxsize=8)
def load_location_data(lat: float, lon: float):
    """Load the model's data for an entered UK location: (crops, successors, farm, weather).

    The crop table is location-independent; the farm climate and daily weather
    are built live from NASA POWER at (lat, lon). Cached per rounded point so the
    same location is not re-fetched. Raises ValueError outside the UK, RuntimeError
    if NASA POWER is unavailable.
    """
    from . import live_climate

    crops, successors = model.load_crops(), model.load_successors()
    farm, weather = live_climate.build_farm_from_power(float(lat), float(lon))
    return crops, successors, farm, weather


def crop_choices(crops=None):
    """The crops a farmer can pick for their current rotation, in a sensible
    order: arable and vegetable crops first, then leys, then fruit.
    Cover crops are left out: the model adds those itself."""
    crops = crops or load_data()[0]
    order = {"cash": 0, "forage": 1, "fruit": 2}
    names = [n for n, c in crops.items() if c["role"] in order]
    return sorted(names, key=lambda n: (order[crops[n]["role"]], n))


def recommend_for_app(current, goals=None, water="rain_only", soil="not_sure", warming_c=0.0,
                      lat=None, lon=None, goal_order=None):
    """Run the model from the app's inputs.

    Arguments
        current    the farmer's rotation as MODEL crop names, one per harvest year
                   (use crops_from_app_ids() first if you have app crop ids)
        goals      the app's goal ratings, e.g. {"water": 2, "forage": 0, ...} (0-2 each)
        water      "rain_only", "some_irrigation", "fully_irrigated" or "not_sure"
        soil       "sandy", "loamy", "silty", "clay" or "not_sure"
        warming_c  what-if warming in °C (0, 1, 2...)
        lat, lon   optional UK coordinates. When given, the farm climate is built
                   live from NASA POWER at that point; otherwise Rothamsted Broadbalk.
        goal_order optional goal keys, most important first. When given, it sets the
                   priorities (see priorities_from_order) and `goals` is ignored.

    Returns a dictionary:
        results     the model's rotations: current, Option A, Option B (may be fewer)
        priorities  the priorities the goals were turned into
        farm        the farm climate summary used
        has_weather True if daily NASA data was available (heat and frost checked)
    """
    if lat is not None and lon is not None:
        crops, successors, farm, weather = load_location_data(float(lat), float(lon))
    else:
        crops, successors, farm, weather = load_data()
    if goal_order is not None:
        priorities = priorities_from_order(goal_order)
    else:
        priorities = priorities_from_goals(goals or DEFAULT_GOALS)
    results = model.recommend(list(current), farm, priorities, crops, successors,
                              weather, float(warming_c), water, soil)
    return {"results": results, "priorities": priorities, "farm": farm,
            "has_weather": weather is not None}
