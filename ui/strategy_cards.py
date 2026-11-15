"""Strategy options as subscription-style comparison boxes — scores stay hidden."""

from __future__ import annotations

from typing import Any

import streamlit as st
from fieldshift.engine.card_copy import (
    SCORE_KEYS,
    farmer_comparison_sentence,
    rotation_title_line,
    top_criterion_diffs,
)
from fieldshift.models import StrategyCard

from ui.option_plans import render_comparison_plans
from ui.source_caption import source_caption
from ui.year_strip import rows_from_sequence, year_strip_html

_TIER_ORDER = ("baseline", "best_fit", "worth_considering", "not_suitable")


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

    by_tier: dict[str, list[StrategyCard]] = {t: [] for t in _TIER_ORDER}
    for card in cards:
        tier = card.tier or "worth_considering"
        by_tier.setdefault(tier, []).append(card)

    compare: list[StrategyCard] = []
    if baseline:
        compare.append(baseline)
    compare.extend(by_tier.get("best_fit") or [])
    others = list(by_tier.get("worth_considering") or [])
    while len(compare) < 3 and others:
        compare.append(others.pop(0))

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
                    alt_index=i,
                )
                for i, c in enumerate(compare)
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
                    alt_index=i + 1,
                )
                for i, c in enumerate(others)
            ],
            details_fn=_field_details,
            allow_expanders=True,
        )

    bad = by_tier.get("not_suitable") or []
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
                        alt_index=0,
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
    alt_index: int,
) -> dict[str, Any]:
    tier = card.tier or "worth_considering"
    if tier == "baseline":
        role = "current"
        blurb = "This is the rotation you said you grow today."
    elif tier == "best_fit":
        role = "recommended"
        diffs = top_criterion_diffs(card.scores, baseline_scores, n=3)
        blurb = farmer_comparison_sentence(
            diffs, overall_delta=card.delta_vs_current.get("total")
        )
    elif tier == "not_suitable":
        role = "unsuitable"
        blurb = card.tier_reason or "Not a fit for this field under your priorities."
    else:
        role = "alternative" if alt_index <= 1 else "other"
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

    return {
        "key": card.id,
        "role": role,
        "title": rotation_title_line(card.sequence),
        "meta": card.name if card.name != rotation_title_line(card.sequence) else "",
        "blurb": blurb,
        "features": list(card.benefits or [])[:5],
        "calendar_html": year_strip_html(
            rows_from_sequence(card.sequence), compact=True
        ),
        "featured": tier == "best_fit",
        "flags": flags,
        "flag_tone": flag_tone,
        "_card": card,
    }


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
    """UK-model results as the same plan boxes (current / recommended / alternative)."""
    if not results:
        st.info("No options to compare yet.")
        return

    plans: list[dict[str, Any]] = []
    for i, r in enumerate(results):
        if i == 0:
            role = "current"
            blurb = "Your starting rotation for this field."
            featured = False
        elif i == 1:
            role = "recommended"
            blurb = "Best match for the priorities you set above."
            featured = True
        else:
            role = "alternative"
            blurb = "A different path that still fits your priorities."
            featured = False
        years = r.get("years") or 0
        year_word = "year" if years == 1 else "years"
        plans.append(
            {
                "key": f"ukm-{i}",
                "role": role,
                "title": r.get("rotation") or r.get("name") or "—",
                "meta": f"{years} {year_word}",
                "blurb": blurb,
                "features": list(r.get("benefits") or [])[:5],
                "featured": featured,
                "_uk": r,
            }
        )

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
