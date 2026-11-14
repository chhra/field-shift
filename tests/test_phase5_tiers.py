"""Tiers, water constraints, nitrogen/forage scoring under the final six goals."""

from __future__ import annotations

from fieldshift.engine.constraints import evaluate_constraints, sequence_has_legume
from fieldshift.engine.scoring import score_forage, score_nitrogen, score_strategy
from fieldshift.engine.thresholds import BEST_FIT_MIN_DELTA, NOT_SUITABLE_TOTAL_DELTA
from fieldshift.engine.tiers import assign_tiers, recommendation_sentence
from fieldshift.models import CropInSequence, PriorityWeights, ScoreSet, StrategyCard


def _card(
    cid: str,
    total: float,
    *,
    confidence: str = "medium",
    unsuitable: list[str] | None = None,
    scores: dict[str, float] | None = None,
) -> StrategyCard:
    base = {
        "water": 0.5,
        "forage": 0.0,
        "nitrogen": 0.5,
        "erosion": 0.5,
        "organic_matter": 0.5,
        "market": 0.5,
    }
    if scores:
        base.update(scores)
    base["total"] = total
    return StrategyCard(
        id=cid,
        name=cid,
        sequence=[CropInSequence(crop_id="maize", months="May–Oct")],
        scores=ScoreSet(**base),
        delta_vs_current={"total": 0.0},
        why="test",
        evidence=[],
        benefits=[],
        data_gaps=[],
        risks_for_local_review=[],
        confidence=confidence,  # type: ignore[arg-type]
        unsuitable_reasons=list(unsuitable or []),
    )


def test_best_fit_and_baseline_tiers() -> None:
    current = _card("current", 0.50)
    alt = _card("cover", 0.50 + BEST_FIT_MIN_DELTA + 0.01)
    alt.delta_vs_current = {"total": BEST_FIT_MIN_DELTA + 0.01}
    weak = _card("weak", 0.50 - NOT_SUITABLE_TOTAL_DELTA - 0.01)
    weak.delta_vs_current = {"total": -NOT_SUITABLE_TOTAL_DELTA - 0.01}
    cards = assign_tiers([alt, current, weak])
    by_id = {c.id: c for c in cards}
    assert by_id["current"].tier == "baseline"
    assert by_id["cover"].tier == "best_fit"
    assert by_id["weak"].tier == "not_suitable"
    assert "best fit" in recommendation_sentence(cards).lower()


def test_no_best_fit_honest_message() -> None:
    current = _card("current", 0.70)
    alt = _card("alt", 0.71)
    alt.delta_vs_current = {"total": 0.01}
    cards = assign_tiers([current, alt])
    assert not any(c.tier == "best_fit" for c in cards)
    assert "already a good fit" in recommendation_sentence(cards).lower()


def test_rain_only_blocks_rice() -> None:
    cons = evaluate_constraints(["rice", "winter_wheat"], water_access="rainfed")
    assert cons["unsuitable"]
    assert any("irrigation" in r.lower() for r in cons["reasons"])
    ok = evaluate_constraints(["rice", "winter_wheat"], water_access="irrigated")
    assert not ok["unsuitable"]


def test_legume_raises_nitrogen() -> None:
    assert sequence_has_legume(["maize", "soybean"])
    with_legume = score_nitrogen(["maize", "soybean"])
    without = score_nitrogen(["maize", "sorghum"])
    assert with_legume > without


def test_forage_inactive_zero() -> None:
    assert score_forage(["cereal_rye_cover"], active=False) == 0.0
    assert score_forage(["cereal_rye_cover"], active=True) > 0.0


def test_worth_considering_on_top_priority() -> None:
    current = _card(
        "current",
        0.55,
        scores={
            "water": 0.40,
            "forage": 0.0,
            "nitrogen": 0.6,
            "erosion": 0.6,
            "organic_matter": 0.6,
            "market": 0.6,
        },
    )
    alt = _card(
        "alt",
        0.56,
        scores={
            "water": 0.90,
            "forage": 0.0,
            "nitrogen": 0.5,
            "erosion": 0.5,
            "organic_matter": 0.5,
            "market": 0.5,
        },
    )
    alt.delta_vs_current = {"total": 0.01}
    cards = assign_tiers(
        [current, alt],
        weights=PriorityWeights(
            water=2.0, forage=0, nitrogen=0.5, erosion=0.5, organic_matter=0.5, market=0.5
        ),
    )
    assert {c.id: c.tier for c in cards}["alt"] == "worth_considering"


def test_score_strategy_six_fields() -> None:
    feats = {
        "bare_months": {"months": [1, 2]},
        "erosion_risk": 0.2,
        "rain": {"rain_cv": 0.2, "rain_annual_mm": 800},
        "frost_window": {"frost_free_days": 180},
        "gdd": {"gdd_annual_mean": 2000, "heat_days_mean": 5},
        "series": {},
    }
    sc = score_strategy(["maize", "soybean"], feats)
    for key in (
        "water",
        "forage",
        "nitrogen",
        "erosion",
        "organic_matter",
        "market",
        "total",
    ):
        assert hasattr(sc, key)
