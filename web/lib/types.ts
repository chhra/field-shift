// Mirrors api/schemas.py. Responses carry words, roles and calendars — never scores.

export type WaterKey = "rain_only" | "some_irrigation" | "fully_irrigated" | "not_sure";
export type SoilKey = "sandy" | "loamy" | "silty" | "clay" | "not_sure";
export type GoalKey = "water" | "forage" | "nitrogen" | "erosion" | "organic_matter" | "market";
export type PlanRole = "current" | "recommended" | "alternative" | "other" | "unsuitable";

export interface CalendarSegment {
  start: number;
  span: number;
  crop_id: string | null;
  name: string;
  cover: boolean;
  tone: string;
  title: string;
}

export interface CalendarRow {
  label: string | null;
  summary: string;
  segments: CalendarSegment[];
}

export interface Evidence {
  text: string;
  source: string;
  data_through: string | null;
}

export interface PlanDetails {
  why: string | null;
  benefits: string[];
  evidence: Evidence[];
  gaps: string[];
  risks: string[];
  checks: string[];
  confidence: string | null;
}

export interface Plan {
  key: string;
  role: PlanRole;
  eyebrow: string;
  title: string;
  steps: string[];
  meta: string;
  blurb: string;
  features: string[];
  featured: boolean;
  flags: string[];
  flag_tone: "note" | "bad";
  calendar: CalendarRow[];
  details: PlanDetails;
}

export interface Fact {
  label: string;
  value: string;
  meaning: string;
  source: string;
}

export interface Choice {
  key: string;
  label: string;
  hint: string | null;
}

export interface CropChoice {
  id: string;
  name: string;
}

export interface InputsMeta {
  questions: Record<string, { title: string; why: string }>;
  water: Choice[];
  water_help: string;
  soil: Choice[];
  soil_help: string;
  goals: Choice[];
  no_goals_note: string;
  max_crops: number;
}

export interface MonthPoint {
  month: number;
  ndvi: number | null;
  rain_mm: number | null;
  water_balance_mm: number | null;
}

export interface FieldDetail {
  field_id: string;
  title: string | null;
  climate_label: string | null;
  watch_label: string;
  area_ha: number | null;
  polygon: GeoJSONPolygon;
  centroid: [number, number];
  facts: Fact[];
  season: {
    months: MonthPoint[];
    bare_months: number[];
    stress_months: number[];
    takeaway: string;
    how_to_read: string;
    data_through: string | null;
  };
  anomalies: {
    months: { month: number; label: string; flags: number }[];
    stress_label: string;
    uncertainty: string | null;
    data_through: string | null;
  };
  timelapse: {
    index: "ndvi" | "rgb";
    label: string;
    available: boolean;
    frames: number;
    size: [number, number] | null;
    message: string | null;
    data_through: string | null;
  }[];
  reliability: { coverage: [string, string][]; cross_check: string | null };
  setup: {
    crops: string[];
    typical_crops: string[];
    cover: string | null;
    water: WaterKey;
    soil: SoilKey;
    goal_order: GoalKey[];
    demo: boolean;
  };
  mock_data: boolean;
}

export interface MonthPick {
  plant: number;
  harvest: number;
}

export interface FieldOptionsRequest {
  crops: string[];
  cover: string | null;
  months: (MonthPick | null)[];
  water: WaterKey;
  soil: SoilKey;
  goal_order: GoalKey[];
  rain_mult: number;
  temp_offset: number;
}

export interface CropSlot {
  id: string;
  name: string;
  plant: number;
  harvest: number;
  detected_plant: number;
  detected_harvest: number;
}

export interface FieldOptions {
  cash_choices: CropChoice[];
  cover_choices: CropChoice[];
  cover: string | null;
  slots: CropSlot[];
  farm_year: CalendarRow[];
  recommendation: string | null;
  note: string | null;
  compare: Plan[];
  others: Plan[];
  unsuitable: Plan[];
}

export interface GeoJSONPolygon {
  type: "Polygon";
  coordinates: [number, number][][];
}

export interface Square {
  polygon: GeoJSONPolygon;
  area_ha: number;
  in_uk: boolean;
}

export interface Status {
  live: boolean;
  mock_data: boolean;
}

export interface StationCheck {
  period: string;
  months_compared: number;
  nasa_mm: number;
  gauge_mm: number;
  bias_pct: number;
  correlation: number;
  mean_abs_error_mm: number;
  wet_nasa_mm: number;
  wet_gauge_mm: number;
  wet_pct: number;
  source: string;
}

export interface UkContext {
  place: string;
  live: boolean;
  at_location: boolean;
  location_error: string | null;
  field_text: string;
  facts: Fact[];
  station: StationCheck | null;
  crop_choices: string[];
  default_rotation: string[];
  default_goal_order: GoalKey[];
  reliability: string[];
  data_sources: [string, string][];
}

export interface UkRequest {
  crops: string[];
  water: WaterKey;
  soil: SoilKey;
  goal_order: GoalKey[];
  warming_c: number;
  lat: number | null;
  lon: number | null;
}

export interface UkOptions {
  recommendation: string | null;
  note: string | null;
  plans: Plan[];
}

export interface HowItWorks {
  pipeline: string[];
  inputs: { title: string; body: string; options?: string[] }[];
  goals: { key: GoalKey; label: string; hint: string; plain: string; measured: string }[];
  goal_order_note: string;
  soil_table: {
    rows: { soil: string; awc_mm_per_m: number; infiltration_mm_h: number }[];
    source: string;
  };
  irrigation_note: string;
  sources: { purpose: string; name: string; access: string; resolution: string; link: string }[];
  sources_through: string | null;
  thresholds: { name: string; value: number; meaning: string }[];
  benefits_note: string;
  standard_risks: string[];
  glossary: { term: string; definition: string }[];
}
