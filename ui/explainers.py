"""Plain-language orientation labels for scores, metrics, and charts."""

from __future__ import annotations

from fieldshift.engine.inputs_config import GOAL_HINTS, GOAL_LABELS, GOAL_MEASURED

# Criterion → what the score measures (farmer-facing) — exactly six goals
CRITERION_HELP: dict[str, dict[str, str]] = {
    key: {
        "label": GOAL_LABELS[key],
        "short": GOAL_HINTS[key],
        "detail": GOAL_MEASURED[key],
    }
    for key in GOAL_LABELS
}
CRITERION_HELP["total"] = {
    "label": "Overall score",
    "short": "Weighted average of the six goals",
    "detail": (
        "0–1 scale. Combines the six scores using what you said matters most. "
        "A higher total means a better match for your goals."
    ),
}

FACT_HELP: dict[str, str] = {
    "bare": (
        "Months when satellites usually see little green cover. Bare soil is "
        "more exposed to erosion and is a window for cover crops."
    ),
    "frost": (
        "Days between last spring frost and first autumn frost. Longer windows "
        "support more crop choices and cover-crop windows."
    ),
    "rain": (
        "Typical yearly rainfall over the field (mm). Compare to crop water "
        "needs; rainfed farms feel this number most."
    ),
    "grace": (
        "Regional groundwater / water-storage trend from GRACE satellites. "
        "A falling trend means irrigation may be less sustainable over time."
    ),
}


def chart_how_to_read() -> str:
    return (
        "**Plant greenness** (line) rises when crops or cover are growing. "
        "**Rain** (bars) shows typical monthly rainfall. "
        "**Water balance** (dashed) is rain minus evaporative demand — negative "
        "means the field is drying. Tan months are usually bare; light red marks "
        "growing-season stress."
    )
