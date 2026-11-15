"""FastAPI app. Run: PYTHONPATH=. uvicorn api.main:app --reload --port 8000"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import field, meta, uk

app = FastAPI(
    title="Field Shift API",
    version="0.1.0",
    description="Crop-rotation options from NASA Earth observations. "
    "Wraps the fieldshift engine and the UK rotation model.",
)

_origins = [
    o.strip()
    for o in os.environ.get("FIELD_SHIFT_WEB_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    # Vercel production + preview deployments
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(meta.router)
app.include_router(field.router)
app.include_router(uk.router)
