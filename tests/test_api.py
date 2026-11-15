"""Web API: real engines behind the endpoints, and no scores in the payloads."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")

from api.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)


def _iowa_body(**over: object) -> dict:
    setup = client.get("/api/fields/iowa").json()["setup"]
    body = {
        "crops": setup["crops"],
        "water": setup["water"],
        "soil": setup["soil"],
        "goal_order": setup["goal_order"],
    }
    body.update(over)
    return body


def test_field_detail_hides_demo_placename() -> None:
    r = client.get("/api/fields/iowa")
    assert r.status_code == 200
    data = r.json()
    assert data["title"] is None
    assert data["watch_label"] == "this field"
    assert "Iowa" not in json.dumps(data["facts"])
    assert len(data["season"]["months"]) == 12


def test_unknown_field_is_404() -> None:
    assert client.get("/api/fields/nowhere").status_code == 404


def test_field_options_return_plans_without_scores() -> None:
    r = client.post("/api/fields/iowa/options", json=_iowa_body())
    assert r.status_code == 200
    data = r.json()
    roles = [p["role"] for p in data["compare"]]
    assert roles[0] == "current"
    assert all(p["calendar"] for p in data["compare"])
    text = json.dumps(data).lower()
    for banned in ('"score', '"scores"', '"weights"', '"total"', '"points"'):
        assert banned not in text


def test_goal_order_changes_the_recommendation() -> None:
    market_first = client.post("/api/fields/iowa/options", json=_iowa_body()).json()
    soil_first = client.post(
        "/api/fields/iowa/options",
        json=_iowa_body(goal_order=["erosion", "organic_matter", "nitrogen"]),
    ).json()
    assert market_first["recommendation"] != soil_first["recommendation"]
    assert any(p["role"] == "recommended" for p in soil_first["compare"])


def test_month_override_shifts_the_farm_year() -> None:
    body = _iowa_body(months=[{"plant": 4, "harvest": 9}, None])
    data = client.post("/api/fields/iowa/options", json=body).json()
    assert data["slots"][0]["plant"] == 4
    first = data["farm_year"][0]["segments"]
    maize = next(s for s in first if s["crop_id"] == "maize")
    assert maize["start"] == 4


def test_unknown_crop_is_422() -> None:
    r = client.post("/api/fields/iowa/options", json=_iowa_body(crops=["moon_cheese"]))
    assert r.status_code == 422


def test_uk_context_and_options() -> None:
    ctx = client.get("/api/uk/context").json()
    assert ctx["crop_choices"]
    body = {"crops": ctx["default_rotation"][:3], "goal_order": ctx["default_goal_order"]}
    data = client.post("/api/uk/options", json=body).json()
    assert data["plans"][0]["role"] == "current"
    assert data["plans"][0]["calendar"]
    assert "score" not in json.dumps(data).lower()


def test_uk_unknown_crop_is_422() -> None:
    r = client.post("/api/uk/options", json={"crops": ["Moon cheese"]})
    assert r.status_code == 422


def test_square_reports_uk_membership() -> None:
    r = client.get("/api/geo/square", params={"lat": 52.205, "lon": 0.085, "size_ha": 25})
    data = r.json()
    assert data["in_uk"] is True
    assert 20 < data["area_ha"] < 30


def test_inputs_meta_has_no_streamlit_icon_codes() -> None:
    data = client.get("/api/meta/inputs").json()
    assert ":material/" not in json.dumps(data)
    assert len(data["goals"]) == 6
