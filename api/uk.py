"""UK rotation model endpoints — team_model behind the /uk page."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, HTTPException
from fieldshift.engine.inputs_config import default_goal_order
from team_model import app_adapter, model
from ui.plans import uk_crop_tone, uk_recommendation_sentence

from api.presenters import uk_plan_list
from api.schemas import CropChoice, Fact, StationCheck, UkContext, UkOptions, UkRequest

router = APIRouter(prefix="/api/uk", tags=["uk"])

DEFAULT_ROTATION = [
    "Winter wheat",
    "Winter barley",
    "Winter oilseed rape",
    "Spring field beans",
    "Spring barley",
    "Sugar beet",
]
_STATION_SUMMARY = model.DATA_DIR / "processed" / "climate" / "station_vs_nasa_rain_summary.json"


def _months(ms: list[int]) -> str:
    """[10, 11, 12, 1] -> "Oct–Jan" when consecutive, else "Oct, Nov, Jan"."""
    if not ms:
        return "none"
    starts = [m for m in ms if ((m - 2) % 12) + 1 not in ms]
    if len(starts) == 1 and len(ms) > 1:
        first = starts[0]
        ordered = sorted(ms, key=lambda m: (m - first) % 12)
        return f"{model.MONTHS[ordered[0] - 1]}–{model.MONTHS[ordered[-1] - 1]}"
    return ", ".join(model.MONTHS[m - 1] for m in sorted(ms))


def _location(
    lat: float | None, lon: float | None
) -> tuple[dict[str, Any], dict[str, Any], Any, bool, str | None]:
    """(crops, farm, weather, at_location, error). Falls back to Broadbalk."""
    error: str | None = None
    if lat is not None and lon is not None:
        try:
            crops, _succ, farm, weather = app_adapter.load_location_data(lat, lon)
            return crops, farm, weather, True, None
        except ValueError as err:
            error = str(err)
        except RuntimeError as err:
            error = (
                f"NASA POWER could not be reached ({err}). "
                "Showing Rothamsted Broadbalk instead."
            )
    crops, _succ, farm, weather = app_adapter.load_data()
    return crops, farm, weather, False, error


def _station(farm: dict[str, Any]) -> StationCheck | None:
    if not _STATION_SUMMARY.exists():
        return None
    s = json.loads(_STATION_SUMMARY.read_text(encoding="utf-8"))
    near = s["nasa_point"]["distance_to_station_km"] < 30 and abs(
        s["nasa_point"]["latitude"] - float(farm["latitude"])
    ) < 0.01
    if not near:
        return None
    agree = s["monthly_agreement_corrected_station"]
    wet = s["wettest_10pct_of_months"]
    return StationCheck(
        period=s["period"],
        months_compared=s["months_compared"],
        nasa_mm=s["mean_annual_rain_mm"]["nasa_power"],
        gauge_mm=s["mean_annual_rain_mm"]["station_corrected"],
        bias_pct=agree["bias_pct"],
        correlation=agree["correlation"],
        mean_abs_error_mm=agree["mean_abs_error_mm"],
        wet_nasa_mm=wet["nasa_mean_mm"],
        wet_gauge_mm=wet["station_mean_mm"],
        wet_pct=wet["nasa_vs_station_pct"],
        source=s["station_source"],
    )


@router.get("/context", response_model=UkContext)
def uk_context(lat: float | None = None, lon: float | None = None) -> UkContext:
    crops, farm, weather, at_location, error = _location(lat, lon)
    real_farm = weather is not None

    if at_location:
        place = f"Your field at {lat:.3f}, {lon:.3f}"
        field_text = (
            f"NASA POWER daily climate for your point ({farm.get('years', '')}). The UK "
            "crop rules are applied to this location's weather — check them against "
            "local experience."
        )
    elif real_farm:
        place = "Rothamsted Broadbalk"
        field_text = (
            "Broadbalk at Rothamsted Research, Harpenden: the world's longest-running "
            "farm experiment, so the tool can be checked against real records."
        )
    else:
        place = "Test climate"
        field_text = "The NASA climate files were not found, so a made-up test climate is used."

    facts = [
        Fact(
            label="Rain in a year",
            value=f"{farm['annual_rain_mm']} mm",
            meaning=f"Wettest for bare soil: {_months(farm['wet_months'])}",
            source="NASA POWER" if real_farm else "Test value",
        ),
        Fact(
            label="Dry months",
            value=_months(farm["dry_months"]),
            meaning="Rain is less than evaporation",
            source="NASA POWER, Hargreaves ET0" if real_farm else "Test value",
        ),
    ]
    if real_farm:
        facts += [
            Fact(
                label="Summer rain",
                value=f"{farm['summer_rain_recent_mm']:.0f} mm",
                meaning=f"Was {farm['summer_rain_earlier_mm']:.0f} mm in "
                f"{farm['earlier_period']}",
                source=f"NASA POWER, Jun–Aug, {farm['recent_period']}",
            ),
            Fact(
                label="Hot days a year",
                value=f"{farm['hot_days_recent']:.0f}",
                meaning=f"Was {farm['hot_days_earlier']:.0f} in {farm['earlier_period']}",
                source=f"Days of 25 °C or more, {farm['recent_period']}",
            ),
        ]

    reliability = [
        "**Rules, not predictions.** Options are compared with each other. They are not "
        "yield or profit forecasts.",
        "**Approximate values.** Sowing months, crop roles, forage and residue levels, and "
        "the ranking rules are our estimates and need checking against AHDB guidance.",
        "**Frost limits are harsh.** FAO EcoCrop gives one killing temperature per species; "
        "UK varieties are often hardier, so frost warnings for barley, clover and ryegrass "
        "are likely overstated.",
        "**Satellite scale.** NASA POWER describes a grid cell about 50 km wide, not your "
        "field. Ground frost and local downpours can differ.",
    ]
    if not real_farm:
        reliability.append(
            "**Test climate in use.** Heat stress and daily frost were not checked."
        )

    return UkContext(
        place=place,
        live=real_farm,
        at_location=at_location,
        location_error=error,
        field_text=field_text,
        facts=facts,
        station=_station(farm) if real_farm else None,
        crop_choices=[
            CropChoice(id=name, name=name, tone=uk_crop_tone(name))
            for name in app_adapter.crop_choices(crops)
        ],
        default_rotation=DEFAULT_ROTATION,
        default_goal_order=default_goal_order(app_adapter.DEFAULT_GOALS),  # type: ignore[arg-type]
        reliability=reliability,
        data_sources=list(app_adapter.DATA_SOURCES),
    )


@lru_cache(maxsize=64)
def _recommend(
    current: tuple[str, ...],
    goal_order: tuple[str, ...],
    water: str,
    soil: str,
    warming_c: float,
    lat: float | None,
    lon: float | None,
) -> dict[str, Any]:
    return app_adapter.recommend_for_app(
        list(current),
        water=water,
        soil=soil,
        warming_c=warming_c,
        lat=lat,
        lon=lon,
        goal_order=list(goal_order),
    )


@router.post("/options", response_model=UkOptions)
def uk_options(body: UkRequest) -> UkOptions:
    crops, _farm, _weather, at_location, _error = _location(body.lat, body.lon)
    choices = set(app_adapter.crop_choices(crops))
    unknown = [c for c in body.crops if c not in choices]
    if unknown:
        raise HTTPException(422, f"The UK model has no crop called {unknown}.")
    try:
        out = _recommend(
            tuple(body.crops),
            tuple(body.goal_order),
            body.water,
            body.soil,
            float(body.warming_c),
            body.lat if at_location else None,
            body.lon if at_location else None,
        )
    except ValueError as err:
        raise HTTPException(422, str(err)) from err

    results = out["results"]
    banner = uk_recommendation_sentence(results)
    note = None
    if not banner:
        reasons = results[0].get("reasons") or []
        note = reasons[-1] if reasons else "No alternative rotation was found."
    return UkOptions(recommendation=banner, note=note, plans=uk_plan_list(results))
