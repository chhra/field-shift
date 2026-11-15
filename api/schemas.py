"""Request and response models for the web API.

Responses carry words, roles and calendars only — engine scores and goal weights
never leave the server.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

WaterKey = Literal["rain_only", "some_irrigation", "fully_irrigated", "not_sure"]
SoilKey = Literal["sandy", "loamy", "silty", "clay", "not_sure"]
GoalKey = Literal["water", "forage", "nitrogen", "erosion", "organic_matter", "market"]
PlanRole = Literal["current", "recommended", "alternative", "other", "unsuitable"]


# --- Shared pieces -----------------------------------------------------------


class CalendarSegment(BaseModel):
    start: int = Field(description="First month, 1 = January")
    span: int
    crop_id: str | None
    name: str
    cover: bool
    tone: str = Field(description="Colour key: bare, other, poaceae, fabaceae-alt, …")
    title: str


class CalendarRow(BaseModel):
    label: str | None
    summary: str
    segments: list[CalendarSegment]


class Evidence(BaseModel):
    text: str
    source: str
    data_through: str | None = None


class PlanDetails(BaseModel):
    why: str | None = None
    benefits: list[str] = []
    evidence: list[Evidence] = []
    gaps: list[str] = []
    risks: list[str] = []
    checks: list[str] = []
    confidence: str | None = None


class Plan(BaseModel):
    key: str
    role: PlanRole
    eyebrow: str
    title: str
    meta: str = ""
    blurb: str = ""
    features: list[str] = []
    featured: bool = False
    flags: list[str] = []
    flag_tone: Literal["note", "bad"] = "note"
    calendar: list[CalendarRow] = []
    details: PlanDetails


class Fact(BaseModel):
    label: str
    value: str
    meaning: str
    source: str


class Choice(BaseModel):
    key: str
    label: str
    hint: str | None = None


class CropChoice(BaseModel):
    id: str
    name: str


# --- Inputs metadata ---------------------------------------------------------


class Question(BaseModel):
    title: str
    why: str


class InputsMeta(BaseModel):
    questions: dict[str, Question]
    water: list[Choice]
    water_help: str
    soil: list[Choice]
    soil_help: str
    goals: list[Choice]
    no_goals_note: str
    max_crops: int


# --- Field -------------------------------------------------------------------


class MonthPoint(BaseModel):
    month: int
    ndvi: float | None
    rain_mm: float | None
    water_balance_mm: float | None


class Season(BaseModel):
    months: list[MonthPoint]
    bare_months: list[int]
    stress_months: list[int]
    takeaway: str
    how_to_read: str
    data_through: str | None


class AnomalyMonth(BaseModel):
    month: int
    label: str
    flags: int


class Anomalies(BaseModel):
    months: list[AnomalyMonth]
    stress_label: str
    uncertainty: str | None
    data_through: str | None


class Timelapse(BaseModel):
    index: Literal["ndvi", "rgb"]
    label: str
    available: bool
    frames: int
    message: str | None
    data_through: str | None


class Reliability(BaseModel):
    coverage: list[tuple[str, str]]
    cross_check: str | None


class FieldSetup(BaseModel):
    crops: list[str]
    cover: str | None
    water: WaterKey
    soil: SoilKey
    goal_order: list[GoalKey]
    demo: bool


class FieldDetail(BaseModel):
    field_id: str
    title: str | None
    climate_label: str | None
    watch_label: str
    area_ha: float | None
    polygon: dict[str, Any]
    centroid: tuple[float, float]
    facts: list[Fact]
    season: Season
    anomalies: Anomalies
    timelapse: list[Timelapse]
    reliability: Reliability
    setup: FieldSetup
    mock_data: bool


class MonthPick(BaseModel):
    plant: int = Field(ge=1, le=12)
    harvest: int = Field(ge=1, le=12)


class FieldOptionsRequest(BaseModel):
    crops: list[str] = Field(min_length=1, max_length=6)
    cover: str | None = None
    months: list[MonthPick | None] = Field(
        default=[], description="Optional plant/harvest month per crop slot, same order"
    )
    water: WaterKey = "rain_only"
    soil: SoilKey = "loamy"
    goal_order: list[GoalKey] = []
    rain_mult: float = Field(1.0, ge=0.7, le=1.3)
    temp_offset: float = Field(0.0, ge=0.0, le=3.0)


class CropSlot(BaseModel):
    id: str
    name: str
    plant: int
    harvest: int
    detected_plant: int
    detected_harvest: int


class FieldOptions(BaseModel):
    cash_choices: list[CropChoice]
    cover_choices: list[CropChoice]
    cover: str | None
    slots: list[CropSlot]
    farm_year: list[CalendarRow]
    recommendation: str | None
    note: str | None
    compare: list[Plan]
    others: list[Plan]
    unsuitable: list[Plan]


class AnalyzeRequest(BaseModel):
    polygon: dict[str, Any]
    name: str | None = None


class AnalyzeResult(BaseModel):
    field_id: str


class Square(BaseModel):
    polygon: dict[str, Any]
    area_ha: float
    in_uk: bool


class Status(BaseModel):
    live: bool
    mock_data: bool


# --- UK model ----------------------------------------------------------------


class StationCheck(BaseModel):
    period: str
    months_compared: int
    nasa_mm: float
    gauge_mm: float
    bias_pct: float
    correlation: float
    mean_abs_error_mm: float
    wet_nasa_mm: float
    wet_gauge_mm: float
    wet_pct: float
    source: str


class UkContext(BaseModel):
    place: str
    live: bool
    at_location: bool
    location_error: str | None
    field_text: str
    facts: list[Fact]
    station: StationCheck | None
    crop_choices: list[str]
    default_rotation: list[str]
    default_goal_order: list[GoalKey]
    reliability: list[str]
    data_sources: list[tuple[str, str]]


class UkRequest(BaseModel):
    crops: list[str] = Field(min_length=1, max_length=6)
    water: WaterKey = "rain_only"
    soil: SoilKey = "loamy"
    goal_order: list[GoalKey] = []
    warming_c: float = Field(0.0, ge=0.0, le=3.0)
    lat: float | None = None
    lon: float | None = None


class UkOptions(BaseModel):
    recommendation: str | None
    note: str | None
    plans: list[Plan]
