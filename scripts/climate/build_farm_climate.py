"""
Build the farm's climate profile from the cleaned NASA POWER daily data.

Everything here depends ONLY on the weather at the farm, not on any crop.
Values that need a crop number (heat stress above a crop's threshold, frost
below a crop's killing temperature) are computed in team_model/model.py instead.

Input
  data/processed/climate/nasa_power_clean.csv   (made by clean_nasa_power.py)

Outputs (data/processed/climate/)
  farm_climate_monthly.csv   one row per calendar month (averages over full years):
                             rain, ET0, water balance, temperatures, frost days
  farm_climate_yearly.csv    one row per full year: rain, coldest night, frost days,
                             last spring / first autumn frost, hot days
  farm_climate_summary.json  the farm summary the rotation model reads
                             (same keys as FAKE_FARM in team_model/model.py, plus extras)

Notes
  - Only full calendar years are used, so a part year (e.g. 2026) can't bias averages.
  - NASA POWER temperature is AIR temperature at 2 m over a ~50 km grid cell.
    Ground frost is more frequent than air frost, so frost counts here are a
    lower bound: confirm with local experience.
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

# ==========================================
# 1. Project paths
# ==========================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLIMATE_DIR = PROJECT_ROOT / "data" / "processed" / "climate"

INPUT_FILE = CLIMATE_DIR / "nasa_power_clean.csv"
MONTHLY_FILE = CLIMATE_DIR / "farm_climate_monthly.csv"
YEARLY_FILE = CLIMATE_DIR / "farm_climate_yearly.csv"
SUMMARY_FILE = CLIMATE_DIR / "farm_climate_summary.json"

# ==========================================
# 2. Thresholds (change here, not in the code below)
# ==========================================

FROST_C = 0.0          # air frost: night minimum at or below 0 °C
HARD_FROST_C = -5.0    # hard frost
HOT_DAY_C = 25.0       # a "hot day" (UK Met Office summer-day threshold)
WET_MONTHS_N = 4       # "wet months" = the N months with the biggest water surplus (rain - ET0),
                       # i.e. when bare soil gets waterlogged, runs off and erodes
FROST_MONTH_DAYS = 1.0 # a month is a "frost month" if it averages at least this many frost days
GROWING_MONTHS = [4, 5, 6, 7, 8, 9]   # Apr-Sep, for the growing-season temperature
SUMMER_MONTHS = [6, 7, 8]             # Jun-Aug, for the summer drying trend
RECENT_YEARS = 10      # trends compare the last N full years with the years before
TREND_CHANGE = 0.10    # a change of more than 10% counts as a trend

# ==========================================
# 3. Load data and keep full years only
# ==========================================

if not INPUT_FILE.exists():
    raise FileNotFoundError(f"Input file not found: {INPUT_FILE} (run clean_nasa_power.py first)")

df = pd.read_csv(INPUT_FILE, parse_dates=["date"]).set_index("date").sort_index()
latitude = float(df["latitude"].iloc[0])
longitude = float(df["longitude"].iloc[0])

days_per_year = df.groupby(df.index.year).size()
full_years = [y for y, n in days_per_year.items() if n >= 365]
df = df[df.index.year.isin(full_years)]
print(f"Using {len(full_years)} full years: {full_years[0]}-{full_years[-1]}")

# ==========================================
# 4. Reference evapotranspiration (ET0), Hargreaves-Samani (FAO-56 Eq. 52)
#    Same formula as fieldshift/data/et0.py, copied so this script only needs pandas.
#    ET0 = 0.0023 * (Tmean + 17.8) * sqrt(Tmax - Tmin) * Ra
# ==========================================

def extraterrestrial_radiation_mm(lat_deg, doy):
    """FAO-56 Eq. 21-25: radiation at the top of the atmosphere, in mm/day of evaporation."""
    lat = math.radians(lat_deg)
    j = np.asarray(doy, dtype=float)
    dr = 1 + 0.033 * np.cos(2 * math.pi / 365 * j)
    delta = 0.409 * np.sin(2 * math.pi / 365 * j - 1.39)
    ws = np.arccos(np.clip(-np.tan(lat) * np.tan(delta), -1, 1))
    ra_mj = (24 * 60 / math.pi * 0.0820 * dr
             * (ws * np.sin(lat) * np.sin(delta) + np.cos(lat) * np.cos(delta) * np.sin(ws)))
    return ra_mj / 2.45   # MJ/m2/day -> mm/day


tmean = (df["t2m_max"] + df["t2m_min"]) / 2
ra = extraterrestrial_radiation_mm(latitude, df.index.dayofyear)
df["et0_mm"] = np.maximum(
    0.0023 * (tmean + 17.8) * np.sqrt((df["t2m_max"] - df["t2m_min"]).clip(lower=0)) * ra, 0)

df["frost"] = df["t2m_min"] <= FROST_C
df["hard_frost"] = df["t2m_min"] <= HARD_FROST_C
df["hot"] = df["t2m_max"] >= HOT_DAY_C

# ==========================================
# 5. Monthly profile (average over full years)
# ==========================================

# first total/count per (year, month), then average across years
ym = df.groupby([df.index.year, df.index.month]).agg(
    rain_mm=("prectotcorr", "sum"),
    et0_mm=("et0_mm", "sum"),
    t2m_mean_c=("t2m", "mean"),
    t2m_max_mean_c=("t2m_max", "mean"),
    t2m_min_mean_c=("t2m_min", "mean"),
    t2m_min_lowest_c=("t2m_min", "min"),
    frost_days=("frost", "sum"),
    hard_frost_days=("hard_frost", "sum"),
    hot_days=("hot", "sum"),
)
ym.index.names = ["year", "month"]

monthly = ym.groupby("month").mean()
monthly["t2m_min_lowest_c"] = ym.groupby("month")["t2m_min_lowest_c"].min()   # record, not average
monthly["water_balance_mm"] = monthly["rain_mm"] - monthly["et0_mm"]
monthly["frost_years_pct"] = (ym["frost_days"] > 0).groupby("month").mean() * 100
monthly = monthly.round(2).reset_index()

# ==========================================
# 6. Yearly table
# ==========================================

def last_spring_frost(g):
    """Last frost night in Jan-Jun (None if there was none)."""
    d = g.index[(g.index.month <= 6) & g["frost"]]
    return d.max().strftime("%m-%d") if len(d) else None


def first_autumn_frost(g):
    """First frost night in Jul-Dec (None if there was none)."""
    d = g.index[(g.index.month >= 7) & g["frost"]]
    return d.min().strftime("%m-%d") if len(d) else None


yearly = pd.DataFrame({
    "rain_mm": df.groupby(df.index.year)["prectotcorr"].sum(),
    "summer_rain_mm": df[df.index.month.isin(SUMMER_MONTHS)].groupby(
        df[df.index.month.isin(SUMMER_MONTHS)].index.year)["prectotcorr"].sum(),
    "et0_mm": df.groupby(df.index.year)["et0_mm"].sum(),
    "coldest_tmin_c": df.groupby(df.index.year)["t2m_min"].min(),
    "hottest_tmax_c": df.groupby(df.index.year)["t2m_max"].max(),
    "frost_days": df.groupby(df.index.year)["frost"].sum(),
    "hard_frost_days": df.groupby(df.index.year)["hard_frost"].sum(),
    "hot_days": df.groupby(df.index.year)["hot"].sum(),
    "last_spring_frost": df.groupby(df.index.year).apply(last_spring_frost),
    "first_autumn_frost": df.groupby(df.index.year).apply(first_autumn_frost),
})
yearly.index.name = "year"


def frost_free_days(row):
    """Days between the last spring frost and the first autumn frost."""
    if row["last_spring_frost"] is None or row["first_autumn_frost"] is None:
        return np.nan
    y = row.name
    return (pd.Timestamp(f"{y}-{row['first_autumn_frost']}")
            - pd.Timestamp(f"{y}-{row['last_spring_frost']}")).days - 1


yearly["frost_free_days"] = yearly.apply(frost_free_days, axis=1)
yearly = yearly.round(2).reset_index()

# ==========================================
# 7. Farm summary for the rotation model
# ==========================================

recent = yearly[yearly["year"] > full_years[-1] - RECENT_YEARS]
earlier = yearly[yearly["year"] <= full_years[-1] - RECENT_YEARS]


def changed(recent_value, earlier_value, direction):
    """True if the recent value moved more than TREND_CHANGE in the given direction."""
    if earlier_value == 0:
        return direction * recent_value > 0
    return direction * (recent_value - earlier_value) / earlier_value > TREND_CHANGE


def median_date(values):
    """Median of "MM-DD" strings, as "MM-DD" (None if empty)."""
    doys = [pd.Timestamp(f"2001-{v}").dayofyear for v in values if v]
    if not doys:
        return None
    return (pd.Timestamp("2001-01-01") + pd.Timedelta(days=int(np.median(doys)) - 1)).strftime("%m-%d")


summer_recent, summer_earlier = recent["summer_rain_mm"].mean(), earlier["summer_rain_mm"].mean()
hot_recent, hot_earlier = recent["hot_days"].mean(), earlier["hot_days"].mean()

summary = {
    # ---- the keys the rotation model uses (same as FAKE_FARM) ----
    "annual_rain_mm": round(float(yearly["rain_mm"].mean())),
    "wet_months": sorted(monthly.nlargest(WET_MONTHS_N, "water_balance_mm")["month"].astype(int).tolist()),
    "dry_months": monthly.loc[monthly["water_balance_mm"] < 0, "month"].astype(int).tolist(),
    "frost_months": monthly.loc[monthly["frost_days"] >= FROST_MONTH_DAYS, "month"].astype(int).tolist(),
    "coldest_temp_c": round(float(yearly["coldest_tmin_c"].median()), 1),
    "growing_temp_c": round(float(df.loc[df.index.month.isin(GROWING_MONTHS), "t2m"].mean()), 1),
    "summer_drying": bool(changed(summer_recent, summer_earlier, -1)),
    "heat_rising": bool(changed(hot_recent, hot_earlier, +1)),

    # ---- extras: evidence behind the values above, and frost dates ----
    "record_min_temp_c": round(float(yearly["coldest_tmin_c"].min()), 1),
    "frost_days_per_year": round(float(yearly["frost_days"].mean()), 1),
    "median_last_spring_frost": median_date(yearly["last_spring_frost"]),
    "median_first_autumn_frost": median_date(yearly["first_autumn_frost"]),
    "median_frost_free_days": round(float(yearly["frost_free_days"].median())),
    "summer_rain_recent_mm": round(float(summer_recent), 1),
    "summer_rain_earlier_mm": round(float(summer_earlier), 1),
    "hot_days_recent": round(float(hot_recent), 1),
    "hot_days_earlier": round(float(hot_earlier), 1),
    "recent_period": f"{int(recent['year'].min())}-{int(recent['year'].max())}",
    "earlier_period": f"{int(earlier['year'].min())}-{int(earlier['year'].max())}",

    # ---- provenance ----
    "latitude": latitude,
    "longitude": longitude,
    "years": f"{full_years[0]}-{full_years[-1]}",
    "source": "NASA POWER daily (t2m, t2m_max, t2m_min, prectotcorr); ET0 by Hargreaves-Samani",
    "thresholds": {"frost_c": FROST_C, "hard_frost_c": HARD_FROST_C, "hot_day_c": HOT_DAY_C,
                   "frost_month_days": FROST_MONTH_DAYS, "trend_change": TREND_CHANGE},
}

# ==========================================
# 8. Save
# ==========================================

monthly.to_csv(MONTHLY_FILE, index=False)
yearly.to_csv(YEARLY_FILE, index=False)
SUMMARY_FILE.write_text(json.dumps(summary, indent=2), encoding="utf-8")

print("\n========== FARM SUMMARY ==========")
for k, v in summary.items():
    if k != "thresholds":
        print(f"{k:28} {v}")
print("\nCreated:")
for f in (MONTHLY_FILE, YEARLY_FILE, SUMMARY_FILE):
    print(f)
