"""Template-based deterministic explanations for strategy cards."""

from __future__ import annotations

from typing import Any

from fieldshift.engine.crops import crop_by_id
from fieldshift.engine.inputs_config import (
    SOIL_INFILTRATION_MM_H,
    STANDARD_LOCAL_RISKS,
)
from fieldshift.engine.scoring import grace_groundwater_penalty, score_pest_break
from fieldshift.models import EvidenceItem, ScoreSet


def _data_through_for(
    features: dict[str, Any], *variable_keys: str
) -> str | None:
    """Best data_through label from coverage rows matching variable name fragments."""
    cov = features.get("data_coverage", {}).get("per_variable") or []
    for key in variable_keys:
        for row in cov:
            var = str(row.get("variable") or "")
            if key in var and row.get("data_through"):
                return str(row["data_through"])
    period = (features.get("rain") or {}).get("period")
    if period and "→" in str(period):
        end = str(period).split("→")[-1].strip()
        try:
            import pandas as pd

            return pd.Timestamp(str(end) + "-01").strftime("%B %Y")
        except Exception:
            return end
    return None


_FAMILY_PLAIN = {
    "poaceae": "a cereal",
    "fabaceae": "a legume",
    "brassicaceae": "a brassica",
    "asteraceae": "in the sunflower family",
    "malvaceae": "in the mallow family",
}


def _plain_name(crop: dict[str, Any]) -> str:
    """Mid-sentence crop name: 'Cereal rye (cover crop)' -> 'cereal rye'."""
    return str(crop["name"]).split(" (")[0].lower()


def _pest_benefit_lines(sequence: list[str]) -> list[str]:
    """Benefit lines when consecutive crops are from different families."""
    if len(sequence) < 2:
        return []
    lines: list[str] = []
    for a, b in zip(sequence, sequence[1:], strict=False):
        ca, cb = crop_by_id(a), crop_by_id(b)
        if ca["family"] != cb["family"]:
            next_crop = _plain_name(cb)
            family = _FAMILY_PLAIN.get(cb["family"], "from another crop family")
            lines.append(
                f"Breaks the cycle of {ca['name'].lower()} pests: {next_crop} is {family}"
            )
    # Keep pest-break calculation alive for the benefit signal.
    _ = score_pest_break(sequence)
    return lines[:2]


def _infiltration_benefit(sequence: list[str], soil_category: str) -> list[str]:
    """Cover / deep roots — stronger wording on clay and silty soils."""
    has_cover = any(crop_by_id(c)["type"] == "cover" for c in sequence)
    deep = any(crop_by_id(c).get("root_depth") == "deep" for c in sequence)
    if not (has_cover or deep):
        return []
    infil = SOIL_INFILTRATION_MM_H.get(soil_category, 13.0)
    if soil_category in ("clay", "silty"):
        return [
            "Cover or deep roots can improve infiltration on "
            f"{soil_category} soil (typical rate ≈ {infil:.1f} mm/h)"
        ]
    return ["Cover or deep roots can help water soak in between rains"]


def _supplemental_income_benefit(sequence: list[str]) -> list[str]:
    forage = [
        crop_by_id(c)
        for c in sequence
        if float(crop_by_id(c).get("forage_value") or 0) >= 0.5
        or crop_by_id(c)["type"] in ("cover", "forage")
    ]
    if not forage:
        return []
    names = " and ".join(_plain_name(c) for c in forage[:2])
    return [f"Supplemental income or feed value possible from {names}"]


def explain_strategy(
    strategy: dict[str, Any],
    features: dict[str, Any],
    scores: ScoreSet,
    *,
    anomalies: dict[str, Any] | None = None,
    baseline_scores: ScoreSet | None = None,
    soil_category: str = "loamy",
    extra_data_gaps: list[str] | None = None,
) -> dict[str, Any]:
    bare = features.get("bare_months", {})
    rain = features.get("rain", {})
    frost = features.get("frost_window", {})
    phenology = features.get("phenology") or {}
    erisk = features.get("erosion_risk")
    seq = strategy["sequence"]
    names = [crop_by_id(c)["name"] for c in seq]

    why_bits = []
    if bare.get("months"):
        why_bits.append(bare.get("detail") or "Persistent bare months detected.")
    if (rain.get("rain_cv") or 0) > 0.2:
        why_bits.append(
            f"Year-to-year rain variability is high (CV={rain['rain_cv']:.2f})."
        )
    if any(crop_by_id(c)["type"] == "cover" for c in seq):
        why_bits.append("A cover crop is included to protect soil in the off-season.")
    if not why_bits:
        why_bits.append(
            f"Scores favour this rotation for the goals you marked as important "
            f"(total={scores.total:.2f})."
        )
    why = " ".join(why_bits[:2])

    evidence: list[EvidenceItem] = []
    ndvi_through = _data_through_for(features, "ndvi_s2", "ndvi_modis")
    rain_through = _data_through_for(features, "rain_best", "rain_mm", "power_rain")
    grace_through = _data_through_for(features, "grace_lwe")
    power_through = _data_through_for(features, "power_t2m", "power_t2m_min")

    if phenology.get("n_seasons", 0) > 0 and phenology.get("detail"):
        evidence.append(
            EvidenceItem(
                text=str(phenology["detail"]),
                source=str(phenology.get("source") or "NDVI"),
                data_through=ndvi_through,
            )
        )
    elif bare.get("evidence_line"):
        evidence.append(
            EvidenceItem(
                text=str(bare["evidence_line"]),
                source="Sentinel-2/MODIS NDVI",
                data_through=ndvi_through,
            )
        )
    if bare.get("detail") and bare.get("ndvi_confirmed_ok"):
        evidence.append(
            EvidenceItem(
                text=str(bare["detail"]),
                source="Sentinel-2 NDVI",
                data_through=ndvi_through,
            )
        )
    if rain.get("rain_annual_mm") is not None:
        src = rain.get("source") or "rain_best"
        period = rain.get("period") or ""
        evidence.append(
            EvidenceItem(
                text=(
                    f"Mean annual rain_best ≈ {rain['rain_annual_mm']:.0f} mm"
                    + (f" ({period})" if period else "")
                ),
                source=str(src),
                data_through=rain_through,
            )
        )
    grace = features.get("grace_trend") or {}
    if grace.get("detail"):
        evidence.append(
            EvidenceItem(
                text=str(grace["detail"]),
                source="GRACE/FO Mascon CRI (deseasonalized)",
                data_through=grace_through
                or (
                    f"{grace.get('end_year')}"
                    if grace.get("end_year")
                    else None
                ),
            )
        )
        _ = grace_groundwater_penalty(features)
    elif features.get("grace_trend_cm_per_yr") is not None:
        trend = float(features["grace_trend_cm_per_yr"])
        evidence.append(
            EvidenceItem(
                text=f"Regional water storage trend {trend:.1f} cm/yr (GRACE-FO)",
                source="GRACE/FO Mascon CRI",
                data_through=grace_through,
            )
        )
    if frost.get("frost_free_days") is not None:
        evidence.append(
            EvidenceItem(
                text=f"Frost-free period ≈ {frost['frost_free_days']:.0f} days",
                source="NASA POWER T2M_MIN",
                data_through=power_through,
            )
        )
    if erisk is not None:
        evidence.append(
            EvidenceItem(
                text=f"Erosion risk index ≈ {erisk:.2f} (0–1)",
                source="SRTM slope + rain extremes + bare months",
            )
        )
    if anomalies and anomalies.get("vulnerable_seasons"):
        top = anomalies["vulnerable_seasons"][0]
        evidence.append(
            EvidenceItem(
                text=(
                    f"Growing-season anomaly: calendar month {top['calendar_month']} "
                    f"({top['n_flags']} times)"
                ),
                source="IsolationForest SI",
                data_through=ndvi_through,
            )
        )
    if not evidence:
        evidence.append(
            EvidenceItem(text="Limited field evidence available", source="data coverage")
        )

    # Benefits (not rated): pest, infiltration, supplemental income, reduced water demand
    benefits: list[str] = []
    benefits.extend(_pest_benefit_lines(seq))
    benefits.extend(_infiltration_benefit(seq, soil_category))
    benefits.extend(_supplemental_income_benefit(seq))
    if baseline_scores is not None and scores.water > baseline_scores.water + 0.02:
        benefits.append("Lower water demand than your current rotation")
    if any(crop_by_id(c)["nitrogen_fixing"] for c in seq):
        benefits.append("Adds nitrogen naturally via a legume")
    if not benefits:
        benefits.append("Keeps familiar cash-crop options for your seasons")

    data_gaps = list(features.get("feature_data_gaps") or [])
    if extra_data_gaps:
        data_gaps.extend(extra_data_gaps)
    cov = features.get("data_coverage", {}).get("per_variable") or []
    for row in cov:
        if row.get("n_gaps", 0) > 0 and row.get("variable") in {
            "ndvi_s2",
            "grace_lwe_cm",
            "rain_mm",
        }:
            data_gaps.append(
                f"{row['variable']}: {row['n_gaps']} gap months "
                f"(data through {row.get('data_through')})"
            )
    if anomalies and anomalies.get("uncertainty"):
        data_gaps.append(anomalies["uncertainty"])
    if not data_gaps:
        data_gaps.append("GAEZ suitability and US SSURGO modules not applied yet")

    risks = list(STANDARD_LOCAL_RISKS)
    if any(crop_by_id(c).get("needs_expert_review") for c in seq):
        risks.append("Crop parameter values need local expert review")

    return {
        "why": why,
        "evidence": evidence,
        "benefits": benefits,
        "data_gaps": data_gaps,
        "risks_for_local_review": risks,
        "display_name": " → ".join(names),
    }
