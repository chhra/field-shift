"""Subscription-style comparison boxes for rotation options — no scores shown."""

from __future__ import annotations

import html
from collections.abc import Callable
from typing import Any

import streamlit as st

_ROLE_EYEBROW = {
    "current": "Your rotation",
    "recommended": "Recommended",
    "alternative": "Alternative",
    "other": "Also worth considering",
    "unsuitable": "Not a fit here",
}


def render_comparison_plans(
    plans: list[dict[str, Any]],
    *,
    details_fn: Callable[[dict[str, Any]], None] | None = None,
    allow_expanders: bool = True,
) -> None:
    """Render plan boxes side by side. Scoring stays in the engine; UI shows none.

    Each plan dict:
      key, role, title, meta?, blurb?, features? (list[str]), calendar_html?,
      featured? (bool), flags? (list[str]), flag_tone? ("bad"|"note")
    """
    if not plans:
        st.info("No options to compare yet.")
        return

    n = len(plans)
    cols = st.columns(n, gap="medium")
    for col, plan in zip(cols, plans, strict=True):
        with col:
            _render_one(plan, details_fn=details_fn, allow_expanders=allow_expanders)


def _render_one(
    plan: dict[str, Any],
    *,
    details_fn: Callable[[dict[str, Any]], None] | None,
    allow_expanders: bool,
) -> None:
    role = plan.get("role") or "other"
    eyebrow = plan.get("eyebrow") or _ROLE_EYEBROW.get(role, "Option")
    featured = bool(plan.get("featured") or role == "recommended")
    title = plan.get("title") or "—"
    meta = plan.get("meta") or ""
    blurb = plan.get("blurb") or ""
    features = list(plan.get("features") or [])[:5]
    calendar = plan.get("calendar_html") or ""
    flags = list(plan.get("flags") or [])
    flag_tone = plan.get("flag_tone") or "note"

    box_cls = "fs-plan fs-plan--featured" if featured else "fs-plan"
    if role == "unsuitable":
        box_cls += " fs-plan--muted"

    feat_html = ""
    if features:
        items = "".join(
            f'<li><span class="fs-plan-tick" aria-hidden="true">✓</span>'
            f"{html.escape(f)}</li>"
            for f in features
        )
        feat_html = f'<ul class="fs-plan-features">{items}</ul>'
    else:
        feat_html = '<p class="fs-plan-empty">No standout benefits listed.</p>'

    flag_html = ""
    if flags:
        cls = "fs-plan-flags bad" if flag_tone == "bad" else "fs-plan-flags"
        flag_html = (
            f'<div class="{cls}">'
            + "".join(f"<div>{html.escape(f)}</div>" for f in flags)
            + "</div>"
        )

    badge = (
        '<span class="fs-plan-badge">Best for your priorities</span>'
        if featured
        else ""
    )

    st.markdown(
        f"""
<div class="{box_cls}">
  <p class="fs-plan-eyebrow">{html.escape(eyebrow)}</p>
  {badge}
  <p class="fs-plan-title">{html.escape(title)}</p>
  {f'<p class="fs-plan-meta">{html.escape(meta)}</p>' if meta else ""}
  {calendar}
  {f'<p class="fs-plan-blurb">{html.escape(blurb)}</p>' if blurb else ""}
  {flag_html}
  <p class="fs-plan-feat-label">What stands out</p>
  {feat_html}
</div>
        """,
        unsafe_allow_html=True,
    )

    if allow_expanders and details_fn is not None:
        with st.expander("Details and local checks", expanded=False):
            details_fn(plan)
    elif not allow_expanders and blurb:
        st.caption(blurb)
