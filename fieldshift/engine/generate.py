"""Pure-Python strategy generation over cached/harmonized field features."""

from __future__ import annotations

from typing import Any

import pandas as pd

from fieldshift.engine.anomalies import detect_anomalies
from fieldshift.engine.candidates import build_candidates, season_label
from fieldshift.engine.constraints import evaluate_constraints, sequence_has_legume
from fieldshift.engine.explain import explain_strategy
from fieldshift.engine.features import compute_features
from fieldshift.engine.inputs_config import (
    MONTH_SHIFT_DATA_GAP_THRESHOLD,
    resolve_soil_category,
    resolve_water_access,
)
from fieldshift.engine.scenarios import apply_scenario
from fieldshift.engine.scoring import CRITERION_KEYS, confidence_label, score_strategy
from fieldshift.engine.tiers import assign_tiers
from fieldshift.models import (
    CropInSequence,
    FarmConstraints,
    StrategyCard,
    StrategyRequest,
    StrategyResult,
)


def generate_strategies(
    field_id: str,
    tidy: pd.DataFrame,
    request: StrategyRequest,
    *,
    daily: pd.DataFrame | None = None,
    features: dict[str, Any] | None = None,
) -> StrategyResult:
    """Score candidate rotations. Must not call EE/POWER."""
    feats = features or compute_features(
        tidy, daily, current_rotation=request.current_rotation
    )
    if "series" not in feats:
        feats = compute_features(
            tidy, daily, current_rotation=request.current_rotation
        )
    anomalies = detect_anomalies(feats)
    adj = apply_scenario(feats, request.scenario)
    constraints = request.constraints or FarmConstraints()

    water_access, water_gaps = resolve_water_access(request.water_category)
    # Prefer explicit request.water_access if already resolved by UI.
    if request.water_access in ("rainfed", "limited", "irrigated"):
        water_access = request.water_access
    soil_type, awc, _infil, soil_gaps = resolve_soil_category(request.soil_category)
    if request.soil_type in ("sand", "loam", "clay", "silt"):
        soil_type = request.soil_type
        from fieldshift.engine.inputs_config import SOIL_AWC_MM_PER_M, SOIL_TYPE_MAP

        inv = {v: k for k, v in SOIL_TYPE_MAP.items() if k != "not_sure"}
        cat = inv.get(soil_type, request.soil_category)
        awc = float(SOIL_AWC_MM_PER_M.get(cat, awc))

    input_gaps = list(request.input_data_gaps or []) + water_gaps + soil_gaps
    if request.equal_weights_note:
        input_gaps.append(request.equal_weights_note)
    input_gaps.extend(
        _month_shift_gaps(
            request.current_rotation,
            adj,
            request.plant_month_overrides,
            request.harvest_month_overrides,
        )
    )

    importance = request.goal_importance.model_dump()
    cands = build_candidates(
        request.current_rotation,
        adj,
        water_access=water_access,
        weights=request.weights,
    )
    scored: list[tuple[dict[str, Any], Any, dict[str, Any]]] = []
    for cand in cands:
        cons = evaluate_constraints(
            cand["sequence"],
            constraints,
            water_access=water_access,
        )
        sc = score_strategy(
            cand["sequence"],
            adj,
            weights=request.weights,
            water_access=water_access,
            soil_awc_mm_per_m=awc,
            goal_importance=importance,
            soft_penalty=float(cons.get("soft_penalty") or 0.0),
        )
        scored.append((cand, sc, cons))

    if not scored:
        return StrategyResult(field_id=field_id, strategies=[])

    current_pair = next(
        ((cand, sc) for cand, sc, _ in scored if cand["id"] == "current"),
        (scored[0][0], scored[0][1]),
    )
    current_scores = current_pair[1]
    conf = confidence_label(
        adj,
        [sc for _, sc, _ in scored],
        [c["sequence"] for c, _, _ in scored],
        input_penalty=bool(request.input_confidence_penalty or water_gaps or soil_gaps),
    )

    cards: list[StrategyCard] = []
    for cand, sc, cons in sorted(scored, key=lambda t: t[1].total, reverse=True):
        expl = explain_strategy(
            cand,
            adj,
            sc,
            anomalies=anomalies,
            baseline_scores=current_scores,
            soil_category=request.soil_category,
            extra_data_gaps=input_gaps,
        )
        benefits = list(expl["benefits"])
        if sequence_has_legume(cand["sequence"]) and "Adds nitrogen" not in " ".join(
            benefits
        ):
            benefits.insert(0, "May reduce fertiliser need via a nitrogen-fixing crop")
        unsuitable = list(cons.get("reasons") or [])
        cards.append(
            StrategyCard(
                id=cand["id"],
                name=expl["display_name"],
                sequence=[
                    CropInSequence(crop_id=cid, months=season_label(cid, adj))
                    for cid in cand["sequence"]
                ],
                scores=sc,
                delta_vs_current=_deltas_vs_current(sc, current_scores),
                why=expl["why"],
                evidence=expl["evidence"],
                benefits=benefits,
                data_gaps=expl["data_gaps"],
                risks_for_local_review=expl["risks_for_local_review"],
                confidence=conf,
                unsuitable_reasons=unsuitable,
                soft_notes=list(cons.get("soft_notes") or []),
            )
        )
    cards = assign_tiers(cards, weights=request.weights)
    return StrategyResult(field_id=field_id, strategies=cards)


def _month_shift_gaps(
    rotation: list[str],
    features: dict[str, Any],
    plant_overrides: dict[str, int],
    harvest_overrides: dict[str, int],
) -> list[str]:
    gaps: list[str] = []
    for cid in rotation:
        detected = season_label(cid, features)
        # season_label is like "May–Oct"; we only gap when overrides exist.
        if cid in plant_overrides:
            # Without a numeric detected plant month, any override > threshold
            # from a stored satellite month is flagged by the UI; here flag presence
            # when override differs from phenology start if available.
            seasons = (features.get("phenology") or {}).get("seasons") or []
            if seasons and abs(
                int(plant_overrides[cid]) - int(seasons[0].get("start_month", plant_overrides[cid]))
            ) > MONTH_SHIFT_DATA_GAP_THRESHOLD:
                gaps.append(
                    f"Planting month for {cid} moved >{MONTH_SHIFT_DATA_GAP_THRESHOLD} "
                    "month from satellite detection"
                )
        if cid in harvest_overrides:
            seasons = (features.get("phenology") or {}).get("seasons") or []
            if seasons and abs(
                int(harvest_overrides[cid])
                - int(seasons[0].get("end_month", harvest_overrides[cid]))
            ) > MONTH_SHIFT_DATA_GAP_THRESHOLD:
                gaps.append(
                    f"Harvest month for {cid} moved >{MONTH_SHIFT_DATA_GAP_THRESHOLD} "
                    "month from satellite detection"
                )
        _ = detected
    return gaps


def _deltas_vs_current(scores: Any, current: Any) -> dict[str, float]:
    """Per-criterion and total delta vs the farmer's current rotation scores."""
    out = {
        key: round(float(getattr(scores, key)) - float(getattr(current, key)), 4)
        for key in CRITERION_KEYS
    }
    out["total"] = round(float(scores.total) - float(current.total), 4)
    return out
