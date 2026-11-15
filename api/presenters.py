"""Engine output → API DTOs, reusing the shared pure helpers in ui/plans.py and
ui/year_strip.py so the web app and the legacy Streamlit UI say the same things."""

from __future__ import annotations

import re
from typing import Any

from fieldshift.models import StrategyCard
from ui.glossary import friendly_source
from ui.plans import ROLE_EYEBROW, field_plan, group_field_cards, uk_plans
from ui.year_strip import calendar_model, rows_from_crops, rows_from_sequence

from api.schemas import CalendarRow, Evidence, Plan, PlanDetails

_MATERIAL_ICON = re.compile(r":material/\w+:\s*")


def strip_icon(label: str) -> str:
    """WATER_TILES etc. carry Streamlit icon codes; the web app draws its own."""
    return _MATERIAL_ICON.sub("", label).strip()


def calendar_rows(items: list[tuple[str, list[int]]]) -> list[CalendarRow]:
    return [CalendarRow.model_validate(r) for r in calendar_model(rows_from_crops(items))]


def _plan(content: dict[str, Any], calendar: list[CalendarRow], details: PlanDetails) -> Plan:
    return Plan(
        key=content["key"],
        role=content["role"],
        eyebrow=ROLE_EYEBROW.get(content["role"], "Option"),
        title=content["title"] or "—",
        meta=content.get("meta") or "",
        blurb=content.get("blurb") or "",
        features=content.get("features") or [],
        featured=bool(content.get("featured")),
        flags=content.get("flags") or [],
        flag_tone=content.get("flag_tone") or "note",
        calendar=calendar,
        details=details,
    )


def _field_details(card: StrategyCard) -> PlanDetails:
    return PlanDetails(
        why=card.why or None,
        benefits=list(card.benefits or []),
        evidence=[
            Evidence(
                text=e.text,
                source=friendly_source(e.source),
                data_through=getattr(e, "data_through", None),
            )
            for e in card.evidence or []
        ],
        gaps=list(card.data_gaps or []),
        risks=list(card.risks_for_local_review or []),
        confidence=(card.confidence or "medium").lower(),
    )


def field_plan_groups(
    cards: list[StrategyCard], *, climate_shifted: bool
) -> tuple[list[Plan], list[Plan], list[Plan]]:
    """(compare row, other options, not suitable) as plans."""
    baseline = next((c for c in cards if c.tier == "baseline"), None)
    baseline_scores = baseline.scores if baseline else None
    compare, others, bad = group_field_cards(cards)

    def build(card: StrategyCard, alt_index: int) -> Plan:
        content = field_plan(
            card,
            baseline_scores=baseline_scores,
            show_climate_delta=climate_shifted,
            alt_index=alt_index,
        )
        rows = calendar_model(rows_from_sequence(card.sequence))
        return _plan(
            content,
            [CalendarRow.model_validate(r) for r in rows],
            _field_details(card),
        )

    return (
        [build(c, i) for i, c in enumerate(compare)],
        [build(c, i + 1) for i, c in enumerate(others)],
        [build(c, 0) for c in bad],
    )


def uk_plan_list(results: list[dict[str, Any]]) -> list[Plan]:
    out: list[Plan] = []
    for content, r in zip(uk_plans(results), results, strict=True):
        items = content.pop("calendar_items")
        out.append(
            _plan(
                content,
                calendar_rows(items) if items else [],
                PlanDetails(
                    benefits=list(r.get("benefits") or []),
                    risks=list(r.get("risks") or []),
                    checks=list(r.get("checks") or []),
                    gaps=list(r.get("reasons") or []),
                ),
            )
        )
    return out
