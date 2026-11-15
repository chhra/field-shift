"""Strategy options as subscription-style comparison boxes — scores stay hidden."""

from __future__ import annotations

from typing import Any

import streamlit as st
from fieldshift.engine.card_copy import SCORE_KEYS
from fieldshift.models import StrategyCard

from ui.option_plans import render_comparison_plans
from ui.plans import field_plan, group_field_cards, uk_plans
from ui.source_caption import source_caption
from ui.year_strip import (
    rows_from_crops,
    rows_from_sequence,
    year_strip_html,
)


def render_strategy_cards(
    cards: list[StrategyCard],
    *,
    show_climate_delta: bool = False,
) -> None:
    """Render Field-page options as plan boxes. Engine scores are not shown."""
    if not cards:
        st.info("No strategies available.")
        return

    baseline = next((c for c in cards if c.tier == "baseline"), None)
    baseline_scores = baseline.scores if baseline else None
    compare, others, bad = group_field_cards(cards)

    if compare:
        st.markdown(
            '<p class="fs-options-label">Compare your options</p>',
            unsafe_allow_html=True,
        )
        render_comparison_plans(
            [
                _card_to_plan(
                    c,
                    baseline_scores=baseline_scores,
                    show_climate_delta=show_climate_delta,
                    in_compare=True,
                )
                for c in compare
            ],
            details_fn=_field_details,
            allow_expanders=True,
        )

    if others:
        st.markdown(
            '<p class="fs-options-label">Other options worth considering</p>',
            unsafe_allow_html=True,
        )
        render_comparison_plans(
            [
                _card_to_plan(
                    c,
                    baseline_scores=baseline_scores,
                    show_climate_delta=show_climate_delta,
                    in_compare=False,
                )
                for c in others
            ],
            details_fn=_field_details,
            allow_expanders=True,
        )

    if bad:
        with st.expander(
            f"Show options we don't recommend ({len(bad)})",
            expanded=False,
        ):
            st.caption(
                "These fail a hard farm constraint or look clearly weaker than "
                "your current rotation for your priorities."
            )
            render_comparison_plans(
                [
                    _card_to_plan(
                        c,
                        baseline_scores=baseline_scores,
                        show_climate_delta=show_climate_delta,
                        in_compare=False,
                    )
                    for c in bad
                ],
                details_fn=None,
                allow_expanders=False,
            )


def _card_to_plan(
    card: StrategyCard,
    *,
    baseline_scores: Any,
    show_climate_delta: bool,
    in_compare: bool,
) -> dict[str, Any]:
    plan = field_plan(
        card,
        baseline_scores=baseline_scores,
        show_climate_delta=show_climate_delta,
        in_compare=in_compare,
    )
    plan["calendar_html"] = year_strip_html(rows_from_sequence(card.sequence), compact=True)
    plan["_card"] = card
    return plan


def _field_details(plan: dict[str, Any]) -> None:
    card: StrategyCard = plan["_card"]
    st.markdown("**Why this option**")
    st.write(card.why)
    if card.benefits:
        st.markdown("**Benefits**")
        for b in card.benefits:
            st.write(f"• {b}")
    if card.evidence:
        st.markdown("**Evidence**")
        for item in card.evidence:
            st.markdown(f"• {item.text}")
            source_caption(item.source, getattr(item, "data_through", None))
    if card.data_gaps:
        st.markdown("**Data gaps**")
        for g in card.data_gaps:
            st.write(f"• {g}")
    if card.risks_for_local_review:
        st.markdown("**Risks to check locally**")
        for r in card.risks_for_local_review:
            st.write(f"• {r}")
    conf = (card.confidence or "medium").lower()
    st.caption(f"Confidence in this comparison: {conf}")
    source_caption("Field Shift engine")


def render_uk_option_plans(results: list[dict[str, Any]]) -> None:
    """UK-model results as Field-style plan boxes with farming-year calendars."""
    if not results:
        st.info("No options to compare yet.")
        return

    plans = uk_plans(results)
    for plan, r in zip(plans, results, strict=True):
        items = plan.pop("calendar_items")
        plan["calendar_html"] = (
            year_strip_html(rows_from_crops(items), compact=True) if items else ""
        )
        plan["_uk"] = r
    render_comparison_plans(plans, details_fn=_uk_details, allow_expanders=True)


def _uk_details(plan: dict[str, Any]) -> None:
    r = plan["_uk"]
    if r.get("benefits"):
        st.markdown("**Benefits**")
        for b in r["benefits"]:
            st.write(f"• {b}")
    if r.get("risks"):
        st.markdown("**Risks**")
        for b in r["risks"]:
            st.write(f"• {b}")
    if r.get("checks"):
        st.markdown("**Check locally**")
        for b in r["checks"]:
            st.write(f"• {b}")
    if r.get("reasons"):
        st.markdown("**Information gaps**")
        for b in r["reasons"]:
            st.write(f"• {b}")


__all__ = [
    "SCORE_KEYS",
    "render_strategy_cards",
    "render_uk_option_plans",
]
