"""Status, shared input choices, geometry help and How-it-works content."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from fieldshift.cache import read_json
from fieldshift.data.ee_client import init_ee
from fieldshift.engine import thresholds as th
from fieldshift.engine.inputs_config import (
    GOAL_HINTS,
    GOAL_KEYS,
    GOAL_LABELS,
    GOAL_MEASURED,
    GOAL_PLAIN,
    LIMITED_IRRIGATION_ALLOWANCE,
    NO_GOALS_NOTE,
    QUESTIONS,
    SOIL_AWC_MM_PER_M,
    SOIL_HELP,
    SOIL_HINT,
    SOIL_INFILTRATION_MM_H,
    SOIL_LABELS,
    SOIL_TEXTURE_META,
    SOIL_TILES,
    SOIL_WHY,
    WATER_HELP,
    WATER_HINT,
    WATER_LABELS,
    WATER_TILES,
    WATER_WHY,
)
from fieldshift.geo import polygon_area_ha, polygon_from_point
from fieldshift.services import list_sources, using_mock_data
from team_model.live_climate import in_uk
from ui.glossary import GLOSSARY

from api.presenters import strip_icon
from api.schemas import Choice, InputsMeta, Question, Square, Status

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/status", response_model=Status)
def status() -> Status:
    ee = init_ee()
    return Status(live=bool(ee.initialized and not ee.demo_mode), mock_data=using_mock_data())


@router.get("/meta/inputs", response_model=InputsMeta)
def inputs_meta() -> InputsMeta:
    soil = []
    for key, tile in SOIL_TILES.items():
        label, _, hint = tile.partition(" · ")
        soil.append(Choice(key=key, label=label, hint=hint or None))
    return InputsMeta(
        questions={k: Question(title=t, why=w) for k, (t, w) in QUESTIONS.items()},
        water=[Choice(key=k, label=strip_icon(v)) for k, v in WATER_TILES.items()],
        water_help=WATER_HELP,
        soil=soil,
        soil_help=SOIL_HELP,
        goals=[Choice(key=k, label=GOAL_LABELS[k], hint=GOAL_HINTS[k]) for k in GOAL_KEYS],
        no_goals_note=NO_GOALS_NOTE,
        max_crops=6,
    )


@router.get("/geo/square", response_model=Square)
def square(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    size_ha: float = Query(25.0, ge=1, le=5000),
) -> Square:
    """A square field outline of ``size_ha`` around a point (Home → coordinates)."""
    poly = polygon_from_point(lat, lon, size_ha)
    return Square(polygon=poly, area_ha=round(polygon_area_ha(poly), 1), in_uk=in_uk(lat, lon))


@router.get("/meta/how-it-works")
def how_it_works() -> dict[str, Any]:
    iowa = read_json("demo_iowa.json", from_mock=False) or {}
    through = (iowa.get("data_through") or {}).get("ndvi_s2")
    return {
        "pipeline": [
            "Reduce satellite and weather datasets to field-by-month values.",
            "Derive bare months, stress months, the frost window, water balance and trends.",
            "Flag unusual seasons with an IsolationForest anomaly model.",
            "Generate rotation candidates: your rotation, cover crops and crop swaps.",
            "Rank the options by the six goals in the order you set.",
            "Show your rotation, a recommended option and an alternative, with benefits "
            "and risks.",
        ],
        "inputs": [
            {
                "title": "Your field",
                "body": "Confirm the outline satellites watch, drawn on the map or "
                "opened from the demo.",
            },
            {
                "title": "What you grow now",
                "body": "How many crops, then each crop in order. Planting and harvest "
                "months stay tucked away unless satellites got them wrong.",
            },
            {
                "title": "Where your water comes from",
                "body": f"{WATER_HINT} {WATER_WHY}",
                "options": list(WATER_LABELS.values()),
            },
            {
                "title": "Your soil",
                "body": f"{SOIL_HINT} {SOIL_WHY}",
                "options": list(SOIL_LABELS.values()),
            },
            {
                "title": "What matters most to you",
                "body": "Put the goals in order and remove any that don't matter.",
            },
        ],
        "goals": [
            {
                "key": k,
                "label": GOAL_LABELS[k],
                "hint": GOAL_HINTS[k],
                "plain": GOAL_PLAIN[k],
                "measured": GOAL_MEASURED[k],
            }
            for k in GOAL_KEYS
        ],
        "goal_order_note": (
            "You only ever see places (1st, 2nd, …), never percentages. Behind the scenes, "
            "with n goals listed, 1st counts n, 2nd n − 1, … last 1. Removed goals count 0. "
            "With no goals left, every goal counts the same."
        ),
        "soil_table": {
            "rows": [
                {
                    "soil": SOIL_LABELS[k],
                    "awc_mm_per_m": SOIL_AWC_MM_PER_M[k],
                    "infiltration_mm_h": SOIL_INFILTRATION_MM_H[k],
                }
                for k in ("sandy", "loamy", "silty", "clay")
            ],
            "source": SOIL_TEXTURE_META["source"],
        },
        "irrigation_note": (
            f"“Some irrigation” adds {LIMITED_IRRIGATION_ALLOWANCE:.2f} to the water measure "
            "on a 0–1 scale — a documented project constant awaiting expert review."
        ),
        "sources": [
            {
                "purpose": s.purpose,
                "name": s.name,
                "access": s.id_or_access,
                "resolution": s.resolution,
                "link": s.link,
            }
            for s in list_sources()
        ],
        "sources_through": through,
        "thresholds": [
            {
                "name": "Best fit margin",
                "value": th.BEST_FIT_MIN_DELTA,
                "meaning": "The recommended option must beat your rotation by at least this.",
            },
            {
                "name": "About the same",
                "value": th.DELTA_NEUTRAL_THRESHOLD,
                "meaning": "Smaller differences read as “about the same as yours”.",
            },
            {
                "name": "Worth considering",
                "value": th.WORTH_CONSIDERING_OF_BEST,
                "meaning": "Options this close to the best are listed as alternatives.",
            },
            {
                "name": "Not suitable",
                "value": th.NOT_SUITABLE_TOTAL_DELTA,
                "meaning": "Options this far below your rotation are set aside.",
            },
        ],
        "benefits_note": (
            "Some benefits are shown but never change the ranking: pest-cycle breaks, "
            "better infiltration from cover and deep roots, extra forage or cover income, "
            "and lower water demand than your rotation."
        ),
        "standard_risks": [
            "Machinery and labour",
            "Seed availability",
            "Local prices and buyers",
            "Pest and herbicide carryover",
        ],
        "glossary": [{"term": t, "definition": d} for t, d in GLOSSARY.items()],
    }
