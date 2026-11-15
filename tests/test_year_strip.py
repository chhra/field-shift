"""Farming-year calendar: month parsing and row layout."""

from __future__ import annotations

from fieldshift.models import CropInSequence
from ui.year_strip import (
    month_range,
    months_from_text,
    rows_from_crops,
    rows_from_sequence,
    year_strip_html,
)


def test_months_wrap_past_december() -> None:
    assert months_from_text("rabi Nov–Apr") == [11, 12, 1, 2, 3, 4]
    assert months_from_text("May–Oct") == [5, 6, 7, 8, 9, 10]
    assert months_from_text("no months here") == []
    assert month_range(12, 1) == [12, 1]


def test_sequence_same_season_crops_take_separate_years() -> None:
    seq = [
        CropInSequence(crop_id="maize", months="May–Oct"),
        CropInSequence(crop_id="soybean", months="May–Oct"),
    ]
    rows = rows_from_sequence(seq)
    assert len(rows) == 2
    assert rows[0][4] == ("maize", False)
    assert rows[1][4] == ("soybean", False)


def test_cover_fills_bare_months_every_year_only() -> None:
    seq = [
        CropInSequence(crop_id="maize", months="May–Oct"),
        CropInSequence(crop_id="soybean", months="May–Oct"),
        CropInSequence(crop_id="cereal_rye_cover", months="Oct–Apr"),
    ]
    rows = rows_from_sequence(seq)
    assert len(rows) == 2
    for row in rows:
        assert row[0] == ("cereal_rye_cover", True)
        assert row[9][0] != "cereal_rye_cover"  # October stays with the cash crop


def test_two_seasons_share_one_year() -> None:
    rows = rows_from_crops(
        [
            ("rice", [6, 7, 8, 9, 10]),
            ("winter_wheat", [11, 12, 1, 2, 3, 4]),
            ("radish_cover", [5, 6]),
        ]
    )
    assert len(rows) == 1
    assert rows[0][4] == ("radish_cover", True)  # May: cover in the bare month
    assert rows[0][5] == ("rice", False)  # June: cash wins over the cover window


def test_six_winter_crops_get_six_years() -> None:
    rows = rows_from_crops([(c, months_from_text("Oct–Jun")) for c in "abcdef"])
    assert len(rows) == 6


def test_html_labels_years_and_describes_rows_for_screen_readers() -> None:
    rows = rows_from_crops(
        [("maize", [5, 6, 7, 8, 9, 10]), ("soybean", [5, 6, 7, 8, 9, 10])]
    )
    out = year_strip_html(rows)
    assert "Year 2" in out
    assert 'aria-label="Year 1: bare soil Jan–Apr, Maize May–Oct, bare soil Nov–Dec"' in out
