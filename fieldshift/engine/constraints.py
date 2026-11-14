"""Farm constraint checks — water/irrigation crop filters (machinery/buyers removed)."""

from __future__ import annotations

from typing import Any

from fieldshift.engine.crops import crop_by_id
from fieldshift.engine.inputs_config import NEEDS_IRRIGATION_CROP_IDS
from fieldshift.models import FarmConstraints, WaterAccess


def sequence_has_legume(sequence: list[str]) -> bool:
    return any(bool(crop_by_id(c).get("nitrogen_fixing")) for c in sequence)


def evaluate_constraints(
    sequence: list[str],
    constraints: FarmConstraints | None = None,
    *,
    water_access: WaterAccess = "rainfed",
) -> dict[str, Any]:
    """Hard exclusions for irrigation-needy crops under rain-only water access.

    Soft penalties from labour/budget/machinery are removed.
    """
    _ = constraints  # kept for call-site compatibility
    hard: list[str] = []
    soft_notes: list[str] = []
    soft_penalty = 0.0

    if water_access == "rainfed":
        for cid in sequence:
            if cid in NEEDS_IRRIGATION_CROP_IDS:
                hard.append(
                    f"{crop_by_id(cid)['name']} usually needs irrigation — "
                    "not suitable under rain only"
                )

    return {
        "unsuitable": bool(hard),
        "reasons": hard,
        "soft_penalty": float(soft_penalty),
        "soft_notes": soft_notes,
    }
