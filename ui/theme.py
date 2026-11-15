"""Field Shift design system — flat Streamlit-demo style tokens + CSS."""

from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Colour tokens (docs/DESIGN.md)
# ---------------------------------------------------------------------------
BACKGROUND = "#FFFFFF"
SURFACE = "#FFFFFF"
SIDEBAR = "#F0F2F6"  # Streamlit-demo soft grey for tracks / subtle fills
TEXT = "#262730"
MUTED = "#555555"  # WCAG AA on BACKGROUND/SURFACE
PRIMARY = "#3F7D3A"
WARNING = "#B26A00"
DANGER = "#B23A3A"
INFO = "#3A7CA5"
CARD_BORDER = "#E6E6E6"
HAIRLINE = CARD_BORDER
FOCUS = "#2F5E2C"
CARD_RADIUS = "6px"

# Spacing scale (px)
SPACE = (8, 16, 24, 32, 48)

# Okabe–Ito colour-blind-safe palette (fixed roles)
OKABE = {
    "black": "#000000",
    "orange": "#E69F00",
    "sky": "#56B4E9",
    "bluish_green": "#009E73",
    "yellow": "#F0E442",
    "blue": "#0072B2",
    "vermillion": "#D55E00",
    "purple": "#CC79A7",
}

# Chart / criterion colours — one fixed colour per variable app-wide
CHART_COLORS = {
    "greenness": OKABE["bluish_green"],
    "rain": OKABE["sky"],
    "water_balance": OKABE["blue"],
    "bare": OKABE["orange"],
    "stress": OKABE["vermillion"],
}
SCORE_COLORS = {
    "water": OKABE["sky"],
    "forage": OKABE["orange"],
    "nitrogen": OKABE["bluish_green"],
    "erosion": OKABE["vermillion"],
    "organic_matter": OKABE["purple"],
    "market": OKABE["blue"],
    "total": PRIMARY,
}

# Farming-year calendar fills by crop family; dark TEXT stays ≥4.5:1 on each.
CROP_FAMILY_FILLS = {
    "poaceae": "#E3B23C",
    "fabaceae": "#7DB86A",
    "brassicaceae": "#C3A6E0",
}
CROP_FAMILY_FILLS_ALT = {
    "poaceae": "#F2D58A",
    "fabaceae": "#AFD6A0",
    "brassicaceae": "#DDCBEF",
}
CROP_OTHER_FILL = "#9CC3D3"
BARE_SOIL_FILL = "#F3EBDD"
COVER_LEGEND_FILL = "#B5B5B5"

# Back-compat aliases used across the codebase
PAPER = SURFACE
PANEL = SIDEBAR
INK = TEXT
NASA_BLUE = PRIMARY
NASA_BLUE_MID = FOCUS
NASA_RED = DANGER
EARTH = PRIMARY
SKY = INFO
SOIL = WARNING
ALERT = DANGER
WHEAT = WARNING
LEAF = PRIMARY
WHEAT_BG = SIDEBAR

# Text/background pairs that must meet WCAG 2.2 AA (used by tests)
CONTRAST_PAIRS: list[tuple[str, str, str, float]] = [
    ("text_on_background", TEXT, BACKGROUND, 4.5),
    ("text_on_surface", TEXT, SURFACE, 4.5),
    ("muted_on_background", MUTED, BACKGROUND, 4.5),
    ("muted_on_surface", MUTED, SURFACE, 4.5),
    ("primary_on_background", PRIMARY, BACKGROUND, 3.0),
    ("primary_on_surface", PRIMARY, SURFACE, 3.0),
    ("warning_on_background", WARNING, BACKGROUND, 3.0),
    ("danger_on_background", DANGER, BACKGROUND, 3.0),
    ("info_on_background", INFO, BACKGROUND, 3.0),
    ("text_on_sidebar", TEXT, SIDEBAR, 4.5),
]

_THEME_VERSION = "visual-questions-v1"


def inject_nav_active(active_path: str) -> None:
    """Green underline on the current top tab (by Streamlit page href)."""
    # Home uses empty href; other pages use their url_path.
    href = (active_path or "").strip()
    scope = 'div[data-testid="stHorizontalBlock"]:has(.fs-brand)'
    selector = (
        f'{scope} [data-testid="stPageLink"] a[href=""]'
        if href == ""
        else f'{scope} [data-testid="stPageLink"] a[href="{href}"]'
    )
    st.markdown(
        f"""
<style>
{selector},
{selector} * {{
  color: {TEXT} !important;
  font-weight: 600 !important;
}}
{selector} {{
  border-bottom: 2px solid {PRIMARY} !important;
  border-bottom-color: {PRIMARY} !important;
}}
</style>
        """,
        unsafe_allow_html=True,
    )


def inject_theme() -> None:
    """Inject global CSS on every run (Streamlit clears custom HTML on rerun)."""
    st.session_state["_fs_theme_ver"] = _THEME_VERSION
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stApp, .stMarkdown, button, input, label, textarea {{
  font-family: "Source Sans 3", "Helvetica Neue", Helvetica, Arial, sans-serif !important;
}}

#MainMenu {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent; }}
footer {{ visibility: hidden; }}
div[data-testid="stDecoration"] {{ display: none; }}
.stDeployButton, [data-testid="stToolbar"], [data-testid="stAppDeployButton"] {{
  display: none !important;
}}

/* No sidebar — gallery-demo layout */
section[data-testid="stSidebar"],
[data-testid="stSidebar"],
[data-testid="stSidebarContent"],
[data-testid="stSidebarCollapsedControl"],
button[kind="headerNoPadding"],
[data-testid="collapsedControl"] {{
  display: none !important;
  width: 0 !important;
  min-width: 0 !important;
  visibility: hidden !important;
}}
section[data-testid="stSidebar"] {{
  transform: translateX(-100%) !important;
}}

.stApp, [data-testid="stAppViewContainer"], [data-testid="stAppViewBlockContainer"] {{
  background: {BACKGROUND} !important;
}}
.block-container,
[data-testid="stMainBlockContainer"] {{
  max-width: 1100px !important;
  padding-top: 16px;
  padding-bottom: 48px;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}}

/* Strip all Streamlit bordered chrome — flat like Seattle weather demo */
div[data-testid="stVerticalBlockBorderWrapper"],
div[data-testid="stMainBlockContainer"],
section.main .block-container {{
  border: none !important;
  box-shadow: none !important;
  outline: none !important;
  background: transparent !important;
  border-radius: 0 !important;
}}
div[data-testid="stVerticalBlockBorderWrapper"] {{
  overflow: visible !important;
  height: auto !important;
  padding: 0 !important;
}}
div[data-testid="stVerticalBlockBorderWrapper"] > div {{
  height: auto !important;
}}

/* Top header — wordmark + tabs on one baseline */
.fs-brand {{
  margin: 0 !important;
  padding: 0 !important;
  font-size: 22px !important;
  font-weight: 700 !important;
  letter-spacing: -0.03em !important;
  color: {TEXT} !important;
  line-height: 40px !important;
  height: 40px !important;
  white-space: nowrap;
}}
.fs-topnav-rule {{
  height: 0;
  margin: 0 0 22px 0;
  border: none;
  border-bottom: 1px solid {CARD_BORDER};
}}
/* One header row: brand + tabs on the same vertical center */
div[data-testid="stHorizontalBlock"]:has(.fs-brand) {{
  align-items: center !important;
  gap: 4px !important;
  margin: 0 0 0 0 !important;
  min-height: 40px !important;
}}
div[data-testid="stHorizontalBlock"]:has(.fs-brand)
> div[data-testid="stColumn"] {{
  display: flex !important;
  flex-direction: column !important;
  justify-content: center !important;
  align-items: flex-start !important;
  min-height: 40px !important;
}}
div[data-testid="stHorizontalBlock"]:has(.fs-brand)
> div[data-testid="stColumn"] > div {{
  display: flex !important;
  flex-direction: column !important;
  justify-content: center !important;
  gap: 0 !important;
  width: 100%;
}}
div[data-testid="stHorizontalBlock"]:has(.fs-brand)
[data-testid="stVerticalBlock"] {{
  gap: 0 !important;
}}
div[data-testid="stHorizontalBlock"]:has(.fs-brand)
[data-testid="element-container"],
div[data-testid="stHorizontalBlock"]:has(.fs-brand)
[data-testid="stMarkdownContainer"],
div[data-testid="stHorizontalBlock"]:has(.fs-brand)
[data-testid="stPageLink"] {{
  margin: 0 !important;
  padding: 0 !important;
}}
div[data-testid="stHorizontalBlock"]:has(.fs-brand)
[data-testid="stPageLink"] {{
  width: auto !important;
  display: inline-flex !important;
  align-items: center !important;
  height: 40px !important;
}}
div[data-testid="stHorizontalBlock"]:has(.fs-brand)
[data-testid="stPageLink"] a,
div[data-testid="stHorizontalBlock"]:has(.fs-brand)
[data-testid="stPageLink-NavLink"] {{
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  width: auto !important;
  min-width: 0 !important;
  min-height: 40px !important;
  height: 40px !important;
  padding: 0 2px !important;
  margin: 0 !important;
  border: none !important;
  border-bottom: 2px solid transparent !important;
  border-radius: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  outline: none !important;
  color: {MUTED} !important;
  font-weight: 500 !important;
  font-size: 15px !important;
  letter-spacing: -0.01em !important;
  text-decoration: none !important;
  white-space: nowrap !important;
  line-height: 1 !important;
  box-sizing: border-box !important;
  transition: color 0.15s ease, border-color 0.15s ease !important;
}}
div[data-testid="stHorizontalBlock"]:has(.fs-brand)
[data-testid="stPageLink"] a:hover {{
  color: {TEXT} !important;
  background: transparent !important;
  border-bottom-color: {CARD_BORDER} !important;
}}
div[data-testid="stHorizontalBlock"]:has(.fs-brand)
[data-testid="stPageLink"] a *,
div[data-testid="stHorizontalBlock"]:has(.fs-brand)
[data-testid="stPageLink-NavLink"] * {{
  color: inherit !important;
  background: transparent !important;
}}
div[data-testid="stHorizontalBlock"]:has(.fs-brand)
[data-testid="stPageLink"] span[data-testid="stIconEmoji"],
div[data-testid="stHorizontalBlock"]:has(.fs-brand)
[data-testid="stPageLink"] [data-testid="stIconMaterial"] {{
  display: none !important;
}}

/* Typography scale */
h1, .fs-title {{
  font-size: 32px !important;
  font-weight: 600 !important;
  color: {TEXT} !important;
  letter-spacing: -0.02em;
  line-height: 1.2 !important;
  margin-bottom: 8px !important;
  text-wrap: balance;
}}
h2, .fs-section-title {{
  font-size: 28px !important;
  font-weight: 500 !important;
  color: {TEXT} !important;
  letter-spacing: -0.01em;
  line-height: 1.25 !important;
  text-wrap: balance;
}}
h3, h5 {{
  font-size: 18px !important;
  font-weight: 500 !important;
  color: {TEXT} !important;
  line-height: 1.3 !important;
}}
p, .stMarkdown p {{
  font-size: 16px;
  line-height: 1.5;
  color: {TEXT};
}}
[data-testid="stCaptionContainer"], .fs-caption {{
  font-size: 13px !important;
  line-height: 1.45 !important;
  color: {MUTED} !important;
}}
.fs-prose {{
  max-width: 640px;
}}

/* Hero — flat, no boxed panel */
.fs-hero {{
  background: transparent;
  border: none;
  border-radius: 0;
  padding: 0 0 24px 0;
  margin-bottom: 24px;
}}
.fs-eyebrow {{
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: {PRIMARY};
  margin: 0 0 8px 0;
}}
.fs-hero-promise {{
  font-size: 16px;
  margin: 8px 0;
  max-width: 640px;
  color: {TEXT};
  font-weight: 400;
  line-height: 1.5;
}}
.fs-hero-sub {{
  color: {MUTED};
  font-size: 13px;
  margin: 0;
  max-width: 640px;
  line-height: 1.45;
}}
/* Status chip — text + green underline, not a solid button */
.fs-mode-pill {{
  display: inline-block;
  margin-top: 14px;
  padding: 4px 0 6px 0;
  border: none;
  border-bottom: 2px solid {PRIMARY};
  border-radius: 0;
  background: transparent;
  color: {PRIMARY} !important;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.3;
  min-height: 0;
}}
.fs-mode-pill.demo {{
  border-bottom-color: {MUTED};
  color: {MUTED} !important;
}}

.fs-section {{
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 48px 0 8px 0;
  padding-bottom: 0;
  border-bottom: none;
}}
.fs-section-sub {{
  color: {MUTED};
  font-size: 16px;
  margin: 0 0 24px 0;
  max-width: 640px;
  line-height: 1.5;
}}

/* Horizontal radios render as answer tiles; the dot stays as the selection cue */
div[data-testid="stRadio"] [role="radiogroup"] {{
  flex-wrap: wrap !important;
  gap: 8px !important;
}}
div[data-testid="stRadio"] [role="radiogroup"] > label[data-baseweb="radio"] {{
  margin: 0 !important;
  padding: 8px 14px 8px 10px !important;
  min-height: 44px !important;
  line-height: 1.3 !important;
  align-items: center !important;
  border: 1.5px solid {CARD_BORDER};
  border-radius: 10px;
  background: {SURFACE};
  cursor: pointer;
  transition: border-color .12s ease, background-color .12s ease;
}}
div[data-testid="stRadio"] [role="radiogroup"] > label[data-baseweb="radio"]:hover {{
  border-color: #A9C3A5;
}}
div[data-testid="stRadio"] [role="radiogroup"] > label[data-baseweb="radio"]:has(input:checked) {{
  border-color: {PRIMARY};
  background: #EFF6ED;
}}
div[data-testid="stRadio"] [role="radiogroup"]:focus-within > label:has(input:checked) {{
  outline: 3px solid {FOCUS};
  outline-offset: 2px;
}}
div[data-testid="stRadio"] label[data-baseweb="radio"] [data-testid="stMarkdownContainer"] p {{
  font-size: 15px;
  font-weight: 500;
}}
@media (prefers-reduced-motion: reduce) {{
  div[data-testid="stRadio"] label[data-baseweb="radio"] {{ transition: none; }}
}}

/* Goal cards: three equal reply tiles */
[class*="st-key-goal-"] [role="radiogroup"] {{ flex-wrap: nowrap !important; gap: 6px !important; }}
[class*="st-key-goal-"] [role="radiogroup"] > label[data-baseweb="radio"] {{
  flex: 1 1 0;
  min-width: 0;
  padding: 6px 8px 6px 6px !important;
  min-height: 40px !important;
}}

/* Soil tiles carry a colour swatch of the soil */
[class*="st-key-soil-cat-"] [role="radiogroup"] > label p::before {{
  content: "";
  display: inline-block;
  width: 14px;
  height: 14px;
  margin: 0 8px -2px 0;
  border-radius: 4px;
  background: var(--fs-soil, transparent);
  box-shadow: inset 0 0 0 1px rgba(0,0,0,.15);
}}
[class*="st-key-soil-cat-"] [role="radiogroup"] > label:nth-of-type(1) {{ --fs-soil: #E4CB86; }}
[class*="st-key-soil-cat-"] [role="radiogroup"] > label:nth-of-type(2) {{ --fs-soil: #8A6038; }}
[class*="st-key-soil-cat-"] [role="radiogroup"] > label:nth-of-type(3) {{ --fs-soil: #BCAE97; }}
[class*="st-key-soil-cat-"] [role="radiogroup"] > label:nth-of-type(4) {{ --fs-soil: #A4532F; }}
[class*="st-key-soil-cat-"] [role="radiogroup"] > label:nth-of-type(5) p::before {{
  display: none;
}}
div[data-testid="stCheckbox"] label {{
  min-height: 40px !important;
  line-height: 1.4 !important;
}}

/* About your farm — plain questions a farmer can answer */
.fs-farm-banner {{
  margin: 0 0 20px 0;
  padding: 0 0 0 12px;
  border-left: 3px solid {PRIMARY};
  font-size: 14px;
  line-height: 1.45;
  color: {TEXT};
  max-width: 640px;
}}
/* Farmer questions: the question is the heading, one reason line under it */
.fs-q {{
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin: 36px 0 12px 0;
}}
.fs-q-num {{
  flex: none;
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: {PRIMARY};
  color: #FFFFFF;
  font-size: 14px;
  font-weight: 700;
}}
.fs-q:not(:has(.fs-q-num)) {{ margin: 8px 0 10px 0; }}
.fs-q:not(:has(.fs-q-num)) p.fs-q-text {{ font-size: 16px; }}
@media (min-width: 900px) {{
  .fs-q:has(.fs-q-num) {{ margin-left: -40px; }}
}}
p.fs-q-text {{
  margin: 0;
  font-size: 19px;
  font-weight: 600;
  line-height: 1.3;
  color: {TEXT};
}}
p.fs-q-why {{
  margin: 4px 0 0 0;
  font-size: 14px;
  line-height: 1.4;
  color: {MUTED};
  max-width: 600px;
}}
p.fs-farm-confirm {{
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  font-size: 15px;
  color: {TEXT};
}}
.fs-tick {{
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #EFF6ED;
  color: {PRIMARY};
  font-weight: 700;
  font-size: 13px;
}}

/* Farming-year calendar */
p.fs-year-title {{
  margin: 22px 0 8px 0;
  font-size: 15px;
  font-weight: 600;
  color: {TEXT};
}}
.fs-year {{ margin: 0 0 6px 0; }}
.fs-year-row {{
  display: grid;
  grid-template-columns: 1fr;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}}
.fs-year--labelled .fs-year-row {{ grid-template-columns: 50px 1fr; }}
.fs-year-lab {{ font-size: 12px; color: {MUTED}; }}
.fs-year-track {{
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 2px;
}}
.fs-year-head .fs-year-track span {{
  font-size: 11px;
  color: {MUTED};
  text-align: center;
}}
.fs-year-seg {{
  display: flex;
  align-items: center;
  min-width: 0;
  height: 34px;
  padding: 0 8px;
  border-radius: 6px;
  overflow: hidden;
}}
.fs-year-seg span {{
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-size: 13px;
  font-weight: 600;
  color: {TEXT};
}}
.fs-year-seg.is-bare span {{ font-weight: 400; color: {MUTED}; }}
.fs-year--compact {{ margin: 8px 0 10px 0; }}
.fs-year--compact .fs-year-row {{ gap: 6px; margin-bottom: 3px; }}
.fs-year--compact.fs-year--labelled .fs-year-row {{ grid-template-columns: 42px 1fr; }}
.fs-year--compact .fs-year-lab {{ font-size: 11px; }}
.fs-year--compact .fs-year-head .fs-year-track span {{ font-size: 10px; }}
.fs-year--compact .fs-year-seg {{ height: 22px; padding: 0 6px; border-radius: 4px; }}
.fs-year--compact .fs-year-seg span {{ font-size: 11px; }}
.fs-year-legend {{
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
  margin-top: 8px;
  font-size: 12px;
  color: {MUTED};
}}
.fs-year-legend i {{
  display: inline-block;
  width: 12px;
  height: 12px;
  margin: 0 6px -2px 0;
  border-radius: 3px;
  box-shadow: inset 0 0 0 1px rgba(0,0,0,.1);
}}

/* Goal cards and the ranking mix bar */
p.fs-goal-name {{
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  line-height: 1.25;
  color: {TEXT};
}}
.fs-goal-name i {{
  flex: none;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}}
p.fs-goal-q {{
  margin: 4px 0 0 0;
  min-height: 2.7em;
  font-size: 13.5px;
  line-height: 1.35;
  color: {MUTED};
}}
.fs-mix {{ margin: 18px 0 4px 0; }}
p.fs-mix-title {{
  margin: 0 0 8px 0;
  font-size: 15px;
  font-weight: 600;
  color: {TEXT};
}}
.fs-mix-bar {{
  display: flex;
  gap: 2px;
  height: 18px;
  border-radius: 9px;
  overflow: hidden;
}}
.fs-mix-seg {{ min-width: 6px; }}
.fs-mix-legend {{
  display: flex;
  flex-wrap: wrap;
  gap: 4px 18px;
  margin-top: 8px;
  font-size: 13px;
  color: {TEXT};
}}
.fs-mix-legend i {{
  display: inline-block;
  width: 10px;
  height: 10px;
  margin-right: 6px;
  border-radius: 50%;
}}
.fs-farm-slot-label {{
  margin: 0 0 6px 0;
  font-size: 14px;
  color: {TEXT};
  line-height: 1.35;
}}
.fs-farm-slot-meta {{
  display: block;
  margin-top: 2px;
  font-size: 12px;
  font-weight: 400;
  color: {MUTED};
}}
.fs-step {{
  display: inline;
  font-size: 13px;
  font-weight: 500;
  color: {MUTED};
  letter-spacing: 0.02em;
  background: none;
  padding: 0;
  min-width: 0;
  height: auto;
  border-radius: 0;
}}

/* Home steps — flat, no boxes */
.fs-home-steps {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
  margin: 8px 0 32px 0;
}}
.fs-home-step {{
  background: transparent;
  border: none;
  border-radius: 0;
  padding: 0;
}}
.fs-home-step-num {{
  font-size: 13px;
  font-weight: 500;
  color: {MUTED};
  margin: 0 0 8px 0;
}}
.fs-home-step-title {{
  font-size: 16px;
  font-weight: 600;
  color: {TEXT};
  margin: 0 0 4px 0;
}}
.fs-home-step-body {{
  font-size: 13px;
  color: {MUTED};
  margin: 0;
  line-height: 1.45;
}}
@media (max-width: 700px) {{
  .fs-home-steps {{ grid-template-columns: 1fr; }}
}}

/* Fact chips — metric-style, no borders */
.fs-chip-grid {{
  display: grid;
  grid-template-columns: repeat(var(--fs-chip-cols, 4), minmax(0, 1fr));
  gap: 24px;
  margin: 8px 0 32px 0;
  align-items: stretch;
}}
.fs-chip {{
  display: flex;
  flex-direction: column;
  background: transparent;
  border: none;
  border-radius: 0;
  padding: 0;
  min-height: 0;
  height: 100%;
  box-sizing: border-box;
  overflow: visible;
}}
.fs-chip-label {{
  font-size: 13px;
  color: {MUTED};
  margin: 0 0 4px 0;
  font-weight: 500;
}}
.fs-chip-value {{
  font-size: 28px;
  font-weight: 600;
  color: {TEXT};
  margin: 0 0 4px 0;
  line-height: 1.2;
  overflow: visible;
  font-variant-numeric: tabular-nums;
}}
.fs-chip-meaning {{
  font-size: 13px;
  color: {MUTED};
  margin: 0;
  line-height: 1.45;
  flex: 1 1 auto;
}}
.fs-chip-source {{
  margin: 8px 0 0 0;
  padding-top: 0;
  border-top: none;
  font-size: 12px;
  line-height: 1.35;
  color: {MUTED};
}}
@media (max-width: 700px) {{
  .fs-chip-grid {{ grid-template-columns: 1fr 1fr; }}
}}

/* Options grid labels */
.fs-options-label {{
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: {MUTED};
  margin: 24px 0 12px 0;
}}

/* Strategy cards — even columns, shared score figure */
.fs-strat {{
  margin: 0;
  padding: 16px 8px 12px 0;
  border-top: 1px solid {CARD_BORDER};
  overflow: visible;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 520px;
}}
.fs-tier-kicker {{
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  color: {MUTED};
  margin: 0 0 8px 0;
  min-height: 1.2em;
}}
.fs-best-badge {{
  display: inline-block;
  font-size: 12px;
  font-weight: 600;
  color: {PRIMARY};
  background: #E8F2E7;
  padding: 2px 8px;
  border-radius: 6px;
  margin: 0 0 8px 0;
  width: fit-content;
}}
.fs-strat-title {{
  font-size: 16px;
  font-weight: 600;
  color: {TEXT};
  margin: 0;
  line-height: 1.35;
  min-height: 2.7em;
  overflow: visible;
}}
.fs-tier-reason {{
  font-size: 13px;
  color: {MUTED};
  margin: 8px 0 0;
  line-height: 1.45;
  min-height: 3.9em;
}}
.fs-strat-flags {{
  min-height: 20px;
  margin: 8px 0;
  font-size: 13px;
  color: {MUTED};
  line-height: 1.35;
}}
.fs-strat-flags .bad {{ color: {DANGER}; }}

.fs-overall {{
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin: 16px 0 8px 0;
  padding: 0;
  background: transparent;
  border: none;
  min-height: 52px;
}}
.fs-overall-label {{
  font-size: 13px;
  color: {MUTED};
  font-weight: 500;
  margin: 0 0 2px 0;
}}
.fs-overall-num {{
  font-size: 36px;
  font-weight: 600;
  color: {TEXT};
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}}
.fs-card-delta {{
  font-size: 13px;
  font-weight: 500;
  padding: 0;
  border-radius: 0;
  white-space: nowrap;
  background: transparent !important;
  text-align: right;
}}
.fs-card-delta.up {{ color: {PRIMARY}; }}
.fs-card-delta.down {{ color: {DANGER}; }}
.fs-card-delta.flat {{ color: {MUTED}; }}
.fs-card-note {{
  font-size: 13px;
  color: {MUTED};
  margin: 0 0 8px 0;
}}
.fs-card-spacer {{
  flex: 1 1 auto;
  min-height: 8px;
}}
.fs-score-heading {{
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  color: {MUTED};
  margin: 12px 0 8px 0;
}}
.fs-score-grid {{
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0 0 12px 0;
  min-height: 168px;
}}
.fs-score-row {{
  display: flex;
  flex-direction: column;
  gap: 3px;
}}
.fs-score-top {{
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}}
.fs-score-name {{
  font-size: 12px;
  font-weight: 500;
  color: {TEXT};
}}
.fs-score-pct {{
  font-size: 12px;
  font-weight: 600;
  color: {MUTED};
  font-variant-numeric: tabular-nums;
}}
.fs-score-track {{
  height: 6px;
  background: {SIDEBAR};
  border-radius: 3px;
  overflow: hidden;
}}
.fs-score-fill {{
  height: 100%;
  border-radius: 3px;
  min-width: 2px;
}}
.fs-compare-note {{
  font-size: 12px;
  color: {MUTED};
  margin: 0 0 8px 0;
  min-height: 3.6em;
  line-height: 1.4;
}}
.fs-diff-list {{
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 0 0 8px 0;
  min-height: 3.6em;
}}
.fs-diff-line {{
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: baseline;
  font-size: 12px;
  line-height: 1.35;
}}
.fs-diff-name {{
  font-weight: 500;
  color: {TEXT};
}}
.fs-diff-band {{
  color: {MUTED};
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
  text-align: right;
}}
.fs-conf {{
  font-size: 12px;
  color: {MUTED};
  margin: 8px 0 0 0;
  letter-spacing: 0.01em;
}}

/* Equal-height option / demo columns */
div[data-testid="stHorizontalBlock"] {{
  align-items: flex-start !important;
  gap: 24px !important;
}}
div[data-testid="stHorizontalBlock"]:has(.fs-strat),
div[data-testid="stHorizontalBlock"]:has(.fs-demo-copy) {{
  align-items: stretch !important;
}}
div[data-testid="stHorizontalBlock"]:has(.fs-strat) > div[data-testid="stColumn"],
div[data-testid="stHorizontalBlock"]:has(.fs-demo-copy) > div[data-testid="stColumn"] {{
  display: flex !important;
  flex-direction: column;
}}
div[data-testid="stHorizontalBlock"]:has(.fs-strat) > div[data-testid="stColumn"] > div,
div[data-testid="stHorizontalBlock"]:has(.fs-demo-copy) > div[data-testid="stColumn"] > div {{
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  height: 100%;
}}
.fs-chart-wrap {{
  display: none;
}}
/* Plotly / map figures — consistent breathing room */
div[data-testid="stPlotlyChart"],
iframe[title="streamlit_folium.st_folium"] {{
  margin: 4px 0 8px 0;
}}

.fs-banner {{
  background: transparent;
  border: none;
  border-left: 3px solid {PRIMARY};
  border-radius: 0;
  padding: 4px 0 4px 16px;
  margin: 8px 0 24px 0;
  font-size: 16px;
  color: {TEXT};
  box-shadow: none;
  max-width: 640px;
}}
.fs-banner strong {{ color: {PRIMARY}; }}

.fs-pills {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0;
  align-items: center;
  min-height: 40px;
}}
.fs-pill {{
  display: inline-block;
  background: {SIDEBAR};
  border: none;
  border-radius: {CARD_RADIUS};
  padding: 4px 12px;
  font-size: 13px;
  color: {TEXT};
  line-height: 1.4;
}}
.fs-pill-arrow {{
  color: {MUTED};
  font-size: 13px;
}}

.fs-badge {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0;
  border-radius: 0;
  border: none;
  font-size: 13px;
  font-weight: 500;
  background: transparent !important;
}}
.fs-badge.high {{ color: {PRIMARY}; }}
.fs-badge.medium {{ color: {INFO}; }}
.fs-badge.low {{ color: {DANGER}; }}

/* Sliders — prevent value label clipping */
div[data-testid="stSlider"] {{
  padding-left: 8px;
  padding-right: 8px;
  overflow: visible !important;
}}
div[data-testid="stSlider"] [data-baseweb="slider"] {{
  overflow: visible !important;
}}
div[data-testid="stSlider"] label {{
  font-size: 16px !important;
}}

div[data-testid="stMetricValue"] {{
  font-size: 28px !important;
  font-weight: 600 !important;
  color: {TEXT} !important;
  line-height: 1.2 !important;
  overflow: visible !important;
}}
div[data-testid="stMetricLabel"] {{
  font-size: 13px !important;
  color: {MUTED} !important;
}}

.stButton > button {{
  border-radius: {CARD_RADIUS} !important;
  min-height: 44px !important;
  font-weight: 600 !important;
  transition: background-color 0.15s ease, border-color 0.15s ease !important;
}}
.stButton > button[kind="primary"],
button[kind="primary"] {{
  background-color: {PRIMARY} !important;
  border: 1px solid {PRIMARY} !important;
  color: {SURFACE} !important;
}}
.stButton > button[kind="primary"] *,
button[kind="primary"] * {{
  color: {SURFACE} !important;
}}
.stButton > button[kind="primary"]:hover,
button[kind="primary"]:hover {{
  background-color: {FOCUS} !important;
  border-color: {FOCUS} !important;
}}
.stButton > button:focus-visible,
/* Exclude select filter inputs — they are ~2px wide; a 3px outline
   reads as a green caret box beside the selected value while typing. */
input:focus-visible:not([role="combobox"]) {{
  outline: 3px solid {FOCUS} !important;
  outline-offset: 2px !important;
}}
div[data-testid="stSelectbox"] input,
div[data-testid="stMultiSelect"] input,
[data-baseweb="select"] input,
[data-baseweb="select"] input:focus,
[data-baseweb="select"] input:focus-visible {{
  outline: none !important;
  outline-width: 0 !important;
  outline-offset: 0 !important;
  box-shadow: none !important;
  caret-color: {TEXT} !important;
}}

/* Expanders — thin top divider only; no box / fill */
[data-testid="stExpander"],
[data-testid="stExpander"] > details,
[data-testid="stExpander"] details {{
  border: none !important;
  border-radius: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
}}
[data-testid="stExpander"] details {{
  border-top: 1px solid {CARD_BORDER} !important;
}}
[data-testid="stExpander"] summary {{
  padding: 12px 0 !important;
  font-size: 14px !important;
  min-height: 44px;
  color: {MUTED} !important;
  background: transparent !important;
}}
[data-testid="stExpander"] [data-testid="stExpanderDetails"],
[data-testid="stExpander"] .streamlit-expanderContent {{
  background: transparent !important;
  border: none !important;
}}
div[data-testid="stDataFrame"] {{
  border: none;
  border-radius: 0;
  overflow: hidden;
}}
/* Hide Streamlit chrome on images/tables — quieter for farmers */
div[data-testid="stImage"] [data-testid="stElementToolbar"],
div[data-testid="stDataFrame"] [data-testid="stElementToolbar"],
div[data-testid="stDataFrameToolbar"],
div[data-testid="stPlotlyChart"] [data-testid="stElementToolbar"] {{
  display: none !important;
}}

[data-testid="stImage"] img {{
  border-radius: 0;
  border: none;
}}
div[data-testid="stHorizontalBlock"] [data-testid="stImage"] img {{
  max-height: 320px;
  width: 100%;
  object-fit: contain;
  background: {SIDEBAR};
}}
.fs-demo-thumb-empty {{
  aspect-ratio: 5 / 4;
  background: {SIDEBAR};
  border: none;
  border-radius: 0;
}}
.fs-demo-bordered {{
  display: none;
}}
.fs-demo-copy {{
  display: flex;
  flex-direction: column;
  min-height: 132px;
  margin: 12px 0 8px 0;
  flex: 1 1 auto;
}}
.fs-demo-card-title {{
  font-weight: 600;
  font-size: 16px;
  color: {TEXT};
  margin: 0 0 4px 0;
  line-height: 1.3;
  min-height: 2.6em;
}}
.fs-demo-card-meta {{
  color: {MUTED};
  font-size: 13px;
  margin: 0 0 8px 0;
  line-height: 1.35;
  min-height: 2.7em;
}}
.fs-demo-card-rot {{
  color: {TEXT};
  font-size: 13px;
  margin: auto 0 0 0;
}}

.fs-glossary {{
  display: grid;
  gap: 8px;
  margin: 8px 0 32px 0;
}}
.fs-glossary-row {{
  display: grid;
  grid-template-columns: minmax(7rem, 11rem) 1fr;
  gap: 16px;
  padding: 12px 0;
  background: transparent;
  border: none;
  border-bottom: 1px solid {CARD_BORDER};
  border-radius: 0;
}}
.fs-glossary-term {{
  font-size: 13px;
  font-weight: 600;
  color: {PRIMARY};
}}
.fs-glossary-def {{
  font-size: 16px;
  color: {TEXT};
  line-height: 1.5;
  margin: 0;
  max-width: 640px;
}}
@media (max-width: 700px) {{
  .fs-glossary-row {{ grid-template-columns: 1fr; gap: 4px; }}
}}

.fs-chart-takeaway {{
  font-size: 16px;
  color: {TEXT};
  margin: 0 0 16px 0;
  max-width: 640px;
  line-height: 1.5;
  font-weight: 400;
}}

@media (max-width: 400px) {{
  .block-container {{ padding-left: 16px; padding-right: 16px; }}
  h1, .fs-title {{ font-size: 28px !important; }}
  .fs-chip-value, .fs-overall-num {{ font-size: 24px; }}
}}
</style>
        """,
        unsafe_allow_html=True,
    )
