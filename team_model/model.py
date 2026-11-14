"""
=============================================================================
FIELD SHIFT - rule-based crop rotation model
NASA Space Apps Challenge 2026
=============================================================================

WHAT THIS FILE DOES
-------------------
It takes four things:
  1. the farm's climate        (from NASA POWER data, prepared by nasa_data.py)
  2. the crop table            (crops.csv: what each crop needs and offers)
  3. the farmer's rotation     (e.g. winter wheat -> maize -> winter barley)
  4. the farmer's priorities   (protect soil, save water, fertility, income)

and returns 3 crop rotations:
  - the farmer's CURRENT rotation, with its problems explained
  - OPTION A: the best-scoring alternative
  - OPTION B: a genuinely different alternative

Each rotation comes with a score plus plain-English benefits, risks and
"check locally" notes, so the farmer can see WHY it was suggested.

HOW IT WORKS (the big picture)
------------------------------
  Step A  Suitability   Can each crop grow in this climate at all?
                        (compares crops.csv climate ranges with the farm's NASA data)
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

INPUT FILES (in the "data" folder next to this file)
-------------------------------------------------------
  crops.csv             15 UK crops. Climate columns come from FAO EcoCrop;
                        rotation columns (sowing month, water need...) are UK estimates.
  successor_matrix.csv  A score from -3 (bad) to +3 (good) for every
                        "crop B after crop A" pair, with a one-line reason.

HOW TO RUN
----------
  pip install pandas
  python model.py
=============================================================================
"""
from pathlib import Path

import pandas as pd


# =============================================================================
# SETTINGS AND CONSTANTS
# =============================================================================

# Where the data files live: the "data" folder next to this file.
# Using the file's own location means it works from any folder you run it from.
DATA_DIR = Path(__file__).resolve().parent / "data"
CROPS_FILE = DATA_DIR / "crops.csv"
SUCCESSORS_FILE = DATA_DIR / "successor_matrix.csv"

# -----------------------------------------------------------------------------
# FAKE farm climate, used for testing until the real NASA data is connected.
# Person 1's code (nasa_data.py) must produce a dictionary with EXACTLY these
# keys, calculated from NASA POWER data for the farmer's location.
# Months are numbers: 1 = January ... 12 = December.
# -----------------------------------------------------------------------------
FAKE_FARM = {
    "annual_rain_mm": 850,           # average total rain per year (mm)
    "wet_months": [10, 11, 12, 1],   # the 4 wettest months at this farm
    "dry_months": [6, 7, 8],         # months where rain is less than evaporation
    "frost_months": [12, 1, 2],      # months with frost days on average
    "coldest_temp_c": -6,            # lowest winter temperature (°C)
    "growing_temp_c": 15,            # average temperature in the growing season (°C)
    "summer_drying": True,           # True if summer rain has fallen in recent years
    "heat_rising": True,             # True if hot days have increased in recent years
}

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

# Turns text levels from crops.csv into numbers, so we can do maths with them
# (used for market value: "high" = 3, "medium" = 2 ...).
LEVEL = {"none": 0, "low": 1, "medium": 2, "high": 3}


# =============================================================================
# LOADING THE DATA FILES
# =============================================================================

def load_crops(path=CROPS_FILE):
    """Read crops.csv and return a dictionary: crop name -> that crop's row.

    This lets the rest of the code look up a crop by name, e.g.
        crops["Maize"]["water_need"]   ->  "high"
    """
    crops = pd.read_csv(path)
    return {row["crop"]: row for _, row in crops.iterrows()}


def load_successors(path=SUCCESSORS_FILE):
    """Read successor_matrix.csv and return a dictionary:
        (previous crop, next crop) -> (score, reason)

    Example:
        successors[("Winter field beans", "Winter wheat")]
        -> (3, "beans leave nitrogen and break cereal diseases: a classic entry for wheat")
    """
    m = pd.read_csv(path)
    return {(r.previous_crop, r.next_crop): (int(r.score), r.reason) for r in m.itertuples()}


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
    if a == b:
        return []
    out, m = [], a % 12 + 1          # start from the month after a (Dec -> Jan wraps round)
    while m != b and len(out) < 12:  # keep going until we reach b (max 12 months, for safety)
        out.append(m)
        m = m % 12 + 1               # next month, wrapping Dec (12) -> Jan (1)
    return out


def is_perennial(c):
    """True for leys (grass, clover). They stay in the ground for several years,
    so in crops.csv their harvest_month is 0 and they never leave the soil bare."""
    return int(c["harvest_month"]) == 0


def is_winter_sown(c):
    """True for crops sown in late summer or autumn (Aug-Nov). These spend the
    winter in the field, so frost matters for them."""
    return int(c["sow_month"]) in (8, 9, 10, 11)


# =============================================================================
# STEP A: SUITABILITY - can this crop grow here at all?
# =============================================================================

def suitability(c, farm):
    """Compare one crop's climate needs (from FAO EcoCrop) with the farm's climate.

    Returns (level, notes) where level is:
        "unsuitable"  outside the range the crop can survive -> never recommended
        "possible"    can grow, but not in its ideal climate, or frost risk -> warning
        "ideal"       inside the crop's optimal range

    EcoCrop gives two ranges per crop:
        absolute range  (rain_abs_min/max, temp_abs_min/max): the crop can survive
        optimal range   (rain_opt_min/max, temp_opt_min/max): the crop grows best
    """
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
    ideal = (c["rain_opt_min_mm"] <= rain <= c["rain_opt_max_mm"]) and \
            (c["temp_opt_min_c"] <= t <= c["temp_opt_max_c"])
    if not ideal:
        notes.append("not in its ideal climate here")

    # 4. Frost (only for crops that spend the winter in the field).
    #    EcoCrop gives ONE killing temperature per species, but many UK varieties
    #    are hardier (e.g. EcoCrop says barley dies at -4 °C, but UK winter barley
    #    survives colder). So frost is only a WARNING ("possible"), never a ban.
    kill = c["killing_temp_dormant_c"]
    if (is_winter_sown(c) or is_perennial(c)) and pd.notna(kill) and farm["coldest_temp_c"] < kill:
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
#     [("Winter wheat", "Common vetch (cover)"),   # wheat, then vetch over winter
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
# STEPS B + C: SCORING A ROTATION
# =============================================================================

def score(rotation, farm, crops, prio, successors, current=None):
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
        farm        the farm's climate (same keys as FAKE_FARM)
        crops       from load_crops()
        prio        farmer priorities, e.g. {"soil": 3, "water": 2, "fertility": 2, "income": 2}
        successors  from load_successors()
        current     the farmer's current crops (to penalise big changes); None to skip
    """
    pts = {"soil": 0, "water": 0, "fertility": 0, "sequence": 0,
           "income": 0, "climate": 0, "change": 0}
    reasons, benefits, risks, checks = [], [], [], []
    mains = [crops[m] for m, _ in rotation]   # the main crops' rows from crops.csv
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
            pts["soil"] -= 2 * len(bare_wet)          # -2 per bare wet month
            risks.append(f"Soil is bare in {month_names(bare_wet)} after {g['after']}, "
                         f"the wettest months here: erosion risk.")

        # A cover crop in this gap
        if g["cover"] and g["covered"]:
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
    #   every = rotation length / number of times the family appears
    # Example: a 4-year rotation with peas twice -> peas every 2 years.
    # Legume and brassica cover crops count too, because they carry the same diseases.
    # -------------------------------------------------------------------------
    years = len(names)
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
    # -1 for every crop that differs from the current rotation, so the model
    # doesn't suggest throwing the whole farm plan away for a tiny gain.
    # -------------------------------------------------------------------------
    if current:
        changed = sum(1 for a, b in zip(names, current) if a != b) + abs(len(names) - len(current))
        pts["change"] -= changed

    # -------------------------------------------------------------------------
    # RULE B5 / B6: water
    # Only applies if NASA data shows summers getting drier at this farm.
    # Thirsty crops lose points; drought-tolerant and low-water crops gain points.
    # -------------------------------------------------------------------------
    for c in mains:
        if farm["summer_drying"] and c["water_need"] == "high":
            pts["water"] -= 3
            risks.append(f"{c['crop']} needs a lot of water and summers here are getting drier.")
        if farm["summer_drying"] and c["drought_tolerance"] == "high":
            pts["water"] += 2
            benefits.append(f"{c['crop']} copes well with dry spells.")
        if farm["summer_drying"] and c["water_need"] == "low":
            pts["water"] += 1
            benefits.append(f"{c['crop']} has a low water need.")

    # -------------------------------------------------------------------------
    # RULE B7: deep-rooted crops improve soil structure and drainage
    # -------------------------------------------------------------------------
    deep = [c["crop"] for c in mains if c["root_depth"] == "deep"]
    if deep:
        pts["soil"] += 1
        benefits.append(f"Deep roots of {', '.join(deep)} improve soil structure and drainage.")

    # -------------------------------------------------------------------------
    # RULE B8: income - average market value of the crops (0 to 3), times 3
    # -------------------------------------------------------------------------
    pts["income"] += sum(LEVEL[str(c["market_value"])] for c in mains) / len(mains) * 3

    # -------------------------------------------------------------------------
    # RULE B9: climate fit (Step A for every crop in the rotation)
    # Unsuitable crops get a big penalty; "possible" crops a small one plus a check.
    # -------------------------------------------------------------------------
    for c in mains:
        level, notes = suitability(c, farm)
        if level == "unsuitable":
            pts["climate"] -= 10
            risks.append(f"{c['crop']} is unsuitable here: {notes[0]}.")
        elif level == "possible":
            pts["climate"] -= 1
            checks.append(f"{c['crop']} is {notes[0]}: check local experience.")

    # -------------------------------------------------------------------------
    # STANDARD LOCAL CHECKS
    # The model can't know everything (soil type, disease history, local markets),
    # so it always reminds the farmer to confirm these with a local expert.
    # The challenge asks for this: the tool supports, but doesn't replace, farmers.
    # -------------------------------------------------------------------------
    if legumes:
        checks.append("Check the field's history of legume diseases and local markets for pulses.")
    if any(c["role"] == "forage" for c in mains):
        checks.append("A ley only pays if there is livestock or a local forage buyer.")
    checks.append("Check soil type, drainage and equipment with your agronomist.")

    # -------------------------------------------------------------------------
    # STEP C: weight the buckets by the farmer's priorities and add them up.
    # Soil, water, fertility and income use the farmer's sliders (1-3).
    # "sequence" (pests and diseases) always counts double: it matters on every farm.
    # -------------------------------------------------------------------------
    weights = {"soil": prio["soil"], "water": prio["water"], "fertility": prio["fertility"],
               "income": prio["income"], "sequence": 2, "climate": 1, "change": 1}
    total = round(sum(pts[k] * weights[k] for k in pts), 1)

    return {"score": total, "points": pts, "reasons": reasons,
            "benefits": benefits, "risks": risks, "checks": checks}


# =============================================================================
# STEP D: BUILD CANDIDATE ROTATIONS AND PICK THE BEST
# =============================================================================

def add_covers(rotation, farm, crops):
    """Add the best cover crop into every gap where the soil would be bare in the
    farm's wet months.

    For each gap it looks at all cover crops that fit, and picks the best using
    (in order of importance):
        1. no clash with the neighbouring crops (see cover_conflict)
        2. covers the most wet months
        3. is a legume (adds free nitrogen)
    """
    # only cover crops that can grow in this climate
    covers = [n for n, c in crops.items()
              if c["role"] == "cover" and suitability(c, farm)[0] != "unsuitable"]
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


def candidates(current, farm, crops):
    """Make all the rotations worth considering.

    Starting from the farmer's current rotation, it creates:
      - every rotation that changes ONE crop
      - every rotation that changes TWO crops
    using any cash or forage crop that can grow in this climate.
    Each of these is tried twice: without cover crops and with cover crops added.

    For a 3-crop rotation this is a few hundred candidates, which takes well
    under a second to score.
    """
    swaps = [n for n, c in crops.items()
             if c["role"] in ("cash", "forage") and suitability(c, farm)[0] != "unsuitable"]

    # a set removes duplicates (e.g. the same rotation reached in two different ways)
    seqs = {tuple(current)}
    for i in range(len(current)):            # change crop i...
        for s in swaps:
            one = list(current)
            one[i] = s
            seqs.add(tuple(one))
            for j in range(i + 1, len(current)):   # ...and optionally crop j as well
                for t in swaps:
                    two = list(one)
                    two[j] = t
                    seqs.add(tuple(two))

    cands = []
    for seq in sorted(seqs):   # sorted, so the order is the same every run
        base = [(c, None) for c in seq]            # without cover crops
        cands.append(base)
        with_covers = add_covers(base, farm, crops)
        if with_covers != base:                    # with cover crops, if any were added
            cands.append(with_covers)
    return cands


def describe(rotation):
    """Turn a rotation into readable text:
    "Winter wheat (+ Common vetch (cover)) → Spring oats → Spring peas"."""
    return " → ".join(m + (f" (+ {c})" if c else "") for m, c in rotation)


def recommend(current, farm, priorities, crops, successors):
    """MAIN FUNCTION - this is what the web page (app.py) calls.

    Arguments:
        current     the farmer's current rotation, e.g. ["Winter wheat", "Maize", "Winter barley"]
        farm        the farm's climate (same keys as FAKE_FARM)
        priorities  e.g. {"soil": 3, "water": 2, "fertility": 2, "income": 2}  (1 low ... 3 high)
        crops       from load_crops()
        successors  from load_successors()

    Returns a list of 3 dictionaries (current, Option A, Option B), each with:
        name, rotation (text), crops (list of steps), score, points (per bucket),
        benefits, risks, reasons, checks
    """
    # 1. Score the farmer's current rotation (no cover crops), to compare against
    current_rot = [(c, None) for c in current]
    cur = {"name": "Current rotation", "rotation": describe(current_rot), "crops": current_rot,
           **score(current_rot, farm, crops, priorities, successors, current)}

    # 2. Score every candidate rotation
    scored = []
    for rot in candidates(current, farm, crops):
        if rot == current_rot:
            continue
        scored.append({"rotation": describe(rot), "crops": rot,
                       **score(rot, farm, crops, priorities, successors, current)})

    # 3. Sort from highest to lowest score.
    #    If two rotations have the SAME score, prefer the one with fewer changes
    #    from the current rotation, then alphabetical order. Without this, ties
    #    would be broken randomly and the answer could change between runs.
    scored.sort(key=lambda r: (-r["score"], -r["points"]["change"], r["rotation"]))

    # 4. Option A = the best overall.
    #    Option B = the best one using at least 2 crops that A doesn't (or at least 1
    #    if no such rotation exists), so the farmer sees two REAL choices, not the
    #    same crops in a different order.
    a = scored[0]
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
    crops = load_crops()
    successors = load_successors()

    # Change these to try different farmers:
    current = ["Winter wheat", "Maize", "Winter barley"]                  # names must match crops.csv
    priorities = {"soil": 3, "water": 2, "fertility": 2, "income": 2}   # 1 low, 2 normal, 3 high

    for r in recommend(current, FAKE_FARM, priorities, crops, successors):
        print("=" * 80)
        print(f"{r['name']}:  {r['rotation']}")
        print(f"Score: {r['score']}   {r['points']}")
        for label in ("benefits", "risks", "reasons", "checks"):
            for line in r[label]:
                print(f"  [{label[:-1]}] {line}")
