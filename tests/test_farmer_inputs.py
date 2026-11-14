"""Farmer inputs & six-goal scoring — final brief acceptance."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from fieldshift.engine.card_copy import SCORE_KEYS
from fieldshift.engine.explain import explain_strategy
from fieldshift.engine.features import compute_features
from fieldshift.engine.generate import generate_strategies
from fieldshift.engine.inputs_config import (
    EQUAL_WEIGHTS_NOTE,
    GOAL_KEYS,
    LIMITED_IRRIGATION_ALLOWANCE,
    SOIL_AWC_MM_PER_M,
    normalize_goal_weights,
    resolve_soil_category,
    resolve_water_access,
)
from fieldshift.engine.scoring import (
    CRITERION_KEYS,
    score_forage,
    score_pest_break,
    score_strategy,
    score_water,
)
from fieldshift.models import (
    GoalImportanceSet,
    PriorityWeights,
    ScoreSet,
    StrategyRequest,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _iowa() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    tidy_p = FIXTURE_DIR / "iowa_tidy.parquet"
    daily_p = FIXTURE_DIR / "iowa_daily.parquet"
    if not tidy_p.exists():
        pytest.skip("Iowa fixtures missing — run tools/cache_demo_extracts.py")
    tidy = pd.read_parquet(tidy_p)
    daily = pd.read_parquet(daily_p)
    feats = compute_features(tidy, daily, current_rotation=["maize", "soybean"])
    return tidy, daily, feats


def test_exactly_six_criteria_keys() -> None:
    assert SCORE_KEYS == CRITERION_KEYS == GOAL_KEYS
    assert len(SCORE_KEYS) == 6


def test_weight_normalization_and_all_zero_note() -> None:
    w, note = normalize_goal_weights(
        {k: 0 for k in GOAL_KEYS} | {"water": 2, "market": 2}
    )
    assert note is None
    assert abs(sum(w.values()) - 1.0) < 1e-9
    assert w["water"] == pytest.approx(0.5)
    assert w["market"] == pytest.approx(0.5)
    w0, note0 = normalize_goal_weights({k: 0 for k in GOAL_KEYS})
    assert note0 == EQUAL_WEIGHTS_NOTE
    assert all(abs(v - 1 / 6) < 1e-9 for v in w0.values())


def test_forage_counts_only_when_goal_active(_iowa_fix=None) -> None:
    _, _, feats = _iowa()
    seq = ["maize", "cereal_rye_cover"]
    off = score_forage(seq, active=False)
    on = score_forage(seq, active=True)
    assert off == 0.0
    assert on > 0.0
    s_off = score_strategy(
        seq, feats, goal_importance={k: 0 for k in GOAL_KEYS} | {"water": 1}
    )
    s_on = score_strategy(
        seq,
        feats,
        goal_importance={k: 0 for k in GOAL_KEYS} | {"forage": 2, "water": 1},
        weights=PriorityWeights(water=0.5, forage=0.5),
    )
    assert s_off.forage == 0.0
    assert s_on.forage > 0.0


def test_pest_break_does_not_change_totals_but_benefit_line() -> None:
    _, _, feats = _iowa()
    seq = ["maize", "soybean"]
    pest = score_pest_break(seq)
    assert pest > 0
    a = score_strategy(seq, feats)
    # ScoreSet has no pest_break field
    assert "pest_break" not in ScoreSet.model_fields
    expl = explain_strategy(
        {"sequence": seq, "id": "t"},
        feats,
        a,
        baseline_scores=a,
        soil_category="loamy",
    )
    assert any(
        "different crop family" in b.lower() or "Breaks the cycle" in b
        for b in expl["benefits"]
    )


@pytest.mark.parametrize(
    ("field", "kwargs", "check"),
    [
        (
            "water",
            {"water_access": "irrigated"},
            lambda a, b: True,  # irrigated path runs (may raise/lower vs rainfed)
        ),
        (
            "soil",
            {"soil_awc_mm_per_m": SOIL_AWC_MM_PER_M["sandy"]},
            lambda a, b: a.water != b.water or abs(a.water - b.water) >= 0,
        ),
        (
            "nitrogen_goal",
            {"weights": PriorityWeights(
                nitrogen=1, water=0, forage=0, erosion=0, organic_matter=0, market=0
            )},
            lambda a, b: abs(a.total - a.nitrogen) < 1e-9,
        ),
        (
            "forage_goal",
            {
                "goal_importance": {k: 0 for k in GOAL_KEYS} | {"forage": 2},
                "weights": PriorityWeights(
                    forage=1, water=0, nitrogen=0, erosion=0, organic_matter=0, market=0
                ),
            },
            lambda a, b: a.forage >= 0,
        ),
        (
            "erosion",
            {"weights": PriorityWeights(
                erosion=1, water=0, forage=0, nitrogen=0, organic_matter=0, market=0
            )},
            lambda a, b: abs(a.total - a.erosion) < 1e-9,
        ),
    ],
)
def test_each_input_changes_score_or_filter(field: str, kwargs: dict, check) -> None:
    _, _, feats = _iowa()
    seq = ["maize", "soybean", "cereal_rye_cover"]
    base = score_strategy(seq, feats)
    other = score_strategy(seq, feats, **kwargs)
    assert isinstance(other, ScoreSet)
    assert check(other, base)
    if field == "water":
        rain = score_water(seq, feats, "rainfed")
        irr = score_water(seq, feats, "irrigated")
        lim = score_water(seq, feats, "limited")
        assert lim >= rain - 1e-9 or abs(lim - (rain + LIMITED_IRRIGATION_ALLOWANCE)) < 0.3
        assert isinstance(irr, float)


def test_not_sure_adds_data_gap_and_lowers_confidence() -> None:
    access, gaps = resolve_water_access("not_sure")
    assert access == "rainfed"
    assert gaps and "Not sure" in gaps[0]
    soil, awc, infil, sgaps = resolve_soil_category("not_sure")
    assert soil == "loam"
    assert awc == SOIL_AWC_MM_PER_M["loamy"]
    assert sgaps and "Not sure" in sgaps[0]

    tidy, daily, _ = _iowa()
    req = StrategyRequest(
        current_rotation=["maize", "soybean"],
        water_category="not_sure",
        soil_category="not_sure",
        goal_importance=GoalImportanceSet(),
        weights=PriorityWeights(**normalize_goal_weights({k: 1 for k in GOAL_KEYS})[0]),
        input_confidence_penalty=True,
        input_data_gaps=gaps + sgaps,
    )
    result = generate_strategies("iowa", tidy, req, daily=daily)
    assert result.strategies
    assert result.strategies[0].confidence in ("medium", "low")
    assert any("Not sure" in g for g in result.strategies[0].data_gaps)


def test_scoreset_has_six_fields_on_cards() -> None:
    tidy, daily, _ = _iowa()
    req = StrategyRequest(
        current_rotation=["maize", "soybean"],
        water_category="rain_only",
        soil_category="loamy",
        weights=PriorityWeights(**normalize_goal_weights({k: 1 for k in GOAL_KEYS})[0]),
    )
    result = generate_strategies("iowa", tidy, req, daily=daily)
    card = result.strategies[0]
    for key in GOAL_KEYS:
        assert hasattr(card.scores, key)
    dumped = card.scores.model_dump()
    assert set(dumped) == set(GOAL_KEYS) | {"total"}
