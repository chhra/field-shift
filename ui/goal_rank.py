"""Goal ranking: the farmer puts the six goals in order; shared by Field and UK pages."""

from __future__ import annotations

import streamlit as st
from fieldshift.engine.inputs_config import (
    GOAL_HINTS,
    GOAL_KEYS,
    GOAL_LABELS,
    NO_GOALS_NOTE,
)

from ui.theme import SCORE_COLORS


def _move(key: str, goal: str, step: int) -> None:
    order = list(st.session_state[key])
    i = order.index(goal)
    j = i + step
    if 0 <= j < len(order):
        order[i], order[j] = order[j], order[i]
    st.session_state[key] = order


def _drop(key: str, goal: str) -> None:
    st.session_state[key] = [g for g in st.session_state[key] if g != goal]


def _add(key: str, goal: str) -> None:
    st.session_state[key] = [*st.session_state[key], goal]


def goal_ranking(scope: str, default_order: list[str]) -> list[str]:
    """Render the ranked goal list; return goal keys, most important first.

    No percentages — order alone is what the farmer sets. ``scope`` keeps widget
    keys apart per page/field (e.g. a field id or "ukm").
    """
    order_key = f"goal-order-{scope}"
    if order_key not in st.session_state:
        st.session_state[order_key] = list(default_order)
    order = [g for g in st.session_state[order_key] if g in GOAL_KEYS]

    for i, gk in enumerate(order):
        name = GOAL_LABELS[gk]
        with st.container(key=f"rank-row-{scope}-{gk}"):
            c_txt, c_up, c_down, c_drop = st.columns(
                [10, 1, 1, 1], gap="small", vertical_alignment="center"
            )
            c_txt.markdown(
                f'<div class="fs-rank"><span class="fs-rank-num">{i + 1}</span>'
                f'<i style="background:{SCORE_COLORS[gk]}"></i>'
                f'<span class="fs-rank-text"><span class="fs-rank-name">{name}</span>'
                f'<span class="fs-rank-q">{GOAL_HINTS[gk]}</span></span></div>',
                unsafe_allow_html=True,
            )
            c_up.button(
                ":material/arrow_upward:",
                key=f"goal-up-{scope}-{gk}",
                help=f"Move “{name}” up",
                disabled=i == 0,
                on_click=_move,
                args=(order_key, gk, -1),
            )
            c_down.button(
                ":material/arrow_downward:",
                key=f"goal-down-{scope}-{gk}",
                help=f"Move “{name}” down",
                disabled=i == len(order) - 1,
                on_click=_move,
                args=(order_key, gk, 1),
            )
            c_drop.button(
                ":material/close:",
                key=f"goal-drop-{scope}-{gk}",
                help=f"Remove “{name}”: it doesn't matter to me",
                on_click=_drop,
                args=(order_key, gk),
            )

    left_out = [g for g in GOAL_KEYS if g not in order]
    if left_out:
        st.markdown(
            '<p class="fs-rank-out">Doesn’t matter to me · tap to add back</p>',
            unsafe_allow_html=True,
        )
        out_cols = st.columns(3, gap="small")
        for j, gk in enumerate(left_out):
            out_cols[j % 3].button(
                GOAL_LABELS[gk],
                icon=":material/add:",
                key=f"goal-add-{scope}-{gk}",
                on_click=_add,
                args=(order_key, gk),
                use_container_width=True,
            )

    if not order:
        st.info(NO_GOALS_NOTE)
    return order
