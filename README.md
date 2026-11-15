# Field Shift

NASA Space Apps Challenge 2026 — crop-rotation decision support using NASA Earth data.

**UI:** Next.js web app (`web/`) on a FastAPI layer (`api/`). **Core:** plain Python packages
`fieldshift/` (Field engine) and `team_model/` (UK rotation rules); the API wraps them, it does
not reimplement them. Routes: `/` (Home), `/field`, `/uk`, `/how-it-works`.
Python **3.12** (see `.python-version`), Node **20+**.

The Streamlit app (`app.py` + `views/`) is **legacy**: it still runs and shares the same
presenters (`ui/plans.py`, `ui/year_strip.py`), but new UI work goes into `web/`.

## Quick start

```bash
cp .env.example .env
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r api/requirements.txt      # engines + FastAPI
# pip install -r requirements-dev.txt    # + pytest, ruff

# Optional: Earth Engine secrets (never commit)
# place service account JSON at secrets/ee-key.json
python tools/make_secrets.py          # local .streamlit/secrets.toml (path-based)
python tools/print_cloud_secrets.py   # secrets/cloud_secrets.toml for Cloud copy-paste
```

Run the API and the web app in two terminals:

```bash
PYTHONPATH=. uvicorn api.main:app --reload --port 8000   # http://127.0.0.1:8000/docs

cd web && npm install && npm run dev                     # http://localhost:3000
```

The web app proxies `/api/*` to `FIELD_SHIFT_API_URL` (default `http://127.0.0.1:8000`).
The API allows browser origins from `FIELD_SHIFT_WEB_ORIGINS` (default `http://localhost:3000`).
Without Earth Engine secrets the demo fields still work; live field analysis is switched off.

Legacy Streamlit UI: `pip install -r requirements.txt && streamlit run app.py` (port 8501).

### Lint & tests

```bash
pip install -r requirements-dev.txt
ruff check fieldshift ui views api scripts tests app.py
pytest                          # engines, presenters and API (FastAPI TestClient)
cd web && npm run typecheck     # TypeScript
```

### Data layer CLI (Phase 2)

```bash
python -m fieldshift.data.extract --lat 42.0 --lon -93.6 --size-ha 60
```

### Verify Earth Engine datasets (§4)

```bash
python tools/verify_ee.py
```

## Deploy — Streamlit Community Cloud (legacy UI)

1. Push this repo to GitHub.
2. https://share.streamlit.io → **New app** · main file `app.py`.
3. **Advanced settings → Secrets:** paste from `.streamlit/secrets.toml.example` (or
   `secrets/cloud_secrets.toml` from `print_cloud_secrets.py`). Never commit real keys.
4. Deploy. Without secrets → demo/mock mode.

## Limitations & cut list

Cut order if late (never SI model or evidence tagging): (a) Punjab demo, (b) live drawn-field analysis,
(c) timelapse, (d) docker-compose polish, (e) How-it-works depth.

## AI use

See [`AI_USAGE.md`](./AI_USAGE.md).
