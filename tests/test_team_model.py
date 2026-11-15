"""Tests for the team rotation model and its bridge to the app's inputs."""

from __future__ import annotations

import pytest
from team_model import app_adapter, model

ARABLE = ["Winter wheat", "Maize", "Winter barley"]
LEY_FARM = ["Winter wheat", "Red clover ley", "Winter barley", "Winter oilseed rape"]
OLD_PRIORITIES = {"soil": 3, "water": 2, "fertility": 2, "income": 2}

# A fixed test farm, so the rule assertions below never change when the real NASA
# farm data is rebuilt. It is deliberately local to the tests (the model itself
# carries no mock farm: production always uses the real NASA POWER climate).
TEST_FARM = {
    "annual_rain_mm": 850,
    "wet_months": [10, 11, 12, 1],
    "dry_months": [6, 7, 8],
    "frost_months": [12, 1, 2],
    "coldest_temp_c": -6,
    "growing_temp_c": 15,
    "summer_drying": True,
    "heat_rising": True,
}


@pytest.fixture(scope="module")
def data():
    crops, successors, _farm, _weather = app_adapter.load_data()
    # TEST_FARM, not the NASA files: results must not change when the farm data does
    return crops, successors, dict(TEST_FARM)


def run(data, current=ARABLE, priorities=OLD_PRIORITIES, **kwargs):
    crops, successors, farm = data
    return model.recommend(current, farm, priorities, crops, successors, **kwargs)


# --- the model -------------------------------------------------------------


def test_returns_current_and_two_options(data):
    results = run(data)
    assert [r["name"] for r in results] == [
        "Current rotation",
        "Option A (best fit)",
        "Option B (alternative)",
    ]
    assert results[1]["score"] >= results[2]["score"] > results[0]["score"]
    for r in results:
        assert set(r) >= {"rotation", "crops", "years", "score", "points",
                          "benefits", "risks", "reasons", "checks"}


def test_typo_in_crop_name_gives_clear_error(data):
    with pytest.raises(ValueError, match="Unknown crop"):
        run(data, current=["Wheat", "Maize"])


def test_unknown_water_or_soil_is_rejected(data):
    with pytest.raises(ValueError, match="water source"):
        run(data, water="canal")
    with pytest.raises(ValueError, match="soil type"):
        run(data, soil="peat")


def test_same_cycle_from_another_year_is_no_change():
    assert model.count_changes(["Maize", "Winter barley", "Winter wheat"], ARABLE) == 0
    assert model.count_changes(["Winter barley", "Maize", "Winter wheat"], ARABLE) == 0.5
    assert model.count_changes(["Winter wheat", "Spring peas", "Winter barley"], ARABLE) == 1
    assert model.count_changes([*ARABLE, "Spring peas"], ARABLE) == 1


def test_a_ley_counts_three_years(data):
    crops = data[0]
    assert model.rotation_years(ARABLE, crops) == 3
    assert model.rotation_years(LEY_FARM, crops) == 6


def test_suggested_rotations_stay_within_five_years(data):
    crops, _successors, farm = data
    for rot in model.candidates(ARABLE, farm, crops):
        assert model.rotation_years([m for m, _ in rot], crops) <= model.MAX_ROTATION_YEARS


def test_irrigation_removes_the_thirsty_crop_penalty(data):
    water_points = {
        w: run(data, water=w, soil="loamy")[0]["points"]["water"]
        for w in ("rain_only", "some_irrigation", "fully_irrigated")
    }
    assert water_points["rain_only"] < water_points["some_irrigation"] < water_points["fully_irrigated"]


def test_light_soil_makes_bare_wet_months_cost_more(data):
    soil_points = {s: run(data, soil=s)[0]["points"]["soil"] for s in ("loamy", "sandy", "silty")}
    assert soil_points["sandy"] < soil_points["loamy"]
    assert soil_points["silty"] < soil_points["loamy"]


def test_not_sure_answers_are_reported_as_gaps(data):
    reasons = " ".join(run(data, water="not_sure", soil="not_sure")[0]["reasons"])
    assert "Water source not given" in reasons
    assert "Soil type not given" in reasons


def test_new_leys_only_suggested_when_forage_matters(data):
    crops = data[0]

    def has_ley(results):
        return any(crops[m]["role"] == "forage" for r in results[1:] for m, _ in r["crops"])

    assert not has_ley(run(data))
    assert has_ley(run(data, priorities={**OLD_PRIORITIES, "forage": 3, "organic_matter": 2}))


def test_existing_ley_is_kept(data):
    results = run(data, current=LEY_FARM, soil="clay")
    assert all(any(m == "Red clover ley" for m, _ in r["crops"]) for r in results)


# --- the bridge to the app ---------------------------------------------------


def test_goals_map_to_the_six_priorities():
    goals = {"water": 2, "forage": 0, "nitrogen": 1, "erosion": 1, "organic_matter": 1, "market": 1}
    assert app_adapter.priorities_from_goals(goals) == {
        "water": 3, "forage": 0, "fertility": 2, "soil": 2, "organic_matter": 2, "income": 2,
    }


def test_bad_goals_are_rejected():
    with pytest.raises(ValueError, match="Unknown goal"):
        app_adapter.priorities_from_goals({"profit": 2})
    with pytest.raises(ValueError, match="0, 1 or 2"):
        app_adapter.priorities_from_goals({"water": 3})


def test_priorities_from_order_scales_first_to_three():
    p = app_adapter.priorities_from_order(["erosion", "water", "market"])
    assert p["soil"] == 3.0
    assert p["water"] == 2.0
    assert p["income"] == 1.0
    assert p["forage"] == p["fertility"] == p["organic_matter"] == 0
    assert app_adapter.priorities_from_order([]) == app_adapter.priorities_from_goals(
        app_adapter.DEFAULT_GOALS
    )
    with pytest.raises(ValueError, match="Unknown goal"):
        app_adapter.priorities_from_order(["profit"])


def test_recommend_for_app_honours_goal_order():
    out = app_adapter.recommend_for_app(
        ARABLE,
        water="rain_only",
        soil="loamy",
        goal_order=["erosion", "organic_matter", "water"],
    )
    assert out["priorities"]["soil"] == 3.0
    assert out["priorities"]["organic_matter"] == 2.0
    assert out["priorities"]["water"] == 1.0
    assert out["priorities"]["income"] == 0
    assert out["results"]


def test_app_crop_ids_translate():
    assert app_adapter.crops_from_app_ids(["winter_wheat", "canola"]) == [
        "Winter wheat", "Winter oilseed rape",
    ]
    with pytest.raises(ValueError, match="no equivalent"):
        app_adapter.crops_from_app_ids(["soybean"])


def test_every_mapped_crop_exists_in_the_model(data):
    crops = data[0]
    assert set(app_adapter.APP_CROP_TO_MODEL.values()) <= set(crops)


def test_crop_choices_exclude_cover_crops(data):
    crops = data[0]
    choices = app_adapter.crop_choices(crops)
    assert "Winter wheat" in choices
    assert all(crops[c]["role"] != "cover" for c in choices)


def test_recommend_for_app_runs_end_to_end():
    out = app_adapter.recommend_for_app(ARABLE, water="rain_only", soil="loamy")
    assert len(out["results"]) == 3
    assert out["priorities"] == app_adapter.priorities_from_goals(app_adapter.DEFAULT_GOALS)


# --- live location climate (no network: bounds + rejection) ------------------


def test_uk_bounding_box():
    from team_model import live_climate

    assert live_climate.in_uk(51.8, -0.37)  # Rothamsted
    assert live_climate.in_uk(57.5, -4.0)  # Scottish Highlands
    assert not live_climate.in_uk(48.85, 2.35)  # Paris
    assert not live_climate.in_uk(42.0, -93.6)  # Iowa


def test_non_uk_location_rejected_before_any_fetch():
    # The UK-box check raises ValueError before NASA POWER is ever called.
    with pytest.raises(ValueError, match="outside the UK"):
        app_adapter.recommend_for_app(
            ARABLE, water="rain_only", soil="loamy", lat=48.85, lon=2.35
        )
