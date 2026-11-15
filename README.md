# Field Shift

NASA Space Apps Challenge 2026 — crop-rotation decision support using NASA Earth data.

Field Shift helps a farmer answer one hard question: **given what the climate is
actually doing to my field, what should I grow next, and why?** The farmer enters a
field (coordinates on a map, or the built-in Rothamsted Broadbalk demo), their current
rotation, soil, water source and priorities. Field Shift pulls **20+ years of NASA POWER
daily climate data** for that exact point, builds a farm climate profile, and runs it
through a **transparent, rule-based agronomy engine** that returns the current rotation
plus two scored alternatives — each one explained: the benefits, the risks, the data
gaps, and what still needs a local expert. Nothing is a black box; every point in a
score traces back to a readable rule.

**UI:** Streamlit multipage app (`app.py` + `views/`). **Core:** plain Python package `fieldshift/`.
**UK rotation model:** rule-based engine in `team_model/`.
Routes: `/` (Home), `/field`, UK model, `/how-it-works`. Python **3.12** (see `.python-version`).

## What it does

- **Live NASA climate for any UK field.** Drop coordinates on the Home page and the
  model fetches NASA POWER daily data for that point (keyless), summarising rainfall,
  wet/dry months, frost windows, growing-season temperature and multi-year heat and
  drought trends.
- **Rotation comparison, not a single answer.** Returns the farmer's current rotation
  plus **Option A (best fit)** and **Option B (alternative)**, each with a score, the
  points behind it, benefits, risks, reasons and local-expert checks.
- **Explainable by design.** Every rotation is scored across nine agronomy "buckets"
  (soil, water, fertility, forage, organic matter, sequence, income, climate, change),
  weighted by the farmer's own priorities. You can read exactly why one rotation beat
  another.
- **Honest about uncertainty.** NASA satellite rainfall is checked against a physical
  ground rain gauge at Rothamsted (recording since 1853), and the difference is shown
  to the farmer rather than hidden.

## Architecture

Two independent engines share one UI:

| Engine | Lives in | Drives | What it is |
| --- | --- | --- | --- |
| **Global field engine** | `fieldshift/` | Field page | Earth Engine + NASA POWER field analysis (NDVI, ET0, suitability) for any point on Earth. |
| **UK rotation model** | `team_model/` | UK model page + Home live-coordinate flow | Rule-based crop-rotation scoring over 25 UK crops, FAO EcoCrop climate envelopes and a crop-successor matrix. |

- `team_model/model.py` — the rule engine: `recommend()`, `score()`, candidate
  generation, change-counting, climate suitability. Rotations stay within
  `MAX_ROTATION_YEARS` (5).
- `team_model/live_climate.py` — builds a farm climate summary + daily weather from
  NASA POWER for **any UK coordinates**, live (same maths as the committed Broadbalk
  files). Rejects locations outside the UK bounding box before any network call.
- `team_model/app_adapter.py` — the bridge between the Streamlit inputs (crop ids,
  goals 0–2, water/soil keys) and the model's vocabulary.

## Quick start

```bash
cp .env.example .env
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # runtime (Cloud / Docker)
# pip install -r requirements-dev.txt    # + pytest, ruff

# Optional: Earth Engine secrets (never commit)
# place service account JSON at secrets/ee-key.json
python tools/make_secrets.py          # local .streamlit/secrets.toml (path-based)
python tools/print_cloud_secrets.py   # secrets/cloud_secrets.toml for Cloud copy-paste

streamlit run app.py
```

Open http://localhost:8501

On Windows PowerShell the venv steps differ slightly:

```powershell
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Without Earth Engine secrets the app runs in **demo/mock mode**: the Field page uses
cached data, and the UK model runs on the committed Rothamsted Broadbalk climate.

### Lint & tests

```bash
pip install -r requirements-dev.txt
ruff check fieldshift ui views scripts tests app.py
pytest
```

The suite (`tests/`, 16 modules) covers the rule engine, the farmer-input bridge, the
Earth Engine services, ET0 maths, Streamlit page smoke tests and the live UK-climate
bounds. Run a single module with `pytest tests/test_team_model.py`, and use
`PYTHONIOENCODING=utf-8` on Windows if console output trips on Unicode.

### Data layer CLI (Phase 2)

```bash
python -m fieldshift.data.extract --lat 42.0 --lon -93.6 --size-ha 60
```

Processed climate and crop tables are rebuilt from the raw NASA POWER / EcoCrop
downloads by the scripts in `scripts/`:

```bash
python scripts/climate/standardize_nasa_power.py   # raw POWER -> clean daily CSV/parquet
python scripts/climate/build_farm_climate.py       # daily -> farm climate summary
python scripts/climate/compare_station_rain.py     # NASA POWER vs Rothamsted gauge
python scripts/crops/filter_uk_25_crops.py         # EcoCrop -> 25 UK crops
```

Convention: `data/raw/` holds inputs exactly as downloaded; `data/processed/` holds
script outputs (never hand-edited).

### Verify Earth Engine datasets (§4)

```bash
python tools/verify_ee.py
```

## Data & sources

| Source | Used for | Access |
| --- | --- | --- |
| **NASA POWER** (daily) | Rainfall, temperature, frost/heat days, ET0 inputs; MERRA-2 lineage | Keyless HTTP API |
| **Google Earth Engine** | Field-scale NDVI, field analysis on the Field page | Service-account key (optional) |
| **FAO EcoCrop** | Crop climate envelopes / suitability for 25 UK crops | Bundled in `data/` |
| **Crop-successor matrix** | How well crop B follows crop A (scores −3..+3) | Fenz et al. (2023) + UK agronomy, `raw/rotation/successor_matrix.csv` |
| **Rothamsted rain gauge** | Ground-truth check on NASA rainfall (since 1853) | Electronic Rothamsted Archive (CC BY 4.0) |

**Ground-truth validation (2000–2024, 300 months, Broadbalk grid cell):** NASA POWER
tracks the corrected gauge with correlation **0.87**, mean bias **−1.4%**, mean absolute
error **11.7 mm/month** — but underestimates the wettest 10% of months by **−22.1%**.
That gap is surfaced in the app as honest uncertainty, not smoothed away.
See `data/processed/climate/station_vs_nasa_rain_summary.json`.

## Project layout

```
app.py                     # Streamlit entry + top navigation
views/                     # Home, Field, UK model, How it works
fieldshift/                # global field engine (data, geo, models, services, engine)
team_model/                # UK rule-based rotation model + live climate + app adapter
scripts/                   # reproducible data-build scripts (climate, crops)
data/raw/ , data/processed/# inputs as downloaded / script outputs
tests/                     # pytest suite (engine, inputs, services, pages)
tools/                     # secrets + Earth Engine helpers
```

## Deploy — Streamlit Community Cloud

1. Push this repo to GitHub.
2. https://share.streamlit.io → **New app** · main file `app.py`.
3. **Advanced settings → Secrets:** paste from `.streamlit/secrets.toml.example` (or
   `secrets/cloud_secrets.toml` from `print_cloud_secrets.py`). Never commit real keys.
4. Deploy. Without secrets → demo/mock mode.

A `Dockerfile` and `docker-compose.yml` are included for container deploys, and
`render.yaml` for Render. The UK model and its Broadbalk demo need no secrets and work
in every deploy mode; only live Earth Engine field analysis needs the service account.

## Limitations & cut list

- **Scope:** the rotation model's crops and agronomy rules are **UK-specific**;
  coordinates outside the UK bounding box are rejected rather than scored on a foreign
  climate.
- **Advisory only:** Field Shift supports, it does not replace, a farmer's or
  agronomist's judgment. Below-surface facts (soil mineral nitrogen) are entered by the
  farmer, not sensed from space.
- **Satellite resolution:** NASA POWER is a grid cell (~0.5° × 0.625°), not a point
  reading; wettest-month rainfall is underestimated (see above).

Cut order if late (never SI model or evidence tagging): (a) Punjab demo, (b) live drawn-field analysis,
(c) timelapse, (d) docker-compose polish, (e) How-it-works depth.

## AI use

See [`AI_USAGE.md`](./AI_USAGE.md).
