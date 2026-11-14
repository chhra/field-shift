"""Pydantic v2 schemas — internal data contracts for the fieldshift package + Streamlit UI."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low"]
# Engine water access (resolved from farmer categories).
WaterAccess = Literal["rainfed", "limited", "irrigated"]
SoilType = Literal["sand", "loam", "clay", "silt", "unknown"]
TimelapseIndex = Literal["ndvi", "rgb"]
StrategyTier = Literal["best_fit", "worth_considering", "baseline", "not_suitable"]
# Farmer-facing categories (see inputs_config.py).
WaterCategory = Literal[
    "rain_only", "some_irrigation", "fully_irrigated", "not_sure"
]
SoilCategory = Literal["sandy", "loamy", "silty", "clay", "not_sure"]
GoalImportance = Literal[0, 1, 2]


class HealthResponse(BaseModel):
    """Liveness / mode probe."""

    status: str = "ok"
    demo_mode: bool
    version: str = "0.1.0"
    phase: str = "1-scaffold"


class DemoField(BaseModel):
    """A pre-loaded demo field listed on the home page."""

    id: str
    name: str
    country: str
    polygon: dict[str, Any]
    climate_label: str


class EvidenceItem(BaseModel):
    """A single evidence string tagged with its dataset source."""

    text: str
    source: str
    data_through: str | None = None


class ScoreSet(BaseModel):
    """Per-criterion scores in [0, 1] plus weighted total.

    Exactly six farmer goals, in display order.
    """

    water: float
    forage: float
    nitrogen: float
    erosion: float
    organic_matter: float
    market: float
    total: float


class CropInSequence(BaseModel):
    """One crop slot in a rotation sequence."""

    crop_id: str
    months: str
    # Satellite-detected planting/harvest (1–12); optional overrides from farmer.
    plant_month: int | None = None
    harvest_month: int | None = None


class GoalImportanceSet(BaseModel):
    """0 = Not important, 1 = Important, 2 = Very important."""

    water: GoalImportance = 1
    forage: GoalImportance = 0
    nitrogen: GoalImportance = 1
    erosion: GoalImportance = 1
    organic_matter: GoalImportance = 1
    market: GoalImportance = 1


class PriorityWeights(BaseModel):
    """Normalized or raw relative weights for the six goals.

    ``score_strategy`` normalizes by sum; all-zero is handled via inputs_config.
    """

    water: float = 1.0
    forage: float = 0.0
    nitrogen: float = 1.0
    erosion: float = 1.0
    organic_matter: float = 1.0
    market: float = 1.0


class FarmConstraints(BaseModel):
    """Legacy shell kept for API compatibility — machinery/buyers removed.

    Water/soil filtering is applied in candidates + scoring, not here.
    """

    pass


class StrategyCard(BaseModel):
    """One rotation strategy shown to the farmer."""

    id: str
    name: str
    sequence: list[CropInSequence]
    scores: ScoreSet
    delta_vs_current: dict[str, float]
    why: str
    evidence: list[EvidenceItem]
    benefits: list[str]
    data_gaps: list[str]
    risks_for_local_review: list[str]
    confidence: Confidence
    tier: StrategyTier | None = None
    tier_label: str = ""
    tier_reason: str = ""
    unsuitable_reasons: list[str] = Field(default_factory=list)
    soft_notes: list[str] = Field(default_factory=list)


class ScenarioParams(BaseModel):
    """What-if adjustments applied before re-scoring."""

    rain_mult: float = Field(default=1.0, ge=0.7, le=1.3)
    temp_offset: float = Field(default=0.0, ge=0.0, le=3.0)


class StrategyRequest(BaseModel):
    """Body for strategy generation from the Field page."""

    current_rotation: list[str]
    water_category: WaterCategory = "rain_only"
    soil_category: SoilCategory = "loamy"
    # Resolved engine fields (filled by services / UI before generate).
    soil_type: SoilType = "loam"
    water_access: WaterAccess = "rainfed"
    goal_importance: GoalImportanceSet = Field(default_factory=GoalImportanceSet)
    weights: PriorityWeights = Field(default_factory=PriorityWeights)
    constraints: FarmConstraints = Field(default_factory=FarmConstraints)
    scenario: ScenarioParams = Field(default_factory=ScenarioParams)
    # Farmer-moved planting months vs satellite (crop_id → plant month 1–12).
    plant_month_overrides: dict[str, int] = Field(default_factory=dict)
    harvest_month_overrides: dict[str, int] = Field(default_factory=dict)
    # Extra data gaps from UI (Not sure, month shifts, equal-weights note).
    input_data_gaps: list[str] = Field(default_factory=list)
    input_confidence_penalty: bool = False
    equal_weights_note: str | None = None


class StrategyResult(BaseModel):
    """Response containing ranked strategy cards."""

    field_id: str
    strategies: list[StrategyCard]


class MonthlySeriesPoint(BaseModel):
    """One calendar-month climatology / profile point."""

    month: int = Field(ge=1, le=12)
    ndvi: float | None = None
    soil_moisture: float | None = None
    rain_mm: float | None = None
    water_balance_mm: float | None = None
    temperature_c: float | None = None


class FieldFeatures(BaseModel):
    """Derived field features from the harmonized monthly table."""

    bare_months: list[int] = Field(default_factory=list)
    bare_months_label: str = ""
    stress_months: list[int] = Field(default_factory=list)
    stress_months_label: str = ""
    frost_window_label: str = ""
    frost_free_days: float | None = None
    gdd_annual: float | None = None
    heat_days_trend: str = ""
    rain_annual_mm: float | None = None
    rain_cv: float | None = None
    slope_pct_mean: float | None = None
    erosion_risk: float | None = None
    water_deficit_annual_mm: float | None = None
    data_coverage_note: str = ""


class FieldConditions(BaseModel):
    """Full conditions payload for a field page."""

    field_id: str
    name: str
    country: str
    climate_label: str
    polygon: dict[str, Any]
    monthly_profile: list[MonthlySeriesPoint]
    features: FieldFeatures
    timelapse_url: str | None = None
    sources_used: list[str] = Field(default_factory=list)
    us_module: dict[str, Any] | None = None
    cross_checks: dict[str, Any] | None = None


class AnalyzeRequest(BaseModel):
    """Body for analyze."""

    polygon: dict[str, Any]
    name: str | None = None


class TimelapseResponse(BaseModel):
    """Time-lapse GIF/URL for a field."""

    url: str
    frames: int | None = None
    start: str | None = None
    end: str | None = None
    cached_static: bool = False


class CropSummary(BaseModel):
    """Crop list entry for dropdowns."""

    id: str
    name: str
    type: Literal["cover", "cash", "forage"]
    family: str
    season: Literal["cool", "warm"]


class DataSourceMeta(BaseModel):
    """One dataset row for the About page."""

    purpose: str
    name: str
    id_or_access: str
    resolution: str
    link: str


class UsModuleResponse(BaseModel):
    """US enhancement payload. Empty/null parts until Phase 7."""

    in_conus: bool | None = None
    detected_rotation: list[str] | None = None
    soil: dict[str, Any] | None = None
    prices: dict[str, Any] | None = None
    county_yields: dict[str, Any] | None = None
    rain_validation: dict[str, Any] | None = None
    errors: list[str] = Field(default_factory=list)


class ValidationResponse(BaseModel):
    """Cross-check statistics. Empty until Phase 7."""

    cross_checks: dict[str, Any] | None = None
    errors: list[str] = Field(default_factory=list)


class ErrorDetail(BaseModel):
    """Consistent API error body."""

    detail: str
