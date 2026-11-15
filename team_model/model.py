"""
=============================================================================
FIELD SHIFT - rule-based crop rotation model
NASA Space Apps Challenge 2026
=============================================================================

WHAT THIS FILE DOES
-------------------
It takes five things:
  1. the farm's climate        (from NASA POWER data, see INPUT FILES below)
  2. the crop table            (EcoCrop climate + UK practices: what each crop needs and offers)
  3. the farmer's rotation     (e.g. winter wheat -> maize -> winter barley)
  4. the farmer's priorities   (the six in the challenge brief: water use, forage value,
                               nitrogen fixing, erosion reduction, organic matter, market)
  5. the farmer's field        (water source: rain only or irrigated; soil type)

and returns 3 crop rotations:
  - the farmer's CURRENT rotation, with its problems explained
  - OPTION A: the best-scoring alternative
  - OPTION B: a genuinely different alternative

Each rotation comes with a score plus plain-English benefits, risks and
"check locally" notes, so the farmer can see WHY it was suggested.

HOW IT WORKS (the big picture)
------------------------------
  Step A  Suitability   Can each crop grow in this climate at all?
                        (compares EcoCrop climate ranges with the farm's NASA data)
  Step B  Rules         Each rotation is checked against agronomy rules, e.g.
                        "is the soil bare in the wettest months?" Every rule adds or
                        removes points and writes a sentence explaining itself.
  Step C  Priorities    Points are multiplied by the farmer's priorities, so a farmer
                        who cares about water sees water-saving rotations ranked higher.
  Step D  Choose        The model tries hundreds of variations of the current rotation
                        (swapping up to 2 crops, adding cover crops), scores them all,
                        and returns the best ones.

WHY RULES AND NOT MACHINE LEARNING?
-----------------------------------
There is no public dataset of "rotation -> outcome" for UK farms to train on, and
the challenge asks us to EXPLAIN every suggestion. Rules are transparent: every
point in the score can be traced back to a sentence the farmer can read.
The approach is inspired by:
  - ROTOR (Bachinger & Zander 2007): a rule-based rotation planning tool
  - Fenz et al. (2023): a "successor crop suitability matrix" (how good crop B is
    when it follows crop A), here stored in successor_matrix.csv

INPUT FILES (in the project's data folder)
-----------------------------------------
  processed/ecocrop/ecocrop_uk_25_crops.csv
                           25 UK crops with their FAO EcoCrop climate needs
                           (made by scripts/crops/filter_uk_25_crops.py).
  raw/rotation/crop_practices.csv
                           How each crop is grown in the UK (role, family, sowing and
                           harvest month, water need...). EcoCrop has none of this, so
                           these are approximate UK values: check against AHDB.
                           One EcoCrop crop can have several rows, e.g. Rye is both a
                           cash crop and a cover crop ("Rye (cover)").
  processed/climate/farm_climate_summary.json
                           The farm's climate (wet, dry and frost months...), made from
                           NASA POWER by scripts/climate/build_farm_climate.py.
  processed/climate/nasa_power_clean.csv
                           Daily NASA POWER weather. Used for the crop-specific
                           heat stress and frost indices, which need a crop's
                           thresholds and so are computed here, not in a script.
  raw/rotation/heat_thresholds.csv
                           Each crop's heat-stress threshold (°C) and flowering /
                           grain-fill months, with the source and a confidence level.
                           Crops left blank or not listed are an information gap.
  raw/rotation/successor_matrix.csv
                           A score from -3 (bad) to +3 (good) for every
                           "crop B after crop A" pair, with a one-line reason.

HOW TO RUN
----------
  pip install pandas
  python model.py
=============================================================================
"""
import json
import re
import warnings
from collections import Counter
from functools import lru_cache
from pathlib import Path

import pandas as pd


# =============================================================================
# SETTINGS AND CONSTANTS
# =============================================================================

# Where the data files live, inside the project's "data" folder:
#   processed/  files made by our scripts (here: the EcoCrop UK-25 table)
#   raw/        files we did not generate (here: the hand-written rotation tables)
# Using this file's own location means it works from any folder you run it from.
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
ECOCROP_FILE = DATA_DIR / "processed" / "ecocrop" / "ecocrop_uk_25_crops.csv"
PRACTICES_FILE = DATA_DIR / "raw" / "rotation" / "crop_practices.csv"
SUCCESSORS_FILE = DATA_DIR / "raw" / "rotation" / "successor_matrix.csv"
HEAT_FILE = DATA_DIR / "raw" / "rotation" / "heat_thresholds.csv"
FARM_FILE = DATA_DIR / "processed" / "climate" / "farm_climate_summary.json"
WEATHER_FILE = DATA_DIR / "processed" / "climate" / "nasa_power_clean.csv"

# Crop-specific climate indices (see crop_climate()):
RECENT_YEARS = 10          # heat stress is judged on the last 10 full years
HEAT_RISK_DAYS = 3         # >= 3 heat-stress days a year at flowering -> risk; >= 1 -> check
WINTER_KILL_RISK_PCT = 20  # >= 20% of winters -> "most winters" wording (a warning only, no points)
SPRING_FROST_CHECK_PCT = 25  # frost below the growing kill temperature after sowing in >= 25% of years -> check (no points)

# Candidate rotations (see candidates()): the model may make the rotation up to
# 2 years longer by adding break crops, but never longer than this.
MAX_ROTATION_YEARS = 5

# -----------------------------------------------------------------------------
# FARMER INPUTS: water source and soil type
# The answer options are the same as on the app's Field page
# (fieldshift/engine/inputs_config.py), so the two can be connected directly.
# The point values below are our own approximate judgement: check with an agronomist.
# -----------------------------------------------------------------------------
WATER_SOURCES = {
    "rain_only": "Rain only",
    "some_irrigation": "Some irrigation (only in dry spells)",
    "fully_irrigated": "Fully irrigated",
    "not_sure": "Not sure",                 # treated as rain only, and reported as a gap
}
SOIL_TYPES = {
    "sandy": "Sandy", "loamy": "Loamy", "silty": "Silty", "clay": "Clay",
    "not_sure": "Not sure",                 # no soil rules applied, and reported as a gap
}

# Water points for a thirsty crop (water_need = high) when summers are getting drier,
# and for a drought-tolerant crop. Irrigation removes the problem, so it removes the points.
THIRSTY_CROP_POINTS = {"rain_only": -3, "not_sure": -3, "some_irrigation": -1, "fully_irrigated": 0}
DROUGHT_TOLERANT_POINTS = {"rain_only": 2, "not_sure": 2, "some_irrigation": 2, "fully_irrigated": 1}

# Soil points
BARE_WET_MONTH_POINTS = -2          # per bare month in the wet season (any soil)
LIGHT_SOIL_BARE_WET_POINTS = -3     # ...on sandy or silty soil, which washes and blows away more easily
LIGHT_SOILS = ("sandy", "silty")
SANDY_THIRSTY_CROP_POINTS = -1      # sandy soil stores about half the water of a loam (FAO-56 Table 19)
CLAY_WET_HARVEST_POINTS = -2        # harvesting on clay in the wet months compacts and smears the soil
CLAY_DEEP_ROOT_POINTS = 1           # extra: deep roots matter most on heavy, slow-draining clay

# EcoCrop column codes -> the names used in this model.
# ktmpr is the killing temperature while the crop is dormant (winter), which is the
# one that matters for winter-sown crops; ktmp is the killing temperature while growing.
ECOCROP_COLUMNS = {
    "scientificname": "ecocrop_name",
    "topmn": "temp_opt_min_c", "topmx": "temp_opt_max_c",
    "tmin": "temp_abs_min_c", "tmax": "temp_abs_max_c",
    "ropmn": "rain_opt_min_mm", "ropmx": "rain_opt_max_mm",
    "rmin": "rain_abs_min_mm", "rmax": "rain_abs_max_mm",
    "ktmpr": "killing_temp_dormant_c", "ktmp": "killing_temp_growing_c",
    "gmin": "growing_days_min", "gmax": "growing_days_max",
    "phopmn": "soil_ph_opt_min", "phopmx": "soil_ph_opt_max",
}

# The climate values suitability() needs. A crop missing any of them (no EcoCrop
# match) gets "unknown" instead of being wrongly called unsuitable.
CLIMATE_COLUMNS = ["rain_abs_min_mm", "rain_abs_max_mm", "rain_opt_min_mm", "rain_opt_max_mm",
                   "temp_abs_min_c", "temp_abs_max_c", "temp_opt_min_c", "temp_opt_max_c"]

# -----------------------------------------------------------------------------
# Some crop families must not come back to the same field too often, because
# soil-borne pests and diseases build up. This sets the recommended minimum
# number of years between crops of the same family (common UK guidance; check
# against AHDB). Cereals and grasses are handled by the successor matrix instead.
# Format:  family: (minimum years, reason shown to the farmer)
# -----------------------------------------------------------------------------
MIN_YEARS_BETWEEN = {
    "legume": (5, "foot and root rots build up in the soil"),
    "brassica": (4, "clubroot and stem canker build up"),
    "solanaceae": (5, "potato cyst nematode builds up"),
    "beet": (3, "beet cyst nematode builds up"),
}

# Month names, used to turn month numbers into readable text ("Oct, Nov, Dec").
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Turns text levels from crop_practices.csv into numbers, so we can do maths with them
# (used for market value: "high" = 3, "medium" = 2 ...).
LEVEL = {"none": 0, "low": 1, "medium": 2, "high": 3}


# =============================================================================
# LOADING THE DATA FILES
# =============================================================================

def load_crops(ecocrop_path=ECOCROP_FILE, practices_path=PRACTICES_FILE, heat_path=HEAT_FILE):
    """Join the EcoCrop climate table, the UK practices table and the heat
    thresholds table, and return a dictionary: crop name -> that crop's row.

    This lets the rest of the code look up a crop by name, e.g.
        crops["Maize"]["water_need"]   ->  "high"
        crops["Maize"]["temp_opt_min_c"] -> 18.0
    """
    # utf-8-sig: the EcoCrop file starts with an invisible "BOM" character
    eco = pd.read_csv(ecocrop_path, encoding="utf-8-sig")
    eco = eco[["crop_name", *ECOCROP_COLUMNS]].rename(columns=ECOCROP_COLUMNS)
    practices = pd.read_csv(practices_path)

    # every practices row must point at a crop that exists in the EcoCrop file
    missing = set(practices["ecocrop_crop"]) - set(eco["crop_name"])
    if missing:
        raise ValueError(f"crop_practices.csv names crops not in {ecocrop_path.name}: "
                         f"{sorted(missing)}")

    crops = practices.merge(eco, left_on="ecocrop_crop", right_on="crop_name", how="left")
    crops = crops.drop(columns="crop_name")

    # heat thresholds: crops not listed get blanks (= information gap)
    heat = pd.read_csv(heat_path).rename(columns={
        "heat_sensitive_months": "heat_months", "confidence": "heat_confidence",
        "threshold_source": "heat_source"})
    unknown = set(heat["crop"]) - set(crops["crop"])
    if unknown:
        warnings.warn(f"{heat_path.name} has crops not in {practices_path.name} "
                      f"(ignored): {sorted(unknown)}", stacklevel=2)
    crops = crops.merge(heat[["crop", "heat_threshold_c", "heat_months",
                              "heat_confidence", "heat_source"]], on="crop", how="left")
    # plain dictionaries, not pandas rows: reading a value from a dict is ~20x
    # faster, and the scoring reads crop values hundreds of thousands of times
    return {row["crop"]: row for row in crops.to_dict("records")}


def load_successors(path=SUCCESSORS_FILE):
    """Read successor_matrix.csv and return a dictionary:
        (previous crop, next crop) -> (score, reason)

    Example:
        successors[("Winter field beans", "Winter wheat")]
        -> (3, "beans leave nitrogen and break cereal diseases: a classic entry for wheat")
    """
    m = pd.read_csv(path)
    return {(r.previous_crop, r.next_crop): (int(r.score), r.reason) for r in m.itertuples()}


def load_farm(path=FARM_FILE):
    """Read the farm's climate summary (the keys the model uses, plus display extras)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_weather(path=WEATHER_FILE):
    """Read the daily NASA POWER weather, indexed by date, full years only
    (a part year such as 2026 would make yearly counts look too low)."""
    w = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    days = w.groupby(w.index.year).size()
    return w[w.index.year.isin(days[days >= 365].index)]


# =============================================================================
# SMALL HELPER FUNCTIONS (months and crop types)
# =============================================================================

def month_names(ms):
    """Turn a list of month numbers into readable text: [10, 11] -> "Oct, Nov"."""
    return ", ".join(MONTHS[m - 1] for m in ms)


def months_between(a, b):
    """Return the months strictly AFTER month a and strictly BEFORE month b,
    wrapping round the end of the year.

    Examples:
        months_between(8, 10) -> [9]                     (Aug -> Oct: only Sep in between)
        months_between(10, 3) -> [11, 12, 1, 2]          (Oct -> Mar, across New Year)
        months_between(8, 8)  -> []                      (same month: nothing in between)

    We use this to find the months when a field is bare: after one crop is
    harvested and before the next one is sown.
    """
    return list(_months_between(a, b))


@lru_cache(maxsize=None)
def _months_between(a, b):
    """The work behind months_between(), remembered for each (a, b) pair
    because the scoring asks for the same pairs thousands of times."""
    if a == b:
        return ()
    out, m = [], a % 12 + 1          # start from the month after a (Dec -> Jan wraps round)
    while m != b and len(out) < 12:  # keep going until we reach b (max 12 months, for safety)
        out.append(m)
        m = m % 12 + 1               # next month, wrapping Dec (12) -> Jan (1)
    return tuple(out)


def is_perennial(c):
    """True for leys (grass, clover). They stay in the ground for several years,
    so in crop_practices.csv their harvest_month is 0 and they never leave the soil bare."""
    return int(c["harvest_month"]) == 0


def rotation_years(names, crops):
    """How many years a rotation lasts. Most crops take one year, but a ley
    stays in the ground for several (the "years" column in crop_practices.csv),
    so 4 crops with a 3-year ley make a 6-year rotation."""
    return sum(int(crops[n]["years"]) for n in names)


def is_winter_sown(c):
    """True for crops sown in late summer or autumn (Aug-Nov). These spend the
    winter in the field, so frost matters for them."""
    return int(c["sow_month"]) in (8, 9, 10, 11)


# Months a ley (perennial) is treated as actively growing, for its climate fit.
GROWING_SEASON_MONTHS = [4, 5, 6, 7, 8, 9]


def growing_season_temp(c, farm):
    """Mean air temperature over the months THIS crop is actively in the ground.

    EcoCrop's optimal temperature is a growing-cycle optimum, so comparing it with
    one farm-wide growing-season average put almost every UK crop just below its
    optimum and told the ranking little. Using each crop's own months (sowing to
    harvest, or the warm season for a ley) gives a fairer, more discriminating fit.

    Falls back to the farm-wide growing-season mean when no monthly profile is
    present (e.g. a minimal farm dict used in tests)."""
    monthly = farm.get("monthly_temp_c")
    if not monthly:
        return farm["growing_temp_c"]
    if is_perennial(c):
        months = GROWING_SEASON_MONTHS
    else:
        s, h = int(c["sow_month"]), int(c["harvest_month"])
        months = [s] + months_between(s, h) + [h]
    temps = [monthly[m - 1] for m in months if 1 <= m <= 12 and pd.notna(monthly[m - 1])]
    return round(sum(temps) / len(temps), 1) if temps else farm["growing_temp_c"]


def sown_into_frost(c, farm):
    """True if the crop is sown on or before the farm's typical last spring frost,
    so its seedlings can actually meet frost. Crops sown after the last frost has
    passed are not flagged. Falls back to True (keep the check) when the farm has
    no frost date."""
    date = farm.get("median_last_spring_frost")
    if not date:
        return True
    try:
        last_frost_month = int(str(date).split("-")[0])
    except (ValueError, IndexError):
        return True
    return int(c["sow_month"]) <= last_frost_month


# =============================================================================
# STEP A: SUITABILITY - can this crop grow here at all?
# =============================================================================

def suitability(c, farm, check_frost=True):
    """Compare one crop's climate needs (from FAO EcoCrop) with the farm's climate.

    check_frost=False skips the simple frost check (step 4) because the daily
    frost index in crop_climate() is used instead.

    Returns (level, notes) where level is:
        "unsuitable"  outside the range the crop can survive -> never recommended
        "possible"    can grow, but not in its ideal climate, or frost risk -> warning
        "ideal"       inside the crop's optimal range
        "unknown"     EcoCrop has no climate data for this crop -> warning

    EcoCrop gives two ranges per crop:
        absolute range  (rain_abs_min/max, temp_abs_min/max): the crop can survive
        optimal range   (rain_opt_min/max, temp_opt_min/max): the crop grows best
    """
    if any(pd.isna(c[k]) for k in CLIMATE_COLUMNS):
        return "unknown", ["missing from EcoCrop, so its climate fit can't be checked"]

    notes = []

    # 1. Rainfall: outside the survivable range -> unsuitable
    #    (EcoCrop rainfall is per year, so we compare with the farm's yearly total)
    rain = farm["annual_rain_mm"]
    if not (c["rain_abs_min_mm"] <= rain <= c["rain_abs_max_mm"]):
        return "unsuitable", [f"rainfall {rain} mm is outside its survivable range"]

    # 2. Temperature: outside the survivable range -> unsuitable
    t = farm["growing_temp_c"]
    if not (c["temp_abs_min_c"] <= t <= c["temp_abs_max_c"]):
        return "unsuitable", [f"growing-season temperature {t} °C is outside its range"]

    # 3. Is it inside the OPTIMAL range for both rain and temperature?
    #    Temperature is taken over THIS crop's own growing months, not one farm-wide
    #    average, so the fit actually separates warm- and cool-season crops. Rainfall
    #    stays annual, because EcoCrop's rain range is a yearly total. The survivable
    #    check in step 2 keeps using the farm-wide mean, so this can never newly ban a
    #    crop, only move it between "ideal" and "possible".
    t_crop = growing_season_temp(c, farm)
    ideal = (c["rain_opt_min_mm"] <= rain <= c["rain_opt_max_mm"]) and \
            (c["temp_opt_min_c"] <= t_crop <= c["temp_opt_max_c"])
    if not ideal:
        notes.append(f"not in its ideal climate here (its growing months average "
                     f"{t_crop:g} °C)")

    # 4. Frost (only for crops that spend the winter in the field).
    #    EcoCrop gives ONE killing temperature per species, but many UK varieties
    #    are hardier (e.g. EcoCrop says barley dies at -4 °C, but UK winter barley
    #    survives colder). So frost is only a WARNING ("possible"), never a ban.
    kill = c["killing_temp_dormant_c"]
    if check_frost and (is_winter_sown(c) or is_perennial(c)) and pd.notna(kill) \
            and farm["coldest_temp_c"] < kill:
        ideal = False
        notes.append(f"at frost risk (winters reach {farm['coldest_temp_c']} °C, "
                     f"EcoCrop limit {kill} °C; choose a hardy variety)")

    return ("ideal" if ideal else "possible"), notes


# =============================================================================
# CROP CALENDAR - which months is the soil bare?
# =============================================================================
#
# HOW A ROTATION IS STORED
# A rotation is a list of "steps". Each step is a pair:
#     (main crop, cover crop or None)
# The cover crop (if any) is grown in the gap AFTER the main crop.
# Example:
#     [("Winter wheat", "Rye (cover)"),            # wheat, then rye over winter
#      ("Spring oats", None),                       # oats, no cover crop
#      ("Spring peas", None)]                       # peas, then back to wheat
#
# The rotation REPEATS, so the last crop is followed by the first one again.
# =============================================================================

def cover_window(cover, crops):
    """All the months a cover crop is in the ground, from sowing to destruction.
    Example: rye sown Sep (9), destroyed Feb (2) -> [9, 10, 11, 12, 1, 2]."""
    cv = crops[cover]
    s, e = int(cv["sow_month"]), int(cv["harvest_month"])  # for covers, "harvest" = destroyed
    return [s] + months_between(s, e) + [e]


def fits(cover, gap, crops, harvest=None, next_sow=None):
    """Does this cover crop fit in the bare gap between two main crops?

    It fits if every month it's in the ground is inside the gap. It may also be
    sown in the same month as the harvest (sown straight after harvest) and
    destroyed in the month the next crop is sown (destroyed just before sowing).
    """
    allowed = set(gap) | {harvest, next_sow}
    return bool(gap) and all(m in allowed for m in cover_window(cover, crops))


def bare_gap(cur, nxt):
    """Bare months between harvesting crop `cur` and sowing crop `nxt`.

    Returns (gap, late):
        gap   list of bare months
        late  True if the next crop must be sown late (see below)

    Special cases:
      - Leys (perennials) never leave the soil bare -> no gap.
      - A gap of 10+ months means the next crop's normal sowing month is BEFORE
        the previous harvest (e.g. maize harvested Oct, winter barley normally sown
        Sep). In practice the farmer sows late, straight after harvest, so we treat
        it as no gap but flag "late sowing" as a risk.
    """
    if is_perennial(cur) or is_perennial(nxt):
        return [], False
    gap = months_between(int(cur["harvest_month"]), int(nxt["sow_month"]))
    if len(gap) >= 10:
        return [], True
    return gap, False


def gaps(rotation, crops):
    """Go through the whole rotation and describe every gap between crops.

    For each step it returns a dictionary:
        after    the crop just harvested
        before   the next crop to be sown
        gap      the bare months in between
        cover    the cover crop chosen for this gap (or None)
        covered  the months the cover crop protects ([] if no cover,
                 None if the cover crop doesn't fit in this gap)
        late     True if the next crop has to be sown late
    """
    out = []
    for i, (main, cover) in enumerate(rotation):
        # the next crop; "% len" wraps round so the last crop is followed by the first
        nxt = crops[rotation[(i + 1) % len(rotation)][0]]
        cur = crops[main]
        gap, late = bare_gap(cur, nxt)

        covered = []
        if cover:
            if fits(cover, gap, crops, int(cur["harvest_month"]), int(nxt["sow_month"])):
                covered = [m for m in cover_window(cover, crops) if m in gap]
            else:
                covered = None  # the cover crop does not fit in this gap

        out.append({"after": main, "before": nxt["crop"], "gap": gap,
                    "cover": cover, "covered": covered, "late": late})
    return out


def cover_conflict(cover, next_crop, rotation_crops, crops, prev_crop=None):
    """Check whether a cover crop clashes with the crops around it.

    A cover crop is good for the soil, but the WRONG cover crop can carry pests
    and diseases to the next crop. Returns (penalty, reason), or (0, None) if fine.

    Rules:
      - brassica cover (e.g. mustard) in a rotation with oilseed rape -> clubroot risk
      - legume cover (e.g. vetch) next to a legume crop (peas, beans)  -> shared root diseases
      - cereal cover (e.g. rye) before a cereal crop                   -> pests, diseases and
        lower yield (AHDB Maxi Cover Crop project: oats or rye before a spring cereal
        can reduce its yield)
    """
    cv, nx = crops[cover], crops[next_crop]
    if cv["family"] == "brassica" and any(crops[c]["family"] == "brassica" for c in rotation_crops):
        return -2, f"{cover} is a brassica like oilseed rape: it can carry clubroot into the rotation."
    if cv["n_fixing"] == "yes" and nx["n_fixing"] == "yes":
        return -2, f"{cover} is a legume before {next_crop}, also a legume: shared root diseases."
    if prev_crop and cv["n_fixing"] == "yes" and crops[prev_crop]["n_fixing"] == "yes":
        return -2, f"{cover} is a legume after {prev_crop}, also a legume: shared root diseases."
    if cv["family"] == "cereal" and nx["family"] == "cereal":
        return -2, (f"{cover} before {next_crop} is cereal before cereal: "
                    f"it can carry pests and diseases over and reduce yield.")
    return 0, None

# =============================================================================
# CROP CLIMATE INDICES - heat stress and frost for ONE crop at this farm
# =============================================================================
#
# These need a crop's own numbers (heat threshold, flowering months, killing
# temperature, sowing month), so they are computed here from the DAILY weather,
# not stored as columns in the climate files. That also lets the what-if
# "warming" slider shift the temperatures and recompute instantly.
# =============================================================================

def parse_months(text):
    """Turn "6;7" from heat_thresholds.csv into [6, 7] (blank -> [])."""
    if pd.isna(text):
        return []
    return [int(m) for m in re.split(r"[;,\s]+", str(text).strip()) if m]


def heat_indices_by_year(tmax, th, months):
    """Heat stress per year for one crop.

    tmax: daily Series with a date index (t2m_max). th: crop threshold in °C.
    months: the crop's sensitive months (flowering / grain fill), e.g. [6, 7].

    Returns one row per year:
        adhs_days  ADHS, accumulated days of heat stress: days with Tmax >= th
        hsi_c      HSI, heat stress intensity: average Tmax on those days
                   (NaN in a year with no hot days)
        hdd_cd     HDD, heat degree days: sum of (Tmax - th) over the days above th
    """
    t = tmax[tmax.index.month.isin(months)]
    year = t.index.year
    hot = t.where(t >= th)                                  # NaN on days below the threshold
    return pd.DataFrame({
        "adhs_days": hot.groupby(year).count(),
        "hsi_c":     hot.groupby(year).mean(),
        "hdd_cd":    (t - th).clip(lower=0).groupby(year).sum(),
    })


def crop_climate(c, weather, warming_c=0.0):
    """Heat stress and frost indices for one crop, from the daily weather.

    warming_c adds that many °C to every day (the what-if slider).

    Returns a dictionary with any of these (missing if the crop has no threshold):
        heat          ADHS / HSI / HDD averages over all years and the recent years
        winter_frost  % of winters with a night below the crop's dormant killing
                      temperature (winter-sown crops and leys)
        spring_frost  % of years with a night below the crop's growing killing
                      temperature in the sowing month and the month after (spring crops)
    """
    out = {}
    tmax, tmin = weather["t2m_max"] + warming_c, weather["t2m_min"] + warming_c
    last_year = weather.index.year.max()

    # --- heat stress at flowering --------------------------------------------
    months = parse_months(c["heat_months"])
    if pd.notna(c["heat_threshold_c"]) and months:
        th = float(c["heat_threshold_c"])
        by_year = heat_indices_by_year(tmax, th, months)
        recent = by_year[by_year.index > last_year - RECENT_YEARS]
        out["heat"] = {
            "threshold_c": th, "months": months, "confidence": c["heat_confidence"],
            "recent_period": f"{recent.index.min()}-{recent.index.max()}",
            "adhs_days": by_year["adhs_days"].mean(),
            "adhs_recent_days": recent["adhs_days"].mean(),
            "hdd_recent_cd": recent["hdd_cd"].mean(),
            "hsi_recent_c": recent["hsi_c"].mean(),         # NaN if no hot days at all
            "stress_years_pct": (by_year["adhs_days"] > 0).mean() * 100,
        }

    # --- winter kill (crop in the field over winter) -------------------------
    kill = c["killing_temp_dormant_c"]
    if (is_winter_sown(c) or is_perennial(c)) and pd.notna(kill):
        # winter-sown: from sowing to the end of March; leys: Nov-Mar;
        # cover crops: only while in the ground (sowing to destruction)
        start = int(c["sow_month"]) if is_winter_sown(c) else 11
        end = int(c["harvest_month"]) if c["role"] == "cover" else 3
        window = [start] + months_between(start, end) + [end]
        window = [m for m in window if m in (8, 9, 10, 11, 12, 1, 2, 3)]   # winter months only
        cold = tmin[tmin.index.month.isin(window)]
        # a winter belongs to the year it ends in (Oct 2010 - Mar 2011 -> 2011);
        # keep only winters fully inside the data
        season = cold.index.year + (cold.index.month >= 7)
        seasons = range(weather.index.year.min() + 1, last_year + 1)
        hit = (cold < kill).groupby(season).any().reindex(seasons, fill_value=False)
        out["winter_frost"] = {"kill_c": float(kill), "months": window,
                               "years_pct": hit.mean() * 100, "n_winters": len(hit)}

    # --- late frost after sowing (spring crops) ------------------------------
    kill_g = c["killing_temp_growing_c"]
    if not is_winter_sown(c) and not is_perennial(c) and pd.notna(kill_g):
        sow = int(c["sow_month"])
        window = [sow, sow % 12 + 1]
        cold = tmin[tmin.index.month.isin(window)]
        hit = (cold < kill_g).groupby(cold.index.year).any()
        out["spring_frost"] = {"kill_c": float(kill_g), "months": window,
                               "years_pct": hit.mean() * 100}

    return out


# =============================================================================
# COMPARING ROTATIONS - how different is a rotation from the farmer's current one?
# =============================================================================
#
# A rotation is a CYCLE: wheat -> maize -> barley -> wheat -> ... So
# "wheat, maize, barley" and "maize, barley, wheat" are the same rotation,
# just started in a different year.
# =============================================================================

def same_cycle(a, b):
    """True if rotation a is rotation b started in a different year.
    same_cycle(["W", "M", "B"], ["M", "B", "W"]) -> True"""
    return len(a) == len(b) and any(list(a) == list(b[i:]) + list(b[:i]) for i in range(len(b)))


def count_changes(names, current):
    """How many changes the farmer would make to go from `current` to `names`.

    Counts crops, not positions:
        swap one crop for another     -> 1   (one in, one out)
        add one crop (longer rotation) -> 1
        drop one crop                  -> 1
        same crops in a new order      -> 0.5 (a small change, but still one)
        same rotation, started in a different year -> 0
    """
    added = sum((Counter(names) - Counter(current)).values())
    removed = sum((Counter(current) - Counter(names)).values())
    changed = max(added, removed)
    if changed == 0 and not same_cycle(names, current):
        changed = 0.5
    return changed


def canonical(seq, current):
    """Pick ONE way of writing a rotation, so the same cycle isn't scored twice.
    Starts with the farmer's first crop if it's in there (so it reads like
    their own plan), otherwise with the alphabetically first start."""
    turns = [tuple(seq[i:]) + tuple(seq[:i]) for i in range(len(seq))]
    own = [t for t in turns if current and t[0] == current[0]]
    return min(own) if own else min(turns)


# =============================================================================
# STEPS B + C: SCORING A ROTATION
# =============================================================================

def score(rotation, farm, crops, prio, successors, current=None, climate=None, suit=None,
          water="rain_only", soil="not_sure"):
    """Score one rotation and explain the score.

    Points are collected in separate "buckets" (soil, water, fertility...), so we
    can see where a score comes from and weight each bucket by the farmer's
    priorities at the end.

    Every rule that adds or removes points also writes a sentence into one of:
        benefits  good things about this rotation
        risks     problems the farmer should know about
        reasons   other notes (e.g. "no nitrogen-fixing crop")
        checks    things a local advisor should confirm

    Arguments:
        rotation    list of (main crop, cover crop or None) steps
        farm        the farm's climate (from load_farm(), see farm_climate_summary.json)
        crops       from load_crops()
        prio        farmer priorities, 0 (doesn't matter) to 3 (high), e.g.
                    {"soil": 3, "water": 2, "fertility": 2, "income": 2,
                     "forage": 0, "organic_matter": 2}
        successors  from load_successors()
        current     the farmer's current crops (to penalise big changes); None to skip
        climate     crop name -> crop_climate() result; None to skip the heat and
                    daily-frost rules (the simple frost check in suitability() is used)
        suit        crop name -> suitability() result, worked out once in recommend()
                    so it isn't recomputed for every rotation; None to compute here
        water       the farmer's water source: a key of WATER_SOURCES
        soil        the farmer's soil type: a key of SOIL_TYPES
    """
    pts = {"soil": 0, "water": 0, "fertility": 0, "forage": 0, "organic_matter": 0,
           "sequence": 0, "income": 0, "climate": 0, "change": 0}
    reasons, benefits, risks, checks = [], [], [], []
    fitted_covers = []                        # cover crops that fit their gap (for organic matter)
    mains = [crops[m] for m, _ in rotation]   # the main crops' rows from load_crops()
    names = [m for m, _ in rotation]          # just the main crop names

    # -------------------------------------------------------------------------
    # RULE B1 / B2: bare soil in the wettest months -> erosion
    # Bare soil in heavy rain gets washed away. Every bare month that falls in the
    # farm's wettest months loses points. A cover crop that protects the soil in
    # those months gains points.
    # -------------------------------------------------------------------------
    for g in gaps(rotation, crops):

        # Late sowing (next crop sown straight after a late harvest): yield risk
        if g["late"]:
            pts["climate"] -= 2
            risks.append(f"{g['before']} has to be sown late, straight after the "
                         f"{g['after']} harvest: lower yield risk.")

        # A cover crop that doesn't fit in this gap: just report it
        if g["covered"] is None:
            risks.append(f"{g['cover']} does not fit between {g['after']} and {g['before']}.")
            continue

        # Bare months = gap months NOT protected by a cover crop
        bare = [m for m in g["gap"] if m not in g["covered"]]
        bare_wet = [m for m in bare if m in farm["wet_months"]]
        if bare_wet:
            # light soils (sandy, silty) wash and blow away more easily: a bigger penalty
            light = soil in LIGHT_SOILS
            per_month = LIGHT_SOIL_BARE_WET_POINTS if light else BARE_WET_MONTH_POINTS
            pts["soil"] += per_month * len(bare_wet)
            risks.append(f"Soil is bare in {month_names(bare_wet)} after {g['after']}, "
                         f"the wettest months here: erosion risk"
                         + (f", higher on {soil} soil." if light else "."))

        # A cover crop in this gap
        if g["cover"] and g["covered"]:
            fitted_covers.append(g["cover"])
            # ...but first check it doesn't clash with neighbouring crops
            penalty, why = cover_conflict(g["cover"], g["before"], names, crops, g["after"])
            if penalty:
                pts["sequence"] += penalty
                risks.append(why)
            # ...and reward it if it protects the soil in the wet months
            saved = [m for m in g["covered"] if m in farm["wet_months"]]
            if saved:
                pts["soil"] += 3
                benefits.append(f"{g['cover']} protects the soil after {g['after']} "
                                f"during {month_names(saved)}.")
                if crops[g["cover"]]["n_fixing"] == "yes":   # legume covers add nitrogen too
                    pts["fertility"] += 1
                    benefits.append(f"{g['cover']} also adds nitrogen.")

    # -------------------------------------------------------------------------
    # RULE B2b: a ley keeps the soil covered all year
    # A cover crop earns +3 for protecting the soil through one wet season. A ley
    # does the same every year it is in the ground, so it earns +3 per year.
    # -------------------------------------------------------------------------
    for c in mains:
        if c["role"] == "forage" and is_perennial(c):
            pts["soil"] += 3 * int(c["years"])
            benefits.append(f"{c['crop']} keeps the soil covered all year for "
                            f"{int(c['years'])} years: no bare soil in the wet months.")

    # -------------------------------------------------------------------------
    # RULE B3: a nitrogen-fixing crop (legume)
    # Legumes (beans, peas, clover) take nitrogen from the air and leave it in the
    # soil, so the next crop needs less fertiliser.
    # -------------------------------------------------------------------------
    legumes = [c["crop"] for c in mains if c["n_fixing"] == "yes"]
    if legumes:
        pts["fertility"] += 3
        benefits.append(f"{legumes[0]} fixes nitrogen from the air, "
                        f"so the next crop needs less fertiliser.")
    else:
        reasons.append("No nitrogen-fixing crop in the rotation.")

    # -------------------------------------------------------------------------
    # RULE B4: successor crop matrix - how well does each crop follow the one before?
    # Looks up every "crop B after crop A" pair in successor_matrix.csv
    # (-3 = bad, +3 = good). The rotation repeats, so the last crop is also
    # checked against the first.
    # Good pairs (+2, +3) are shown as benefits, bad pairs (-2, -3) as risks,
    # and slightly bad pairs (-1) as things to check.
    # -------------------------------------------------------------------------
    for i, prev in enumerate(names):
        nxt = names[(i + 1) % len(names)]
        s, why = successors.get((prev, nxt), (0, "no strong effect known"))
        pts["sequence"] += s
        if s >= 2:
            benefits.append(f"{nxt} after {prev}: {why}.")
        elif s <= -2:
            risks.append(f"{nxt} after {prev}: {why}.")
        elif s == -1:
            checks.append(f"{nxt} after {prev}: {why}.")

    # -------------------------------------------------------------------------
    # RULE B4b: how often a sensitive crop family comes back to the same field
    # The successor matrix only checks NEIGHBOURING crops. This rule checks the
    # whole rotation: e.g. peas every 2 years is far too often (5+ is advised).
    #   every = rotation length in YEARS / number of times the family appears
    # Example: a 4-year rotation with peas twice -> peas every 2 years.
    # The length is in years, not crops: a 3-year ley makes the rotation 2 years
    # longer than its number of crops (see rotation_years).
    # Legume and brassica cover crops count too, because they carry the same diseases.
    # -------------------------------------------------------------------------
    years = rotation_years(names, crops)
    fams = [crops[n]["family"] for n in names]
    for _, cv in rotation:
        if cv and crops[cv]["family"] in ("legume", "brassica"):
            fams.append(crops[cv]["family"])
    for fam_name, (min_years, why) in MIN_YEARS_BETWEEN.items():
        k = fams.count(fam_name)
        if k == 0:
            continue
        every = years / k
        if every < min_years:
            # Twice in one rotation, or far too often: a heavy penalty (-8), a near-ban.
            # Once in a slightly too short rotation: a small penalty (up to -3), a warning.
            short = 8 if (k >= 2 or every <= min_years / 2) else min(3, round(min_years - every))
            pts["sequence"] -= short
            line = (f"{fam_name.capitalize()} crops come back every {every:g} year(s) here; "
                    f"at least {min_years} years is advised because {why}.")
            (risks if short >= 2 else checks).append(line)

    # -------------------------------------------------------------------------
    # CHANGE PENALTY: farmers prefer small, practical changes
    # -1 for every crop swapped in or added, so the model doesn't suggest
    # throwing the whole farm plan away for a tiny gain (see count_changes).
    # -------------------------------------------------------------------------
    if current:
        pts["change"] -= count_changes(names, current)

    # -------------------------------------------------------------------------
    # RULE B5 / B6: water
    # Only applies if NASA data shows summers getting drier at this farm.
    # Thirsty crops lose points; drought-tolerant or low-water crops gain points.
    # Each crop gets ONE water result (the strongest that applies), so a crop
    # that is both drought-tolerant and low-water isn't rewarded twice.
    #
    # The farmer's WATER SOURCE changes the points (THIRSTY_CROP_POINTS):
    #   rain only        thirsty crop -3   (nothing to fall back on in a dry summer)
    #   some irrigation  thirsty crop -1   (dry spells can be covered)
    #   fully irrigated  thirsty crop  0   (but flagged: it depends on the irrigation)
    # -------------------------------------------------------------------------
    for c in mains if farm["summer_drying"] else []:
        if c["water_need"] == "high":
            p = THIRSTY_CROP_POINTS[water]
            pts["water"] += p
            if water == "some_irrigation":
                risks.append(f"{c['crop']} needs a lot of water and summers here are getting "
                             f"drier: it will rely on your irrigation in dry spells.")
            elif p:
                risks.append(f"{c['crop']} needs a lot of water and summers here are getting drier.")
        elif c["drought_tolerance"] == "high":
            pts["water"] += DROUGHT_TOLERANT_POINTS[water]
            benefits.append(f"{c['crop']} copes well with dry spells.")
        elif c["water_need"] == "low":
            pts["water"] += 1
            benefits.append(f"{c['crop']} has a low water need.")

    # Full irrigation takes the drought risk away, but the crop now depends on it.
    thirsty = [c["crop"] for c in mains if c["water_need"] == "high"]
    if thirsty and water == "fully_irrigated":
        checks.append(f"{', '.join(thirsty)} {'depends' if len(thirsty) == 1 else 'depend'} "
                      f"on irrigation all season: check your "
                      f"abstraction licence, water supply in dry years and the cost.")

    # SOIL: sandy soil stores about half the water of a loam, so a thirsty crop
    # runs short sooner in the dry months, unless the field is fully irrigated.
    if soil == "sandy" and water != "fully_irrigated":
        for name in thirsty:
            pts["water"] += SANDY_THIRSTY_CROP_POINTS
            risks.append(f"{name} needs a lot of water, and sandy soil holds little of it "
                         f"through the dry months ({month_names(farm['dry_months'])}).")

    # -------------------------------------------------------------------------
    # RULE B7: deep-rooted crops improve soil structure and drainage
    # (worth an extra point on clay, which is heavy and drains slowly)
    # -------------------------------------------------------------------------
    deep = [c["crop"] for c in mains if c["root_depth"] == "deep"]
    if deep:
        pts["soil"] += 1 + (CLAY_DEEP_ROOT_POINTS if soil == "clay" else 0)
        benefits.append(f"Deep roots of {', '.join(deep)} improve soil structure and drainage"
                        + (", which matters most on clay." if soil == "clay" else "."))

    # -------------------------------------------------------------------------
    # RULE B7b: harvesting on clay in the wet months
    # Heavy machinery on wet clay compacts and smears it, and the damage lasts
    # into the next crop. Applies to crops harvested in the farm's wet months.
    # -------------------------------------------------------------------------
    if soil == "clay":
        for c in mains:
            if not is_perennial(c) and int(c["harvest_month"]) in farm["wet_months"]:
                pts["soil"] += CLAY_WET_HARVEST_POINTS
                risks.append(f"{c['crop']} is harvested in {MONTHS[int(c['harvest_month']) - 1]}, "
                             f"a wet month here: on clay this risks compaction and soil damage.")

    # Missing answers are information gaps: say so, don't guess silently.
    if water == "not_sure":
        reasons.append("Water source not given: scored as rain only (information gap).")
    if soil == "not_sure":
        reasons.append("Soil type not given: soil-specific rules were not applied (information gap).")

    # -------------------------------------------------------------------------
    # RULE B8: income - average market value per YEAR (0 to 3), times 3
    # (a 3-year ley counts three times, because it earns its value for three years)
    # -------------------------------------------------------------------------
    pts["income"] += round(
        sum(LEVEL[str(c["market_value"])] * int(c["years"]) for c in mains) / years * 3, 1)

    # -------------------------------------------------------------------------
    # RULE B8b: forage - how much of the rotation can feed livestock
    # Average forage value per YEAR (0 to 3), times 3: a 3-year ley counts three
    # times. Only matters if the farmer gives forage a priority above 0, i.e. has
    # livestock or a forage buyer (see STEP C); otherwise it scores but weighs nothing.
    # -------------------------------------------------------------------------
    pts["forage"] += round(
        sum(LEVEL[str(c["forage_value"])] * int(c["years"]) for c in mains) / years * 3, 1)
    wants_forage = prio.get("forage", 0) > 0
    feed = [c["crop"] for c in mains if LEVEL[str(c["forage_value"])] >= 2]
    if wants_forage and feed:
        benefits.append(f"{', '.join(feed)} can feed livestock (grazing, silage or hay).")
    elif wants_forage:
        reasons.append("No forage crop in the rotation, although animal feed matters to you.")

    # -------------------------------------------------------------------------
    # RULE B8c: organic matter - roots and residues returned to the soil
    # Average organic-matter level per YEAR (0 to 3), times 3. A cover crop that
    # fits its gap adds half a year's worth, because it only grows for part of one.
    # Leys score highest: years of roots and no ploughing.
    # -------------------------------------------------------------------------
    om = sum(LEVEL[str(c["organic_matter"])] * int(c["years"]) for c in mains)
    om += sum(LEVEL[str(crops[cv]["organic_matter"])] * 0.5 for cv in fitted_covers)
    pts["organic_matter"] += round(om / years * 3, 1)
    builders = [c["crop"] for c in mains if c["organic_matter"] == "high"]
    if builders:
        benefits.append(f"{', '.join(builders)} builds organic matter: years of roots "
                        f"and residues with no ploughing.")
    if fitted_covers:
        benefits.append("Cover crops add organic matter between the main crops.")
    if om / years < 1.5:
        reasons.append("Little crop residue returns to the soil in this rotation: "
                       "organic matter may fall over time.")

    # -------------------------------------------------------------------------
    # RULE B9: climate fit (Step A for every crop in the rotation)
    # Unsuitable crops get a big penalty; "possible" crops a small one plus a check.
    # -------------------------------------------------------------------------
    for c in mains:
        level, notes = (suit[c["crop"]] if suit is not None
                        else suitability(c, farm, check_frost=climate is None))
        if level == "unsuitable":
            pts["climate"] -= 10
            risks.append(f"{c['crop']} is unsuitable here: {notes[0]}.")
        elif level == "possible":
            pts["climate"] -= 1
            checks.append(f"{c['crop']} is {notes[0]}: check local experience.")
        elif level == "unknown":
            checks.append(f"{c['crop']} is {notes[0]}: check local experience.")

    # -------------------------------------------------------------------------
    # RULE B10 / B11: heat stress at flowering, and frost (daily NASA data)
    # Uses the crop_climate() indices, so only runs when they were computed.
    #   Heat:   ADHS in the recent years >= HEAT_RISK_DAYS -> -3 (risk); >= 1 -> -1 (check)
    #   Winter: killing frost -> WARNING ONLY, no points. EcoCrop gives one killing
    #           temperature per species, too harsh for hardy UK varieties (it would
    #           "kill" ryegrass, winter barley and winter peas most winters), so it
    #           would unfairly rank leys and winter crops down. Same no-points stance
    #           the climate-fit frost note already takes.
    #   Spring: frost after sowing in >= SPRING_FROST_CHECK_PCT % of years -> check only,
    #           and only for crops sown into the farm's frost window (see below),
    #           because young plants can often recover and EcoCrop's value is rough
    # -------------------------------------------------------------------------
    for c in mains if climate else []:
        cc = climate[c["crop"]]

        h = cc.get("heat")
        if not h:
            reasons.append(f"No heat-stress threshold found for {c['crop']}: "
                           f"information gap, heat risk not checked.")
        elif h["adhs_recent_days"] >= 1:
            line = (f"{c['crop']} had {h['adhs_recent_days']:.1f} days a year above "
                    f"{h['threshold_c']:g} °C in {month_names(h['months'])} ({h['recent_period']}), "
                    f"when it flowers: heat stress can cut yield "
                    f"(HDD {h['hdd_recent_cd']:.1f} °C·days a year, "
                    f"average {h['hsi_recent_c']:.1f} °C on those days; "
                    f"threshold confidence: {h['confidence']}).")
            if h["adhs_recent_days"] >= HEAT_RISK_DAYS:
                pts["climate"] -= 3
                risks.append(line)
            else:
                pts["climate"] -= 1
                checks.append(line)

        # Winter kill: a warning, never a points penalty. EcoCrop's single killing
        # temperature is too harsh for hardy UK varieties, so penalising it would
        # unfairly rank leys, winter barley and winter peas down (see rule note).
        f = cc.get("winter_frost")
        if f and f["years_pct"] > 0:
            often = ("most winters" if f["years_pct"] >= WINTER_KILL_RISK_PCT
                     else "some winters")
            checks.append(
                f"{c['crop']}: cold nights reach EcoCrop's killing temperature "
                f"({f['kill_c']:g} °C) in {f['years_pct']:.0f}% of winters ({often}), "
                f"but hardy UK varieties usually survive — choose a hardy variety "
                f"and check local experience.")

        # Spring frost: a check, no points, and only when the crop is actually sown
        # into the farm's frost window (crops sown after the last frost are not
        # flagged). A seedling-specific killing temperature would be better than
        # EcoCrop's rough 0 °C, but none is sourced yet.
        s = cc.get("spring_frost")
        if s and s["years_pct"] >= SPRING_FROST_CHECK_PCT and sown_into_frost(c, farm):
            last = farm.get("median_last_spring_frost")
            when = f" (last frost here is typically around {last})" if last else ""
            checks.append(f"{c['crop']}: frost below {s['kill_c']:g} °C in "
                          f"{month_names(s['months'])}, just after sowing, in "
                          f"{s['years_pct']:.0f}% of years{when}: check the sowing date.")

    # -------------------------------------------------------------------------
    # STANDARD LOCAL CHECKS
    # The model can't know everything (soil type, disease history, local markets),
    # so it always reminds the farmer to confirm these with a local expert.
    # The challenge asks for this: the tool supports, but doesn't replace, farmers.
    # -------------------------------------------------------------------------
    if legumes:
        checks.append("Check the field's history of legume diseases and local markets for pulses.")
    if any(c["role"] == "forage" for c in mains) and not wants_forage:
        checks.append("A ley only pays if there is livestock or a local forage buyer "
                      "(you gave animal feed no priority).")
    checks.append("Check soil type, drainage and equipment with your agronomist." if soil == "not_sure"
                  else "Check drainage, soil pH and equipment with your agronomist.")

    # -------------------------------------------------------------------------
    # STEP C: weight the buckets by the farmer's priorities and add them up.
    # The six farmer priorities from the challenge brief each weight one bucket:
    #   water use -> water            nitrogen fixing -> fertility
    #   erosion reduction -> soil     market suitability -> income
    #   forage value -> forage        organic matter improvement -> organic_matter
    # Each is 0 (doesn't matter) to 3 (high). Forage and organic matter count 0
    # if the caller leaves them out, so older calls give the same scores as before.
    # "sequence" (pests and diseases) always counts double: it matters on every farm.
    # -------------------------------------------------------------------------
    weights = {"soil": prio["soil"], "water": prio["water"], "fertility": prio["fertility"],
               "income": prio["income"], "forage": prio.get("forage", 0),
               "organic_matter": prio.get("organic_matter", 0),
               "sequence": 2, "climate": 1, "change": 1}
    total = round(sum(pts[k] * weights[k] for k in pts), 1)

    return {"score": total, "years": years, "points": pts, "reasons": reasons,
            "benefits": benefits, "risks": risks, "checks": checks}


# =============================================================================
# STEP D: BUILD CANDIDATE ROTATIONS AND PICK THE BEST
# =============================================================================

def usable_covers(farm, crops):
    """Cover crops the model may add: marked suggest = "yes" and able to grow here."""
    return [n for n, c in crops.items()
            if c["role"] == "cover" and c["suggest"] == "yes"
            and suitability(c, farm)[0] in ("ideal", "possible")]


def add_covers(rotation, farm, crops, covers=None):
    """Add the best cover crop into every gap where the soil would be bare in the
    farm's wet months. `covers` is the list of usable cover crops (worked out
    once by candidates()); None to work it out here.

    For each gap it looks at all cover crops that fit, and picks the best using
    (in order of importance):
        1. no clash with the neighbouring crops (see cover_conflict)
        2. covers the most wet months
        3. is a legume (adds free nitrogen)
    """
    if covers is None:
        covers = usable_covers(farm, crops)
    names = [m for m, _ in rotation]
    out = []
    for i, (main, _) in enumerate(rotation):
        nxt = rotation[(i + 1) % len(rotation)][0]
        gap, _ = bare_gap(crops[main], crops[nxt])
        wet_gap = [m for m in gap if m in farm["wet_months"]]
        best = None
        if wet_gap:   # only add a cover crop if the soil would be bare in wet months
            h, ns = int(crops[main]["harvest_month"]), int(crops[nxt]["sow_month"])
            options = [cv for cv in covers if fits(cv, gap, crops, h, ns)]
            # sort from best to worst using the three criteria above
            # (Python compares the tuples item by item; reverse=True puts the best first)
            options.sort(key=lambda cv: (cover_conflict(cv, nxt, names, crops, main)[0],
                                         len([m for m in cover_window(cv, crops) if m in wet_gap]),
                                         crops[cv]["n_fixing"] == "yes"),
                         reverse=True)
            best = options[0] if options else None
        out.append((main, best))
    return out


def candidates(current, farm, crops, suggest_leys=True):
    """Make all the rotations worth considering.

    suggest_leys=False stops the model adding NEW leys (grass, clover): a ley only
    pays with livestock or a forage buyer, so recommend() turns this off when the
    farmer gives animal feed no priority. A ley already in the rotation stays.

    Starting from the farmer's current rotation, it creates:
      A. same length:   every rotation that swaps ONE or TWO crops
      B. 1 year longer: add one BREAK crop anywhere, to the current rotation or
                        to a rotation with one crop swapped
      C. 2 years longer: add two break crops anywhere to the current rotation
    using any cash or forage crop that can grow in this climate. Break crops are
    the non-cereals (legumes, brassicas, potatoes, beet, leys, vegetables): they
    are what a longer rotation is for, e.g. room for peas only every 5 years.
    Rotations never get longer than MAX_ROTATION_YEARS, counted in years (a ley
    takes 3), unless the farmer's own rotation is already longer.

    Crops marked suggest = "no" in crop_practices.csv (fruit, and crops with no
    EcoCrop data) are never swapped in, but can still be in the current rotation.
    Each rotation is tried twice: without cover crops and with cover crops added.
    The same cycle written from a different starting year is only scored once.
    """
    swaps = [n for n, c in crops.items()
             if c["role"] in ("cash", "forage") and c["suggest"] == "yes"
             and (suggest_leys or c["role"] != "forage")
             and suitability(c, farm)[0] in ("ideal", "possible")]
    breaks = [n for n in swaps if crops[n]["family"] != "cereal"]
    n = len(current)

    def insert(seq, pos, crop):
        """seq with `crop` added before position pos (pos = len(seq) is the
        same cycle as pos = 0, so positions 0 .. len-1 cover every place)."""
        return tuple(seq[:pos]) + (crop,) + tuple(seq[pos:])

    # A. swap one or two crops (same length)
    one_swap = set()
    seqs = {tuple(current)}
    for i in range(n):                       # change crop i...
        for s in swaps:
            one = list(current)
            one[i] = s
            one_swap.add(tuple(one))
            for j in range(i + 1, n):        # ...and optionally crop j as well
                for t in swaps:
                    two = list(one)
                    two[j] = t
                    seqs.add(tuple(two))
    seqs |= one_swap

    # B. one year longer: add a break crop (to the current or a one-swap rotation)
    if n + 1 <= MAX_ROTATION_YEARS:
        for base in {tuple(current)} | one_swap:
            for pos in range(n):
                for b in breaks:
                    seqs.add(insert(base, pos, b))

    # C. two years longer: add two break crops to the current rotation
    if n + 2 <= MAX_ROTATION_YEARS:
        for p in range(n):
            for b1 in breaks:
                longer = insert(current, p, b1)
                for q in range(n + 1):
                    for b2 in breaks:
                        seqs.add(insert(longer, q, b2))

    # the same cycle started in a different year is the same rotation: keep one
    seqs = {canonical(s, current) for s in seqs}

    # the cap is in YEARS: swapping in or adding a 3-year ley can push a rotation
    # past MAX_ROTATION_YEARS, so drop those (never below the farmer's own length)
    cap = max(MAX_ROTATION_YEARS, rotation_years(current, crops))
    seqs = {s for s in seqs if rotation_years(s, crops) <= cap}

    covers = usable_covers(farm, crops)
    cands = []
    for seq in sorted(seqs):   # sorted, so the order is the same every run
        base = [(c, None) for c in seq]            # without cover crops
        cands.append(base)
        with_covers = add_covers(base, farm, crops, covers)
        if with_covers != base:                    # with cover crops, if any were added
            cands.append(with_covers)
    return cands


def describe(rotation, crops=None):
    """Turn a rotation into readable text:
    "Winter wheat (+ Rye (cover)) → Red clover ley (3 years) → Spring peas".
    Pass `crops` to show how long multi-year crops stay."""
    def step(m, c):
        yrs = int(crops[m]["years"]) if crops else 1
        return m + (f" ({yrs} years)" if yrs > 1 else "") + (f" (+ {c})" if c else "")
    return " → ".join(step(m, c) for m, c in rotation)


def recommend(current, farm, priorities, crops, successors, weather=None, warming_c=0.0,
              water="rain_only", soil="not_sure"):
    """MAIN FUNCTION - this is what the web page (app.py) calls.

    Arguments:
        current     the farmer's current rotation, e.g. ["Winter wheat", "Maize", "Winter barley"]
        farm        the farm's climate, from load_farm() (or a small farm dict in tests)
        priorities  the six priorities in the brief, each 0 (doesn't matter) to 3 (high):
                    {"soil": 3, "water": 2, "fertility": 2, "income": 2,
                     "forage": 0, "organic_matter": 2}
                    soil = erosion reduction, fertility = nitrogen fixing, income = market;
                    forage and organic_matter may be left out (then they count 0)
        crops       from load_crops()
        successors  from load_successors()
        weather     daily NASA data from load_weather(); None skips heat stress and
                    the daily frost index
        warming_c   what-if slider: adds this many °C to the farm's temperatures
        water       the farmer's water source: "rain_only", "some_irrigation",
                    "fully_irrigated" or "not_sure" (see WATER_SOURCES)
        soil        the farmer's soil type: "sandy", "loamy", "silty", "clay" or
                    "not_sure" (see SOIL_TYPES)

    Returns a list of 3 dictionaries (current, Option A, Option B), each with:
        name, rotation (text), crops (list of steps), years (rotation length),
        score, points (per bucket), benefits, risks, reasons, checks
    If there aren't enough alternatives, the list is shorter (current + A, or
    just current) and the last item's "reasons" says why.

    Raises ValueError if a crop in `current` isn't in the crop table, listing
    the valid names (e.g. "Wheat" instead of "Winter wheat").
    """
    # Check the farmer's crop names first, so a typo gives a clear message
    # instead of a KeyError deep inside the scoring.
    unknown = [c for c in current if c not in crops]
    if unknown:
        raise ValueError(f"Unknown crop(s) in the current rotation: {unknown}. "
                         f"Valid names: {', '.join(sorted(crops))}")
    if not current:
        raise ValueError("The current rotation is empty: enter at least one crop.")
    if water not in WATER_SOURCES:
        raise ValueError(f"Unknown water source {water!r}. Valid: {', '.join(WATER_SOURCES)}")
    if soil not in SOIL_TYPES:
        raise ValueError(f"Unknown soil type {soil!r}. Valid: {', '.join(SOIL_TYPES)}")

    # 0. What-if warming: shift the farm's temperatures, and compute each crop's
    #    heat and frost indices ONCE (not once per candidate rotation)
    if warming_c:
        farm = {**farm, "growing_temp_c": farm["growing_temp_c"] + warming_c,
                "coldest_temp_c": farm["coldest_temp_c"] + warming_c}
    climate = None
    if weather is not None:
        climate = {name: crop_climate(c, weather, warming_c) for name, c in crops.items()}
    # each crop's climate fit, also worked out once
    suit = {name: suitability(c, farm, check_frost=climate is None) for name, c in crops.items()}

    # 1. Score the farmer's current rotation (no cover crops), to compare against
    current_rot = [(c, None) for c in current]
    cur = {"name": "Current rotation", "rotation": describe(current_rot, crops), "crops": current_rot,
           **score(current_rot, farm, crops, priorities, successors, current, climate, suit,
                   water, soil)}

    # 2. Score every candidate rotation (skipping the current one, in any starting year)
    scored = []
    #    New leys are only suggested if the farmer gives animal feed a priority.
    for rot in candidates(current, farm, crops, suggest_leys=priorities.get("forage", 0) > 0):
        if not any(cv for _, cv in rot) and same_cycle([m for m, _ in rot], current):
            continue
        scored.append({"rotation": describe(rot, crops), "crops": rot,
                       **score(rot, farm, crops, priorities, successors, current, climate, suit,
                               water, soil)})

    # 3. Sort from highest to lowest score.
    #    If two rotations have the SAME score, prefer the one with fewer changes
    #    from the current rotation, then alphabetical order. Without this, ties
    #    would be broken randomly and the answer could change between runs.
    scored.sort(key=lambda r: (-r["score"], -r["points"]["change"], r["rotation"]))

    # 4. Option A = the best overall.
    #    Option B = the best one using at least 2 crops that A doesn't (or at least 1
    #    if no such rotation exists), so the farmer sees two REAL choices, not the
    #    same crops in a different order.
    # Not enough alternatives (e.g. every other crop is unsuitable here):
    # return what we have, with a note, instead of crashing.
    if not scored:
        cur["reasons"].append("No alternative rotation could be built for this farm.")
        return [cur]
    a = scored[0]
    a["name"] = "Option A (best fit)"
    if len(scored) < 2:
        a["reasons"].append("Only one alternative rotation could be built, so there is no Option B.")
        return [cur, a]

    set_a = {m for m, _ in a["crops"]}
    b = next((r for r in scored[1:] if len({m for m, _ in r["crops"]} - set_a) >= 2),
             next((r for r in scored[1:] if {m for m, _ in r["crops"]} - set_a), scored[1]))
    a["name"], b["name"] = "Option A (best fit)", "Option B (alternative)"
    return [cur, a, b]


# =============================================================================
# TEST RUN - only runs when you type "python model.py"
# (not when app.py imports this file)
# =============================================================================
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")   # Windows consoles can't print "→" otherwise

    crops = load_crops()
    successors = load_successors()

    # The real farm climate from NASA POWER (build it first if the files are missing)
    if not (FARM_FILE.exists() and WEATHER_FILE.exists()):
        raise SystemExit(
            "No farm climate data found. Run scripts/climate/build_farm_climate.py "
            "to build it from NASA POWER first."
        )
    farm, weather = load_farm(), load_weather()
    print(f"Farm climate: NASA POWER {farm['years']} at {farm['latitude']}, {farm['longitude']}")

    # Change these to try different farmers:
    current = ["Winter wheat", "Maize", "Winter barley"]                  # names must match crop_practices.csv
    # the six priorities: 0 doesn't matter, 1 low, 2 normal, 3 high
    priorities = {"soil": 3, "water": 2, "fertility": 2, "income": 2,
                  "forage": 0,             # 0 = no livestock and no forage buyer
                  "organic_matter": 2}
    warming_c = 0.0                                                     # what-if: try 2.0
    water = "rain_only"      # "rain_only", "some_irrigation", "fully_irrigated", "not_sure"
    soil = "loamy"           # "sandy", "loamy", "silty", "clay", "not_sure"
    print(f"Water source: {WATER_SOURCES[water]}   Soil type: {SOIL_TYPES[soil]}")

    for r in recommend(current, farm, priorities, crops, successors, weather, warming_c,
                       water, soil):
        print("=" * 80)
        print(f"{r['name']} ({r['years']} years):  {r['rotation']}")
        print(f"Score: {r['score']}   {r['points']}")
        for label in ("benefits", "risks", "reasons", "checks"):
            for line in r[label]:
                print(f"  [{label[:-1]}] {line}")
