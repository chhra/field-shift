"""Farming-year calendar strip — crop seasons and bare-soil months, Jan–Dec."""

from __future__ import annotations

import html
import re
from functools import lru_cache
from typing import Any

from fieldshift.engine.crops import load_crops

from ui.theme import BARE_SOIL_FILL as BARE_FILL
from ui.theme import COVER_LEGEND_FILL
from ui.theme import CROP_FAMILY_FILLS as FAMILY_FILL
from ui.theme import CROP_FAMILY_FILLS_ALT as FAMILY_FILL_ALT
from ui.theme import CROP_OTHER_FILL as OTHER_FILL

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# One month cell: (crop_id, is_cover) or None for bare soil.
Cell = tuple[str, bool] | None
Row = list[Cell]

_MONTH_RE = re.compile(r"\b(" + "|".join(MONTH_ABBR) + r")\b")


@lru_cache(maxsize=1)
def _crops() -> dict[str, dict[str, Any]]:
    return {c["id"]: c for c in load_crops()}


# Extra labels/families for crops that only exist in the UK model (or aliases).
_META: dict[str, dict[str, Any]] = {}


def register_crop_meta(
    crop_id: str,
    *,
    name: str | None = None,
    family: str | None = None,
    cover: bool = False,
) -> None:
    """Tell the calendar how to label/colour a crop id that is not in crops.json."""
    row = dict(_META.get(crop_id) or {})
    if name:
        row["name"] = name
    if family:
        row["family"] = family
    if cover:
        row["type"] = "cover"
    _META[crop_id] = row


def short_name(crop_id: str) -> str:
    meta = _META.get(crop_id) or {}
    # Prefer an explicit register_crop_meta name (e.g. UK "Winter barley").
    name = str(
        meta.get("name")
        or _crops().get(crop_id, {}).get("name")
        or crop_id.replace("_", " ")
    )
    return name.split(" / ")[0].split(" (")[0]


def is_cover_crop(crop_id: str) -> bool:
    if (_META.get(crop_id) or {}).get("type") == "cover":
        return True
    if _crops().get(crop_id, {}).get("type") == "cover":
        return True
    return "cover" in crop_id.lower()


def months_from_text(text: str) -> list[int]:
    """'kharif Jun–Oct' → [6..10]; wraps the year ('Oct–Apr' → 10..12, 1..4)."""
    found = [MONTH_ABBR.index(m) + 1 for m in _MONTH_RE.findall(text or "")]
    if not found:
        return []
    return month_range(found[0], found[-1])


def month_range(start: int, end: int) -> list[int]:
    """Inclusive 1–12 month range that may wrap past December."""
    span = (end - start) % 12
    return [((start - 1 + k) % 12) + 1 for k in range(span + 1)]


def rows_from_sequence(sequence: list[Any], *, max_rows: int = 6) -> list[Row]:
    """Rows from a strategy sequence (CropInSequence items)."""
    items: list[tuple[str, list[int]]] = []
    for item in sequence:
        months = months_from_text(item.months)
        if not months and item.plant_month and item.harvest_month:
            months = month_range(item.plant_month, item.harvest_month)
        items.append((item.crop_id, months))
    return rows_from_crops(items, max_rows=max_rows)


def rows_from_crops(
    items: list[tuple[str, list[int]]], *, max_rows: int = 6
) -> list[Row]:
    """Lay crops out year by year. A cash crop that mostly overlaps the current
    year starts the next year; cover crops fill bare months every year."""
    rows: list[Row] = [[None] * 12]
    covers: list[tuple[str, list[int]]] = []
    for crop, months in items:
        if not months:
            continue
        if is_cover_crop(crop):
            covers.append((crop, months))
            continue
        row = rows[-1]
        taken = sum(1 for m in months if row[m - 1] is not None)
        if taken * 2 > len(months) and len(rows) < max_rows:
            row = [None] * 12
            rows.append(row)
        for m in months:
            if row[m - 1] is None:
                row[m - 1] = (crop, False)
    for crop, months in covers:
        for row in rows:
            for m in months:
                if row[m - 1] is None:
                    row[m - 1] = (crop, True)
    return rows


def _runs(row: Row) -> list[tuple[int, int, Cell]]:
    """Contiguous (start_index, length, cell) runs within one calendar year."""
    out: list[tuple[int, int, Cell]] = []
    i = 0
    while i < 12:
        j = i
        while j + 1 < 12 and row[j + 1] == row[i]:
            j += 1
        out.append((i, j - i + 1, row[i]))
        i = j + 1
    return out


def _stripes(base: str) -> str:
    return (
        f"repeating-linear-gradient(135deg, {base} 0 6px, "
        f"rgba(255,255,255,.55) 6px 10px), {base}"
    )


def fill_tone(cell: Cell) -> str:
    """Colour key for a cell: 'bare', 'other', a crop family, or '<family>-alt'."""
    if cell is None:
        return "bare"
    fam = str(
        _crops().get(cell[0], {}).get("family")
        or (_META.get(cell[0]) or {}).get("family")
        or ""
    )
    if fam not in FAMILY_FILL:
        return "other"
    same_family = [cid for cid, c in _crops().items() if c.get("family") == fam]
    # Alternate shades so two neighbouring cereals (e.g. rice → wheat) stay distinct.
    alt = cell[0] in same_family and same_family.index(cell[0]) % 2 == 1
    return f"{fam}-alt" if alt else fam


def _fill(cell: Cell) -> str:
    tone = fill_tone(cell)
    if tone == "bare":
        return BARE_FILL
    if tone == "other":
        base = OTHER_FILL
    elif tone.endswith("-alt"):
        base = FAMILY_FILL_ALT[tone.removesuffix("-alt")]
    else:
        base = FAMILY_FILL[tone]
    return _stripes(base) if cell and cell[1] else base


def title_from_crops(items: list[tuple[str, list[int]]]) -> str:
    """Field-style title: 'Winter wheat (Oct–Aug) → Spring peas (Mar–Jul)'."""
    parts: list[str] = []
    for crop_id, months in items:
        if not months:
            parts.append(short_name(crop_id))
            continue
        a, b = MONTH_ABBR[months[0] - 1], MONTH_ABBR[months[-1] - 1]
        label = short_name(crop_id)
        if is_cover_crop(crop_id) and "cover" not in label.lower():
            label = f"{label} cover"
        parts.append(f"{label} ({a}–{b})")
    return " → ".join(parts)


def _run_text(start: int, n: int, cell: Cell) -> str:
    span = MONTH_ABBR[start] if n == 1 else f"{MONTH_ABBR[start]}–{MONTH_ABBR[start + n - 1]}"
    what = "bare soil" if cell is None else short_name(cell[0]) + (" cover" if cell[1] else "")
    return f"{what} {span}"


def _row_summary(row: Row) -> str:
    return ", ".join(_run_text(*run) for run in _runs(row))


def calendar_model(rows: list[Row]) -> list[dict[str, Any]]:
    """The same calendar as ``year_strip_html`` as data: one entry per year row.

    Segments use 1-based start months; ``tone`` is a colour key from ``fill_tone``.
    """
    labelled = len(rows) > 1
    out: list[dict[str, Any]] = []
    for y, row in enumerate(rows):
        summary = _row_summary(row)
        out.append(
            {
                "label": f"Year {y + 1}" if labelled else None,
                "summary": f"Year {y + 1}: {summary}" if labelled else summary,
                "segments": [
                    {
                        "start": start + 1,
                        "span": n,
                        "crop_id": cell[0] if cell else None,
                        "name": short_name(cell[0]) if cell else "Bare soil",
                        "cover": bool(cell and cell[1]),
                        "tone": fill_tone(cell),
                        "title": _run_text(start, n, cell),
                    }
                    for start, n, cell in _runs(row)
                ],
            }
        )
    return out


def year_strip_html(rows: list[Row], *, compact: bool = False, legend: bool = False) -> str:
    labelled = len(rows) > 1
    cls = "fs-year" + (" fs-year--compact" if compact else "") + (
        " fs-year--labelled" if labelled else ""
    )
    head = "".join(f"<span>{m[0] if compact else m}</span>" for m in MONTH_ABBR)
    lab_slot = '<span class="fs-year-lab"></span>' if labelled else ""
    out = [f'<div class="{cls}">', f'<div class="fs-year-row fs-year-head">{lab_slot}'
           f'<div class="fs-year-track">{head}</div></div>']
    summaries = []
    for y, row in enumerate(rows):
        summary = _row_summary(row)
        summaries.append(f"Year {y + 1}: {summary}" if labelled else summary)
        segs = []
        for start, n, cell in _runs(row):
            if cell is None:
                text = "bare" if n >= 2 and not compact else ""
            else:
                text = short_name(cell[0]) if n > 1 else ""
            segs.append(
                f'<div class="fs-year-seg{" is-bare" if cell is None else ""}" '
                f'style="grid-column:{start + 1} / span {n};background:{_fill(cell)}" '
                f'title="{html.escape(_run_text(start, n, cell))}">'
                f"<span>{html.escape(text)}</span></div>"
            )
        lab = f'<span class="fs-year-lab">Year {y + 1}</span>' if labelled else ""
        out.append(
            f'<div class="fs-year-row" role="img" aria-label="{html.escape(summaries[-1])}">'
            f'{lab}<div class="fs-year-track">{"".join(segs)}</div></div>'
        )
    if legend:
        out.append(
            '<div class="fs-year-legend">'
            f'<span><i style="background:{FAMILY_FILL["poaceae"]}"></i>Cereals</span>'
            f'<span><i style="background:{FAMILY_FILL["fabaceae"]}"></i>Legumes</span>'
            f'<span><i style="background:{FAMILY_FILL["brassicaceae"]}"></i>Brassicas</span>'
            f'<span><i style="background:{_stripes(COVER_LEGEND_FILL)}"></i>Cover crop</span>'
            f'<span><i style="background:{BARE_FILL}"></i>Bare soil</span>'
            "</div>"
        )
    out.append("</div>")
    return "".join(out)
