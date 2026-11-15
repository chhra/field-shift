"""How it works: five inputs, six goals, sources, thresholds, glossary."""

from __future__ import annotations

import streamlit as st
from fieldshift.cache import read_json
from fieldshift.engine import thresholds as th
from fieldshift.engine.inputs_config import (
    GOAL_HINTS,
    GOAL_KEYS,
    GOAL_LABELS,
    GOAL_MEASURED,
    GOAL_PLAIN,
    IMPORTANCE_LABELS,
    LIMITED_IRRIGATION_ALLOWANCE,
    SOIL_AWC_MM_PER_M,
    SOIL_HINT,
    SOIL_INFILTRATION_MM_H,
    SOIL_LABELS,
    SOIL_TEXTURE_META,
    SOIL_WHY,
    WATER_HINT,
    WATER_LABELS,
    WATER_WHY,
)
from fieldshift.services import list_sources, using_mock_data
from ui.charts import pipeline_figure
from ui.components import hero, section
from ui.glossary import GLOSSARY
from ui.mock_banner import show_mock_banner
from ui.source_caption import source_caption

if using_mock_data():
    show_mock_banner()

hero(
    "How it works",
    "Field Shift turns NASA and partner Earth observations into a rotation advisory "
    "you can check against local knowledge.",
    sub="Five plain farm questions, six goals in everyday language, then the formulas.",
    mode_label="Methods & data",
    live=True,
    eyebrow="Mission documentation",
)

section("Pipeline")
st.plotly_chart(
    pipeline_figure(),
    use_container_width=True,
    config={"displayModeBar": False},
    key="how-pipeline-chart",
)
st.markdown(
    """
1. Reduce satellite & weather datasets to **field × month** values.  
2. Derive bare months, stress months, frost window, water balance, trends.  
3. Flag unusual seasons with an IsolationForest anomaly model (**SI**).  
4. Generate rotation candidates (current + cover + swaps).  
5. Score the **six farmer goals** with your importance weights.  
6. Explain each card with evidence, benefits, and local risks.  
"""
)

section(
    "The five inputs",
    "Ask what a farmer can answer. Satellites fill the rest. Categories map to numbers.",
)
st.markdown(
    """
1. **Your field** — confirm the map polygon satellites watch.  
2. **What you grow now** — confirm the crop in each satellite season; planting/harvest
   months stay tucked away unless satellites got them wrong.  
3. **Where your water comes from** — """
    + f"*{WATER_HINT}*  \n"
    + f"{WATER_WHY}  \n"
    + " · ".join(f"**{WATER_LABELS[k]}**" for k in WATER_LABELS)
    + """  
4. **Your soil type** — """
    + f"*{SOIL_HINT}*  \n"
    + f"{SOIL_WHY}  \n"
    + " · ".join(f"**{SOIL_LABELS[k]}**" for k in SOIL_LABELS)
    + """  
5. **What matters to you** — each goal Not important / Important / Very important.  
"""
)

section("The six goals")
for key in GOAL_KEYS:
    st.markdown(
        f"**{GOAL_LABELS[key]}** — *{GOAL_HINTS[key]}*  \n"
        f"**In plain words:** {GOAL_PLAIN[key]}  \n"
        f"**How we measure it:** {GOAL_MEASURED[key]}"
    )

section("Category → number mappings")
st.markdown("**Goal importance**")
st.dataframe(
    [{"Label": IMPORTANCE_LABELS[i], "Score": i} for i in (0, 1, 2)],
    hide_index=True,
    use_container_width=True,
)
st.caption("Weight = score ÷ sum of scores. All Not important → equal weights + note.")

st.markdown("**Soil available water (FAO-56 Table 19 midpoints)**")
st.dataframe(
    [
        {
            "Soil": SOIL_LABELS[k],
            "AWC (mm/m)": SOIL_AWC_MM_PER_M[k],
            "Infiltration (mm/h)": SOIL_INFILTRATION_MM_H[k],
        }
        for k in ("sandy", "loamy", "silty", "clay")
    ],
    hide_index=True,
    use_container_width=True,
)
st.caption(
    f"{SOIL_TEXTURE_META['source']} · "
    f"needs_expert_review={SOIL_TEXTURE_META['needs_expert_review']}"
)

st.markdown("**Limited irrigation allowance**")
st.write(
    f"Some irrigation adds **+{LIMITED_IRRIGATION_ALLOWANCE:.2f}** on the water score "
    "(documented project constant; needs expert review)."
)

section("Data sources")
sources = list_sources()
iowa = read_json("demo_iowa.json", from_mock=False) or {}
through = iowa.get("data_through") or {}
rows = []
for s in sources:
    rows.append(
        {
            "Purpose": s.purpose,
            "Dataset": s.name,
            "ID / access": s.id_or_access,
            "Resolution": s.resolution,
            "Data through (Iowa demo)": through.get("ndvi_s2", "see demo cache"),
            "Link": s.link,
        }
    )
st.dataframe(rows, use_container_width=True, hide_index=True)
source_caption("Demo field cache · Iowa", through.get("ndvi_s2"))

section("Decision thresholds")
st.dataframe(
    [
        {
            "Constant": "BEST_FIT_MIN_DELTA",
            "Value": th.BEST_FIT_MIN_DELTA,
            "Meaning": "Best fit must beat current by at least this",
        },
        {
            "Constant": "DELTA_NEUTRAL_THRESHOLD",
            "Value": th.DELTA_NEUTRAL_THRESHOLD,
            "Meaning": "Small overall change → “About the same as yours”",
        },
        {
            "Constant": "WORTH_CONSIDERING_OF_BEST",
            "Value": th.WORTH_CONSIDERING_OF_BEST,
            "Meaning": "Near-best band for Worth considering",
        },
        {
            "Constant": "NOT_SUITABLE_TOTAL_DELTA",
            "Value": th.NOT_SUITABLE_TOTAL_DELTA,
            "Meaning": "Below current by this → Not suitable",
        },
    ],
    use_container_width=True,
    hide_index=True,
)

section("Benefits (not rated) & local risks")
st.markdown(
    """
**Shown as benefits only** (do not change the ranking): pest-cycle breaks, infiltration
help from cover/deep roots, supplemental forage/cover income, and reduced water demand
vs your rotation.

**Risks listed on every card:** machinery and labour; seed availability; local prices
and buyers; pest and herbicide carryover.
"""
)

section("Glossary")
rows_g = "".join(
    f'<div class="fs-glossary-row">'
    f'<div class="fs-glossary-term">{term}</div>'
    f'<p class="fs-glossary-def">{definition}</p>'
    f"</div>"
    for term, definition in GLOSSARY.items()
)
st.markdown(f'<div class="fs-glossary">{rows_g}</div>', unsafe_allow_html=True)

section("Team & AI use")
st.write(
    "Built for NASA Space Apps Challenge 2026. See `AI_USAGE.md` for how AI assisted "
    "implementation. Human experts remain responsible for agronomic decisions."
)
