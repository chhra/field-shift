"""Card copy helpers — six-goal labels and deltas."""

from __future__ import annotations

from fieldshift.engine.card_copy import (
    SCORE_KEYS,
    farmer_comparison_sentence,
    format_delta_label,
    rotation_title_line,
    top_criterion_diffs,
)
from fieldshift.models import CropInSequence, ScoreSet


def _scores(**kwargs: float) -> ScoreSet:
    base = {
        "water": 0.5,
        "forage": 0.0,
        "nitrogen": 0.5,
        "erosion": 0.5,
        "organic_matter": 0.5,
        "market": 0.5,
        "total": 0.5,
    }
    base.update(kwargs)
    return ScoreSet(**base)


def test_score_keys_are_six_goals() -> None:
    assert SCORE_KEYS == (
        "water",
        "forage",
        "nitrogen",
        "erosion",
        "organic_matter",
        "market",
    )


def test_top_criterion_diffs_order() -> None:
    opt = _scores(nitrogen=0.9, erosion=0.2, total=0.6)
    base = _scores(nitrogen=0.4, erosion=0.7, total=0.5)
    diffs = top_criterion_diffs(opt, base, n=3)
    assert diffs[0]["key"] in {"nitrogen", "erosion"}
    assert {d["key"] for d in diffs}.issubset(set(SCORE_KEYS))


def test_format_delta_neutral() -> None:
    text, tone = format_delta_label(0.01)
    assert tone == "neutral"
    assert "same" in text.lower()


def test_farmer_sentence_tradeoff() -> None:
    diffs = [
        {"key": "nitrogen", "friendly": "natural nitrogen", "direction": "better", "delta": 0.2, "pct": 80, "band": "Strong", "label": "N"},
        {"key": "market", "friendly": "market potential", "direction": "worse", "delta": -0.1, "pct": 40, "band": "Fair", "label": "M"},
    ]
    s = farmer_comparison_sentence(diffs, overall_delta=0.05)
    assert "natural nitrogen" in s
    assert "market potential" in s


def test_rotation_title_line() -> None:
    line = rotation_title_line(
        [
            CropInSequence(crop_id="maize", months="May–Oct"),
            CropInSequence(crop_id="soybean", months="May–Oct"),
        ]
    )
    assert "Maize" in line and "Soybean" in line
