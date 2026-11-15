"""Field report endpoints — the fieldshift engine behind the /field page."""

from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from fieldshift.cache import read_json
from fieldshift.data.ee_client import init_ee
from fieldshift.engine.candidates import season_label
from fieldshift.engine.crops import load_crops
from fieldshift.engine.inputs_config import (
    DEMO_FARM_ANSWERS,
    MONTH_SHIFT_DATA_GAP_THRESHOLD,
    default_goal_order,
    rank_goal_weights,
    resolve_soil_category,
    resolve_water_access,
)
from fieldshift.engine.slots import crops_for_slot
from fieldshift.engine.tiers import recommendation_sentence
from fieldshift.geo import polygon_area_ha, polygon_centroid
from fieldshift.models import (
    FieldConditions,
    GoalImportanceSet,
    PriorityWeights,
    ScenarioParams,
    StrategyRequest,
)
from fieldshift.services import (
    analyze_field,
    demo_data_through,
    generate_strategies,
    get_timelapse,
    get_validation,
    load_demo_conditions,
    load_field_features,
    using_mock_data,
)
from PIL import Image
from ui.charts import conditions_takeaway
from ui.explainers import FACT_HELP, chart_how_to_read
from ui.plans import best_fit_sentence
from ui.year_strip import MONTH_ABBR, month_range, months_from_text, short_name

from api.presenters import calendar_rows, crop_tone, field_plan_groups
from api.schemas import (
    AnalyzeRequest,
    AnalyzeResult,
    Anomalies,
    AnomalyMonth,
    CropChoice,
    CropSlot,
    Fact,
    FieldDetail,
    FieldOptions,
    FieldOptionsRequest,
    FieldSetup,
    MonthPoint,
    Reliability,
    Season,
    Timelapse,
)

router = APIRouter(prefix="/api/fields", tags=["field"])

FIELD_IDS = ("iowa", "uk", "punjab", "custom")
DEFAULT_ROTATION = {
    "iowa": ["maize", "soybean"],
    "uk": ["winter_wheat"],
    "punjab": ["rice", "winter_wheat"],
    "custom": ["maize", "soybean"],
}
TYPICAL_CROPS = {
    "iowa": ["maize", "soybean", "winter_wheat", "oats", "alfalfa", "red_clover"],
    "uk": ["winter_wheat", "barley", "canola", "field_pea", "oats", "spring_wheat"],
    "punjab": ["rice", "winter_wheat", "mung_bean", "maize", "cotton", "lentil"],
    "custom": ["maize", "soybean", "winter_wheat", "oats", "alfalfa", "red_clover"],
}
DEMO_ANSWERS_GAP = "Started from demo farm answers"
_TIMELAPSE_LABELS = {"ndvi": "Plant greenness (NDVI)", "rgb": "True colour (RGB)"}
DATASET_LABELS = {
    "ndvi_s2": "Plant greenness, Sentinel-2",
    "ndvi_landsat": "Plant greenness, Landsat",
    "ndvi_modis": "Plant greenness, MODIS",
    "rain_best_mm": "Rainfall, best available",
    "rain_mm": "Rainfall, GPM IMERG",
    "power_rain_mm": "Rainfall, NASA POWER",
    "era5_precip_mm": "Rainfall, ERA5",
    "power_t2m_c": "Air temperature, NASA POWER",
    "power_t2m_max_c": "Daily highs, NASA POWER",
    "power_t2m_min_c": "Daily lows, NASA POWER",
    "era5_t2m_c": "Air temperature, ERA5",
    "power_rh2m_pct": "Humidity, NASA POWER",
    "power_srad": "Sunshine, NASA POWER",
    "et0_mm": "Reference evaporation (FAO-56)",
    "era5_evap_mm": "Evaporation, ERA5",
    "era5_pet_mm": "Potential evaporation, ERA5",
    "water_balance_mm": "Water balance",
    "sm_surface": "Surface soil moisture, SMAP",
    "sm_rootzone": "Root-zone soil moisture, SMAP",
    "era5_soil_water": "Soil water, ERA5",
    "grace_lwe_cm": "Regional water storage, GRACE",
}


def _conditions(field_id: str) -> FieldConditions:
    if field_id not in FIELD_IDS:
        raise HTTPException(404, f"Unknown field {field_id!r}.")
    try:
        return load_demo_conditions(field_id)
    except FileNotFoundError as exc:
        if field_id == "custom":
            raise HTTPException(
                404, "No analyzed field yet. Draw or locate a field on the Home page."
            ) from exc
        raise HTTPException(404, str(exc)) from exc


def _is_demo_name(name: str | None) -> bool:
    return not name or "(demo)" in name.lower()


def _facts(field_id: str, conditions: FieldConditions, payload: dict) -> list[Fact]:
    feat = conditions.features
    if feat.frost_free_days:
        frost = f"{feat.frost_free_days:.0f} days"
    elif conditions.climate_label and "subtropical" in conditions.climate_label.lower():
        frost = "Rarely frosts"
    else:
        frost = "Not estimated yet"
    grace = (payload.get("coverage") or {}).get("grace_trend") or {}
    grace_cm = grace.get("trend_cm_per_yr")
    grace_value = (
        f"{grace_cm:+.1f} cm/yr" if grace_cm is not None else (grace.get("detail") or "")
    )

    def through(var: str) -> str:
        return demo_data_through(field_id, var) or "latest available"

    return [
        Fact(
            label="Bare soil window",
            value=feat.bare_months_label.split("(")[0].strip()
            if feat.bare_months_label
            else "Not estimated yet",
            meaning=FACT_HELP["bare"],
            source=f"Sentinel-2 plant greenness, data through {through('ndvi_s2')}",
        ),
        Fact(
            label="Frost-free days",
            value=frost,
            meaning=FACT_HELP["frost"],
            source=f"NASA POWER temperature, data through {through('power_t2m_c')}",
        ),
        Fact(
            label="Rain in a year",
            value=f"{feat.rain_annual_mm:.0f} mm" if feat.rain_annual_mm else "Not estimated yet",
            meaning=FACT_HELP["rain"],
            source=f"Best available rainfall, data through {through('rain_best_mm')}",
        ),
        Fact(
            label="Regional water storage",
            value=grace_value or "Not estimated yet",
            meaning=FACT_HELP["grace"],
            source=f"GRACE water storage, data through {through('grace_lwe_cm')}",
        ),
    ]


@lru_cache(maxsize=8)
def _gif_frames(path: str, mtime: float) -> tuple[bytes, ...]:
    _ = mtime
    im = Image.open(path)
    out: list[bytes] = []
    for i in range(getattr(im, "n_frames", 1)):
        im.seek(i)
        buf = io.BytesIO()
        im.convert("RGB").save(buf, format="PNG")
        out.append(buf.getvalue())
    return tuple(out)


def _timelapse_frames(field_id: str, index: str) -> tuple[bytes, ...] | None:
    tl = get_timelapse(field_id, index=index)
    path = tl.get("path")
    if not path or not Path(path).exists():
        return None
    return _gif_frames(path, Path(path).stat().st_mtime)


def _frame_months(field_id: str, n_frames: int) -> list[int] | None:
    """Frames are the 12 monthly composites ending at the extract's end month
    (tools/precompute_demo.py). Any other count means months were skipped: unknown."""
    meta = read_json(f"demo_{field_id}_meta.json", from_mock=False) or {}
    end = str(meta.get("end") or "")
    if n_frames != 12 or len(end) < 7 or not end[5:7].isdigit():
        return None
    end_month = int(end[5:7])
    return [(end_month - 12 + i) % 12 + 1 for i in range(12)]


@router.get("/{field_id}", response_model=FieldDetail)
def field_detail(field_id: str) -> FieldDetail:
    conditions = _conditions(field_id)
    payload = read_json(f"demo_{field_id}.json", from_mock=False) or {}
    feat = conditions.features
    name = conditions.name or ""
    ndvi_through = demo_data_through(field_id, "ndvi_s2")

    try:
        area: float | None = round(polygon_area_ha(conditions.polygon), 1)
    except Exception:  # noqa: BLE001 — malformed cached polygon: just omit the area
        area = None
    lat, lon = polygon_centroid(conditions.polygon)

    anoms = payload.get("anomalies") or {}
    months = []
    for v in anoms.get("vulnerable_seasons") or []:
        m = v.get("calendar_month")
        if isinstance(m, int) and 1 <= m <= 12:
            months.append(AnomalyMonth(month=m, label=MONTH_ABBR[m - 1], flags=v.get("n_flags", 1)))

    timelapse = []
    for index in ("ndvi", "rgb"):
        frames = _timelapse_frames(field_id, index)
        size = Image.open(io.BytesIO(frames[0])).size if frames else None
        timelapse.append(
            Timelapse(
                index=index,  # type: ignore[arg-type]
                label=_TIMELAPSE_LABELS[index],
                available=bool(frames),
                frames=len(frames or ()),
                size=size,
                months=_frame_months(field_id, len(frames)) if frames else None,
                message=None if frames else "Timelapse not available for this field yet.",
                data_through=ndvi_through,
            )
        )

    val = get_validation(field_id)
    cc = (val.cross_checks or payload.get("cross_checks") or {}).get("imerg_vs_power_rain")
    cross = (
        f"IMERG and NASA POWER monthly rain agree with r = {cc['r']:.2f} "
        f"over {cc.get('n_months', '—')} months."
        if cc and cc.get("r") is not None
        else None
    )

    coverage = sorted(
        (DATASET_LABELS.get(k, k.replace("_", " ")), str(v))
        for k, v in (payload.get("data_through") or {}).items()
    )
    answers = DEMO_FARM_ANSWERS.get(field_id) or DEMO_FARM_ANSWERS["iowa"]
    return FieldDetail(
        field_id=field_id,
        title=None if _is_demo_name(name) else name,
        climate_label=conditions.climate_label or None,
        watch_label="this field" if _is_demo_name(name) else name,
        area_ha=area,
        polygon=conditions.polygon,
        centroid=(lat, lon),
        facts=_facts(field_id, conditions, payload),
        season=Season(
            months=[
                MonthPoint(
                    month=p.month,
                    ndvi=p.ndvi,
                    rain_mm=p.rain_mm,
                    water_balance_mm=p.water_balance_mm,
                )
                for p in sorted(conditions.monthly_profile, key=lambda p: p.month)
            ],
            bare_months=list(feat.bare_months or []),
            stress_months=list(feat.stress_months or []),
            takeaway=conditions_takeaway(conditions),
            how_to_read=chart_how_to_read(),
            data_through=demo_data_through(field_id, "rain_best_mm"),
        ),
        anomalies=Anomalies(
            months=months,
            stress_label=feat.stress_months_label or "",
            uncertainty=anoms.get("uncertainty"),
            data_through=ndvi_through,
        ),
        timelapse=timelapse,
        reliability=Reliability(
            coverage=coverage,
            cross_check=cross,
        ),
        setup=FieldSetup(
            crops=list(DEFAULT_ROTATION.get(field_id, ["maize", "soybean"])),
            typical_crops=TYPICAL_CROPS.get(field_id, TYPICAL_CROPS["custom"]),
            cover=None,
            water=answers["water_category"],
            soil=answers["soil_category"],
            goal_order=default_goal_order(answers["goals"]),  # type: ignore[arg-type]
            demo=field_id in DEMO_FARM_ANSWERS,
        ),
        mock_data=using_mock_data(),
    )


@router.get("/{field_id}/timelapse/{index}/frames/{frame}")
def timelapse_frame(field_id: str, index: Literal["ndvi", "rgb"], frame: int) -> Response:
    _conditions(field_id)
    frames = _timelapse_frames(field_id, index)
    if not frames or not 0 <= frame < len(frames):
        raise HTTPException(404, "No such timelapse frame.")
    return Response(
        frames[frame],
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.post("/{field_id}/options", response_model=FieldOptions)
def field_options(field_id: str, body: FieldOptionsRequest) -> FieldOptions:
    """Score the farmer's answers. Same request the Streamlit Field page builds."""
    _conditions(field_id)
    known = {c["id"] for c in load_crops()}
    unknown = [c for c in [*body.crops, body.cover] if c and c not in known]
    if unknown:
        raise HTTPException(422, f"Unknown crop id(s): {unknown}")

    cash = list(body.crops)
    try:
        feats = load_field_features(field_id, current_rotation=cash)
    except FileNotFoundError:
        feats = {}

    cash_choices = [
        o for o in crops_for_slot({"kind": "cash"}, feats, always_allow=cash) if o["enabled"]
    ]
    names = {o["id"]: o["name"] for o in cash_choices}
    fallow = list(
        (feats.get("phenology") or {}).get("fallow_months")
        or (feats.get("bare_months") or {}).get("months")
        or []
    )
    cover_choices = [
        o
        for o in crops_for_slot(
            {"kind": "cover", "months": fallow},
            feats,
            always_allow=[body.cover] if body.cover else [],
        )
        if o["enabled"]
    ]
    cover = body.cover if body.cover in {o["id"] for o in cover_choices} else None

    slots: list[CropSlot] = []
    plant_overrides: dict[str, int] = {}
    harvest_overrides: dict[str, int] = {}
    month_gaps: list[str] = []
    calendar_items: list[tuple[str, list[int]]] = []
    for i, crop in enumerate(cash):
        detected = months_from_text(season_label(crop, feats)) or list(range(5, 11))
        det_plant, det_harvest = detected[0], detected[-1]
        pick = body.months[i] if i < len(body.months) else None
        plant = pick.plant if pick else det_plant
        harvest = pick.harvest if pick else det_harvest
        name = names.get(crop) or short_name(crop)
        if abs(plant - det_plant) > MONTH_SHIFT_DATA_GAP_THRESHOLD:
            month_gaps.append(
                f"Planting month for {name} moved >"
                f"{MONTH_SHIFT_DATA_GAP_THRESHOLD} month from satellite detection"
            )
            plant_overrides[crop] = plant
        if abs(harvest - det_harvest) > MONTH_SHIFT_DATA_GAP_THRESHOLD:
            month_gaps.append(
                f"Harvest month for {name} moved >"
                f"{MONTH_SHIFT_DATA_GAP_THRESHOLD} month from satellite detection"
            )
            harvest_overrides[crop] = harvest
        slots.append(
            CropSlot(
                id=crop,
                name=name,
                plant=plant,
                harvest=harvest,
                detected_plant=det_plant,
                detected_harvest=det_harvest,
            )
        )
        calendar_items.append((crop, month_range(plant, harvest)))
    if cover:
        calendar_items.append((cover, fallow))

    weights, importance, equal_note = rank_goal_weights(list(body.goal_order))
    water_access, water_gaps = resolve_water_access(body.water)
    soil_type, _awc, _inf, soil_gaps = resolve_soil_category(body.soil)
    input_gaps = water_gaps + soil_gaps + month_gaps
    if field_id in DEMO_FARM_ANSWERS:
        input_gaps.append(DEMO_ANSWERS_GAP)

    request = StrategyRequest(
        current_rotation=cash + ([cover] if cover else []),
        water_category=body.water,
        soil_category=body.soil,
        soil_type=soil_type,  # type: ignore[arg-type]
        water_access=water_access,  # type: ignore[arg-type]
        goal_importance=GoalImportanceSet(**importance),
        weights=PriorityWeights(**weights),
        scenario=ScenarioParams(rain_mult=body.rain_mult, temp_offset=body.temp_offset),
        plant_month_overrides=plant_overrides,
        harvest_month_overrides=harvest_overrides,
        input_data_gaps=input_gaps,
        input_confidence_penalty=bool(water_gaps or soil_gaps),
        equal_weights_note=equal_note,
    )
    cards = generate_strategies(field_id, request).strategies
    climate_shifted = abs(body.rain_mult - 1.0) > 1e-6 or body.temp_offset > 1e-6
    compare, others, unsuitable = field_plan_groups(cards, climate_shifted=climate_shifted)
    best = next((p for p in compare if p.role == "recommended"), None)
    if best:
        recommendation: str | None = best_fit_sentence(best.steps)
    else:
        recommendation = recommendation_sentence(cards) if cards else None

    return FieldOptions(
        cash_choices=[
            CropChoice(id=o["id"], name=o["name"], tone=crop_tone(o["id"])) for o in cash_choices
        ],
        cover_choices=[
            CropChoice(id=o["id"], name=o["name"], tone=crop_tone(o["id"])) for o in cover_choices
        ],
        cover=cover,
        slots=slots,
        farm_year=calendar_rows(calendar_items),
        recommendation=recommendation,
        note=equal_note,
        compare=compare,
        others=others,
        unsuitable=unsuitable,
    )


@router.post("/analyze", response_model=AnalyzeResult)
def analyze(body: AnalyzeRequest) -> AnalyzeResult:
    """Live Earth Engine + NASA POWER analysis (about a minute). Result id is 'custom'."""
    init_ee()
    try:
        analyze_field(body.polygon, name=body.name)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return AnalyzeResult(field_id="custom")
