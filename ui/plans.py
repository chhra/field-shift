"""Plan content for rotation options — shared by the Streamlit UI and the web API.

Pure Python (no Streamlit). Scores stay inside the engines; a plan carries words,
a role and calendar items only.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from fieldshift.engine.card_copy import (
    farmer_comparison_sentence,
    rotation_title_line,
    top_criterion_diffs,
)
from fieldshift.models import StrategyCard
from team_model import app_adapter, model

from ui.year_strip import month_range, register_crop_meta, title_from_crops

ROLE_EYEBROW = {
    "current": "Your rotation",
    "recommended": "Recommended",
    "alternative": "Alternative",
    "other": "Also worth considering",
    "unsuitable": "Not a fit here",
}

_TIER_ORDER = ("baseline", "best_fit", "worth_considering", "not_suitable")


def group_field_cards(
    cards: list[StrategyCard],
) -> tuple[list[StrategyCard], list[StrategyCard], list[StrategyCard]]:
    """Split engine cards into (compare row, other options, not suitable).

    The compare row is the current rotation, the best fit, then alternatives
    until there are three boxes.
    """
    baseline = next((c for c in cards if c.tier == "baseline"), None)
    by_tier: dict[str, list[StrategyCard]] = {t: [] for t in _TIER_ORDER}
    for card in cards:
        by_tier.setdefault(card.tier or "worth_considering", []).append(card)

    compare: list[StrategyCard] = []
    if baseline:
        compare.append(baseline)
    compare.extend(by_tier.get("best_fit") or [])
    others = list(by_tier.get("worth_considering") or [])
    while len(compare) < 3 and others:
        compare.append(others.pop(0))
    return compare, others, list(by_tier.get("not_suitable") or [])


def field_plan(
    card: StrategyCard,
    *,
    baseline_scores: Any,
    show_climate_delta: bool,
    in_compare: bool,
) -> dict[str, Any]:
    """One Field-engine card as plan content (no calendar markup).

    ``in_compare``: the card sits in the compare row, where a near-best option
    is the Alternative; below the row it is "Also worth considering".
    """
    tier = card.tier or "worth_considering"
    if tier == "baseline":
        role = "current"
        blurb = "This is the rotation you said you grow today."
    elif tier == "not_suitable":
        role = "unsuitable"
        blurb = card.tier_reason or "Not a fit for this field under your priorities."
    else:
        role = "recommended" if tier == "best_fit" else (
            "alternative" if in_compare else "other"
        )
        diffs = top_criterion_diffs(card.scores, baseline_scores, n=3)
        blurb = farmer_comparison_sentence(
            diffs, overall_delta=card.delta_vs_current.get("total")
        )

    if show_climate_delta and tier not in ("baseline", "not_suitable"):
        blurb = f"{blurb} Climate scenario applied."

    flags: list[str] = []
    flag_tone = "note"
    if card.unsuitable_reasons:
        flags = list(card.unsuitable_reasons)
        flag_tone = "bad"
    elif card.soft_notes:
        flags = list(card.soft_notes)

    title = rotation_title_line(card.sequence)
    return {
        "key": card.id,
        "role": role,
        "title": title,
        "meta": card.name if card.name != title else "",
        "blurb": blurb,
        "features": list(card.benefits or [])[:5],
        "featured": tier == "best_fit",
        "flags": flags,
        "flag_tone": flag_tone,
    }


# --- UK model -----------------------------------------------------------------

_UK_FAMILY = {
    "cereal": "poaceae",
    "legume": "fabaceae",
    "brassica": "brassicaceae",
}
_MODEL_TO_APP = {v: k for k, v in app_adapter.APP_CROP_TO_MODEL.items()}


@lru_cache(maxsize=1)
def _uk_crops() -> dict[str, Any]:
    return model.load_crops()


def _uk_crop_id(name: str, *, cover: bool = False) -> str:
    """Map a UK model crop name to a calendar id (prefer Field Shift ids)."""
    display = name.replace(" (cover)", "").replace("(cover)", "").strip()
    row = _uk_crops().get(name) or {}
    is_cover = cover or str(row.get("role") or "") == "cover"
    if name in _MODEL_TO_APP:
        cid = _MODEL_TO_APP[name]
    else:
        cid = (
            name.lower()
            .replace("(", "")
            .replace(")", "")
            .replace(" ", "_")
            .strip("_")
        )
        if is_cover and not cid.endswith("_cover"):
            cid = f"{cid}_cover"
    register_crop_meta(
        cid,
        name=display,
        family=_UK_FAMILY.get(str(row.get("family") or "")) or None,
        cover=is_cover,
    )
    return cid


def uk_calendar_items(
    rotation: list[tuple[str, str | None]],
) -> list[tuple[str, list[int]]]:
    """(crop_id, months) list for year_strip, matching Field page calendars."""
    crops = _uk_crops()
    items: list[tuple[str, list[int]]] = []
    for main, cover in rotation:
        c = crops[main]
        if model.is_perennial(c):
            months = list(range(1, 13))
        else:
            months = month_range(int(c["sow_month"]), int(c["harvest_month"]))
        items.append((_uk_crop_id(main), months))
        if cover:
            items.append(
                (
                    _uk_crop_id(cover, cover=True),
                    list(model.cover_window(cover, crops)),
                )
            )
    return items


def uk_plans(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """UK-model results as plan content; ``calendar_items`` feed the year strip."""
    plans: list[dict[str, Any]] = []
    for i, r in enumerate(results):
        if i == 0:
            role, blurb = "current", "Your starting rotation for this field."
        elif i == 1:
            role, blurb = "recommended", "Best match for the priorities you set above."
        else:
            role, blurb = "alternative", "A different path that still fits your priorities."

        steps = list(r.get("crops") or [])
        cal_items = uk_calendar_items(steps) if steps else []
        years = r.get("years") or 0
        plans.append(
            {
                "key": f"ukm-{i}",
                "role": role,
                "title": (
                    title_from_crops(cal_items)
                    if cal_items
                    else (r.get("rotation") or r.get("name") or "—")
                ),
                "meta": f"{years} {'year' if years == 1 else 'years'}",
                "blurb": blurb,
                "features": list(r.get("benefits") or [])[:5],
                "featured": role == "recommended",
                "flags": [],
                "flag_tone": "note",
                "calendar_items": cal_items,
            }
        )
    return plans


def uk_recommendation_sentence(results: list[dict[str, Any]]) -> str | None:
    """Banner line for the UK options, or None when there is no alternative."""
    if len(results) < 2:
        return None
    best = results[1]
    years = best["years"]
    return (
        f"{best['rotation']} ({years} {'year' if years == 1 else 'years'}) is the "
        "recommended option for your priorities, ahead of your current rotation."
    )
