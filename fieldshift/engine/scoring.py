"""Criterion scores in [0, 1]. Six farmer goals — formulas in each docstring."""

from __future__ import annotations

from typing import Any

from fieldshift.engine.crops import crop_by_id
from fieldshift.engine.inputs_config import (
    LIMITED_IRRIGATION_ALLOWANCE,
    SOIL_AWC_REFERENCE_MM_PER_M,
    WATER_SOIL_BLEND,
    forage_goal_active,
)
from fieldshift.models import Confidence, PriorityWeights, ScoreSet, WaterAccess

MARKET_TIER = {"none": 0.0, "low": 0.3, "medium": 0.6, "high": 0.9}
ROOT_DEPTH = {"shallow": 0.35, "medium": 0.65, "deep": 1.0}

CRITERION_KEYS = (
    "water",
    "forage",
    "nitrogen",
    "erosion",
    "organic_matter",
    "market",
)


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def grace_groundwater_penalty(features: dict[str, Any]) -> float:
    """Documented GRACE/FO groundwater stress penalty ∈ [0, 0.25].

    penalty = min(0.25, −trend_cm_per_yr / 20) when trend < 0; else 0.
    """
    trend = features.get("grace_trend_cm_per_yr")
    if trend is None or trend >= 0:
        return 0.0
    return float(min(0.25, -float(trend) / 20.0))


def score_water(
    sequence: list[str],
    features: dict[str, Any],
    water_access: WaterAccess = "rainfed",
    *,
    soil_awc_mm_per_m: float = SOIL_AWC_REFERENCE_MM_PER_M,
) -> float:
    """Water score: crop demand vs effective rain, irrigation, soil AWC.

    For each non-cover crop::

        demand = Σ_season (Kc × ET0_month)
        rain_eff = 0.8 × Σ_season rain_best
        crop_score = rain_eff / max(demand, 1)

    Sequence score = mean(crop_score). Then soil storage blend and irrigation::

        soil_proxy = clip(AWC / 150)
        base = (1 − WATER_SOIL_BLEND) × mean + WATER_SOIL_BLEND × soil_proxy

    Rain only: no grace penalty.
    Some irrigation: +LIMITED_IRRIGATION_ALLOWANCE, half grace penalty.
    Fully irrigated: score irrigation need, full grace penalty when GRACE < 0.
    """
    from fieldshift.engine.crop_water import irrigation_requirement_mm

    cash = [c for c in sequence if crop_by_id(c)["type"] != "cover"]
    if not cash:
        crop_mean = 0.5
    else:
        scores = []
        for cid in cash:
            ir = irrigation_requirement_mm(cid, features)
            demand = max(ir["demand_mm"], 1.0)
            rain_eff = ir["rain_eff_mm"]
            scores.append(_clip01(rain_eff / demand))
        crop_mean = sum(scores) / len(scores)

    soil_proxy = _clip01(float(soil_awc_mm_per_m) / SOIL_AWC_REFERENCE_MM_PER_M)
    base = (1.0 - WATER_SOIL_BLEND) * crop_mean + WATER_SOIL_BLEND * soil_proxy
    penalty = grace_groundwater_penalty(features)

    if water_access == "irrigated":
        score = base - penalty
    elif water_access == "limited":
        score = base + LIMITED_IRRIGATION_ALLOWANCE - 0.5 * penalty
    else:
        score = base
    return _clip01(score)


def score_forage(sequence: list[str], *, active: bool) -> float:
    """Mean forage_value; returns 0 when Animal feed goal is Not important."""
    if not active or not sequence:
        return 0.0
    vals = [float(crop_by_id(c).get("forage_value") or 0.0) for c in sequence]
    return _clip01(sum(vals) / len(vals))


def score_nitrogen(sequence: list[str]) -> float:
    """Fraction of slots that are nitrogen-fixing legumes."""
    if not sequence:
        return 0.0
    nfix = sum(
        1.0 if crop_by_id(c).get("nitrogen_fixing") else 0.0 for c in sequence
    )
    return _clip01(nfix / len(sequence))


def score_organic_matter(sequence: list[str], features: dict[str, Any]) -> float:
    """Residue + root depth + cover months (former soil_health without N-fix).

    weights: residue 0.35, root 0.30, cover 0.35.
    Cover = 1 − (n_bare_months_eff / 12).
    """
    if not sequence:
        return 0.0
    residue = sum(
        float(crop_by_id(c)["residue_organic_matter"]) for c in sequence
    ) / len(sequence)
    root = sum(
        ROOT_DEPTH.get(crop_by_id(c)["root_depth"], 0.5) for c in sequence
    ) / len(sequence)
    bare_n = len(features.get("bare_months", {}).get("months") or [])
    cover_boost = sum(1 for c in sequence if crop_by_id(c)["type"] == "cover")
    bare_eff = max(0, bare_n - cover_boost)
    cover = 1.0 - bare_eff / 12.0
    return _clip01(0.35 * residue + 0.30 * root + 0.35 * cover)


def score_erosion(sequence: list[str], features: dict[str, Any]) -> float:
    """Ground cover during risk periods × (1 − slope/extreme factor)."""
    if not sequence:
        return 0.0
    cover = sum(
        0.5 * float(crop_by_id(c)["ground_cover"])
        + 0.5 * float(crop_by_id(c)["erosion_protection"])
        for c in sequence
    ) / len(sequence)
    risk = float(features.get("erosion_risk") or 0.0)
    return _clip01(cover * (1.0 - 0.6 * risk))


def score_pest_break(sequence: list[str]) -> float:
    """Family diversity score — used for benefit lines only, not ranking."""
    if not sequence:
        return 0.0
    families = [crop_by_id(c)["family"] for c in sequence]
    diversity = len(set(families)) / max(3.0, float(len(families)))
    penalty = 0.0
    for a, b in zip(families, families[1:], strict=False):
        if a == b:
            penalty += 0.15
    return _clip01(diversity - penalty)


def score_climate_fit(
    sequence: list[str],
    features: dict[str, Any],
    *,
    season_months: list[int] | None = None,
) -> float:
    """Climate fit for candidate filtering — not a ranked farmer goal."""
    rain_cv = features.get("rain", {}).get("rain_cv") or 0.2
    if season_months:
        from fieldshift.engine.features import season_window_climate

        win = season_window_climate(features.get("daily"), season_months)
        frost_free = win.get("frost_free_proxy_days")
        gdd_mean = win.get("gdd_mean")
        heat_days = win.get("heat_days_mean") or 0.0
        tmax_mean = win.get("tmax_mean")
    else:
        frost_free = features.get("frost_window", {}).get("frost_free_days")
        gdd_mean = features.get("gdd", {}).get("gdd_annual_mean")
        heat_days = features.get("gdd", {}).get("heat_days_mean") or 0.0
        tmax_mean = None
    margins = []
    for cid in sequence:
        c = crop_by_id(cid)
        if frost_free is not None and c["min_frost_free_days"]:
            need = float(c["min_frost_free_days"])
            if season_months:
                need = need * (len(season_months) / 12.0)
            margins.append(_clip01((frost_free - need) / max(need, 1.0)))
        elif c["min_frost_free_days"] == 0:
            margins.append(1.0)
        if gdd_mean is not None and c["gdd_required"]:
            need_gdd = float(c["gdd_required"])
            if season_months:
                need_gdd = need_gdd * (len(season_months) / 12.0)
            margins.append(_clip01(gdd_mean / max(need_gdd, 1.0)))
        heat_load = min(1.0, heat_days / 20.0)
        margins.append(_clip01(float(c["heat_tolerance"]) * (1.0 - 0.5 * heat_load)))
        if tmax_mean is not None and c["season"] == "cool" and tmax_mean > 32:
            margins.append(_clip01(float(c["heat_tolerance"]) * 0.2))
        if tmax_mean is not None and c["season"] == "warm" and tmax_mean < 18:
            margins.append(0.2)
        margins.append(_clip01(float(c["drought_tolerance"]) * (1.0 - min(1.0, rain_cv))))
    if not margins:
        return 0.5
    return _clip01(sum(margins) / len(margins))


def score_market(sequence: list[str]) -> float:
    """Relative market tier of non-cover crops (crops.json market_tier)."""
    if not sequence:
        return 0.0
    cash = [c for c in sequence if crop_by_id(c)["type"] != "cover"]
    if not cash:
        return 0.0
    tiers = [MARKET_TIER.get(crop_by_id(c)["market_tier"], 0.3) for c in cash]
    return _clip01(sum(tiers) / len(tiers))


def score_strategy(
    sequence: list[str],
    features: dict[str, Any],
    *,
    weights: PriorityWeights | None = None,
    water_access: WaterAccess = "rainfed",
    soil_awc_mm_per_m: float = SOIL_AWC_REFERENCE_MM_PER_M,
    goal_importance: dict[str, int] | None = None,
    soft_penalty: float = 0.0,
) -> ScoreSet:
    """Weighted total over the six goals. Forage is 0 unless goal is active."""
    weights = weights or PriorityWeights()
    forage_on = forage_goal_active(goal_importance)
    scores = {
        "water": score_water(
            sequence,
            features,
            water_access,
            soil_awc_mm_per_m=soil_awc_mm_per_m,
        ),
        "forage": score_forage(sequence, active=forage_on),
        "nitrogen": score_nitrogen(sequence),
        "erosion": score_erosion(sequence, features),
        "organic_matter": score_organic_matter(sequence, features),
        "market": score_market(sequence),
    }
    w = weights.model_dump()
    # If forage goal inactive, force weight 0 so it cannot affect ranking.
    if not forage_on:
        w["forage"] = 0.0
    total_w = sum(float(w.get(k, 0.0)) for k in scores)
    if total_w <= 0:
        equal = 1.0 / len(scores)
        total = sum(equal * scores[k] for k in scores)
    else:
        total = sum(float(w.get(k, 0.0)) * scores[k] for k in scores) / total_w
    total = _clip01(total - float(soft_penalty or 0.0))
    return ScoreSet(**scores, total=float(total))


def confidence_label(
    features: dict[str, Any],
    scores: list[ScoreSet],
    sequence_ids: list[list[str]],
    *,
    input_penalty: bool = False,
) -> Confidence:
    """high/medium/low from coverage, expert-review flags, score separation, inputs."""
    from fieldshift.engine.crops import crop_by_id

    cov = features.get("data_coverage", {}).get("per_variable") or []
    if cov:
        rates = []
        for row in cov:
            n = row.get("n_valid", 0) + row.get("n_gaps", 0)
            if n:
                rates.append(row.get("n_valid", 0) / n)
        coverage = float(sum(rates) / len(rates)) if rates else 0.5
    else:
        coverage = 0.5
    review = any(
        crop_by_id(cid).get("needs_expert_review")
        for seq in sequence_ids
        for cid in seq
    )
    if len(scores) >= 2:
        totals = sorted([s.total for s in scores], reverse=True)
        separation = totals[0] - totals[1]
    else:
        separation = 0.1
    if coverage >= 0.85 and separation >= 0.05 and not review and not input_penalty:
        return "high"
    if coverage >= 0.6 and not input_penalty:
        return "medium"
    if input_penalty and coverage >= 0.6:
        return "medium" if coverage >= 0.85 else "low"
    return "low"


# Back-compat aliases used by older tests / call sites during transition.
def score_soil_health(sequence: list[str], features: dict[str, Any], **_: Any) -> float:
    """Deprecated: mean of nitrogen + organic_matter."""
    return _clip01(
        0.5 * score_nitrogen(sequence) + 0.5 * score_organic_matter(sequence, features)
    )


def score_income(sequence: list[str], *args: Any, **kwargs: Any) -> float:
    """Deprecated alias for score_market."""
    return score_market(sequence)
