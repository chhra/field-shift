"""
Satellite vs ground: compare NASA POWER rainfall with the Rothamsted rain gauge.

The challenge asks the tool to explain how satellite data differs from ground
measurements. NASA POWER rainfall is a model/satellite estimate averaged over a
grid cell about 50 km wide. The Rothamsted Meteorological Station (Harpenden)
has measured rain with a gauge, in one spot, every day since 1853. This script
puts the two side by side, month by month.

Inputs
  data/processed/climate/nasa_power_clean.csv            daily NASA POWER (must be the
                                                         Rothamsted Broadbalk download)
  data/raw/rothamsted/01-data-rain-1853-2024_DATA.csv    monthly station rain: the DATA
                                                         sheet of 01-data-rain-1853-2024.xlsx

Outputs (data/processed/climate/)
  station_vs_nasa_rain_monthly.csv    one row per month: station (raw and corrected), NASA, difference
  station_vs_nasa_rain_yearly.csv     one row per year
  station_vs_nasa_rain_summary.json   the headline numbers, with the source and method

Station data
  Perryman S.A.M. & Scott T. (2025) Total Monthly and Annual Rain at Rothamsted
  March 1853-2024. Electronic Rothamsted Archive, Rothamsted Research.
  DOI 10.23637/rmsTMArain1853-2024-01. Licence: CC BY 4.0.

Rain gauge correction (from the dataset's ReadMe)
  From 11 Dec 2003 to 9 Sep 2020 the station used an ARG100 gauge, which catches
  about 10% more rain than the gauges before and after it. Rothamsted's correction
  is to divide those years by 1.1098, and their file applies it to the whole years
  2004-2020. We do the same for each month of 2004-2020 and report both versions;
  the corrected one is the fair comparison. (Sep-Dec 2020 were measured by the new
  gauge, so those four months are slightly over-corrected.)
"""
import json
import math
from pathlib import Path

import pandas as pd

# ==========================================
# 1. Paths and settings
# ==========================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLIMATE_DIR = PROJECT_ROOT / "data" / "processed" / "climate"

NASA_FILE = CLIMATE_DIR / "nasa_power_clean.csv"
STATION_FILE = PROJECT_ROOT / "data" / "raw" / "rothamsted" / "01-data-rain-1853-2024_DATA.csv"

MONTHLY_FILE = CLIMATE_DIR / "station_vs_nasa_rain_monthly.csv"
YEARLY_FILE = CLIMATE_DIR / "station_vs_nasa_rain_yearly.csv"
SUMMARY_FILE = CLIMATE_DIR / "station_vs_nasa_rain_summary.json"

STATION_LAT, STATION_LON = 51.809, -0.373      # Rothamsted, Harpenden
MAX_DISTANCE_KM = 30                           # NASA point must be this close to the station

GAUGE_CORRECTION = 1.1098                      # ARG100 gauge, see the note above
CORRECTED_YEARS = range(2004, 2021)            # 2004-2020 inclusive

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
SEASONS = {"winter (Dec-Feb)": [12, 1, 2], "spring (Mar-May)": [3, 4, 5],
           "summer (Jun-Aug)": [6, 7, 8], "autumn (Sep-Nov)": [9, 10, 11]}

# ==========================================
# 2. Load NASA POWER and check it is the right place
# ==========================================

for f in (NASA_FILE, STATION_FILE):
    if not f.exists():
        raise FileNotFoundError(f"Input file not found: {f}")

nasa = pd.read_csv(NASA_FILE, parse_dates=["date"])
lat, lon = float(nasa["latitude"].iloc[0]), float(nasa["longitude"].iloc[0])


def distance_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two points (haversine formula)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(a))


km = distance_km(lat, lon, STATION_LAT, STATION_LON)
if km > MAX_DISTANCE_KM:
    raise SystemExit(
        f"The NASA POWER data is for {lat}, {lon}, which is {km:.0f} km from the Rothamsted "
        f"station. Download NASA POWER for Rothamsted Broadbalk first (download_power.py).")

# monthly totals, full months only
nasa["year"], nasa["month"] = nasa["date"].dt.year, nasa["date"].dt.month
nasa_m = nasa.groupby(["year", "month"]).agg(nasa_mm=("prectotcorr", "sum"),
                                             days=("prectotcorr", "size")).reset_index()
nasa_m = nasa_m[nasa_m["days"] == pd.to_datetime(
    dict(year=nasa_m["year"], month=nasa_m["month"], day=1)).dt.days_in_month]

# ==========================================
# 3. Load the station data (wide table -> one row per month)
# ==========================================

# semicolon-separated, 3 note lines above the header, starts with a "BOM" character
wide = pd.read_csv(STATION_FILE, sep=";", skiprows=3, encoding="utf-8-sig")
station = wide.melt(id_vars="Year", value_vars=MONTH_NAMES, var_name="month_name",
                    value_name="station_raw_mm").rename(columns={"Year": "year"})
station["month"] = station["month_name"].map({m: i + 1 for i, m in enumerate(MONTH_NAMES)})
station = station.dropna(subset=["station_raw_mm"])

# apply Rothamsted's gauge correction to 2004-2020
station["station_mm"] = station["station_raw_mm"].where(
    ~station["year"].isin(CORRECTED_YEARS), station["station_raw_mm"] / GAUGE_CORRECTION)

# ==========================================
# 4. Join month by month
# ==========================================

both = station.merge(nasa_m[["year", "month", "nasa_mm"]], on=["year", "month"]) \
              .sort_values(["year", "month"]).reset_index(drop=True)
both["diff_mm"] = both["nasa_mm"] - both["station_mm"]          # NASA minus station
both["diff_raw_mm"] = both["nasa_mm"] - both["station_raw_mm"]

# keep only years with all 12 months in both sources
full = both.groupby("year")["month"].transform("size") == 12
both = both[full]
years = sorted(both["year"].unique())
print(f"Comparing {len(both)} months, {years[0]}-{years[-1]}; "
      f"NASA point is {km:.1f} km from the station")

# ==========================================
# 5. The numbers
# ==========================================


def stats(nasa_col, station_col):
    """Agreement between two series of monthly totals."""
    d = nasa_col - station_col
    return {
        "bias_mm_per_month": round(float(d.mean()), 1),                 # + = NASA wetter
        "bias_pct": round(float(d.sum() / station_col.sum() * 100), 1),
        "mean_abs_error_mm": round(float(d.abs().mean()), 1),
        "rmse_mm": round(float((d ** 2).mean() ** 0.5), 1),
        "correlation": round(float(nasa_col.corr(station_col)), 2),
    }


yearly = both.groupby("year").agg(station_mm=("station_mm", "sum"),
                                  station_raw_mm=("station_raw_mm", "sum"),
                                  nasa_mm=("nasa_mm", "sum")).round(1)
yearly["diff_mm"] = (yearly["nasa_mm"] - yearly["station_mm"]).round(1)
yearly["diff_pct"] = (yearly["diff_mm"] / yearly["station_mm"] * 100).round(1)

by_month = both.groupby("month").agg(station_mm=("station_mm", "mean"),
                                     nasa_mm=("nasa_mm", "mean")).round(1)

seasons = {}
for name, months in SEASONS.items():
    s = both[both["month"].isin(months)]
    seasons[name] = {"station_mm_per_month": round(float(s["station_mm"].mean()), 1),
                     "nasa_mm_per_month": round(float(s["nasa_mm"].mean()), 1),
                     **stats(s["nasa_mm"], s["station_mm"])}

# how NASA does in the wettest and driest months the gauge recorded (top / bottom 10%)
wet_cut, dry_cut = both["station_mm"].quantile(0.9), both["station_mm"].quantile(0.1)
wet, dry = both[both["station_mm"] >= wet_cut], both[both["station_mm"] <= dry_cut]

summary = {
    "period": f"{years[0]}-{years[-1]}",
    "months_compared": int(len(both)),
    "nasa_point": {"latitude": lat, "longitude": lon, "distance_to_station_km": round(km, 1)},
    "mean_annual_rain_mm": {
        "station_corrected": round(float(yearly["station_mm"].mean())),
        "station_raw": round(float(yearly["station_raw_mm"].mean())),
        "nasa_power": round(float(yearly["nasa_mm"].mean())),
    },
    "monthly_agreement_corrected_station": stats(both["nasa_mm"], both["station_mm"]),
    "monthly_agreement_raw_station": stats(both["nasa_mm"], both["station_raw_mm"]),
    "yearly_correlation": round(float(yearly["nasa_mm"].corr(yearly["station_mm"])), 2),
    "by_season": seasons,
    "wettest_10pct_of_months": {
        "station_at_least_mm": round(float(wet_cut), 1), "months": int(len(wet)),
        "station_mean_mm": round(float(wet["station_mm"].mean()), 1),
        "nasa_mean_mm": round(float(wet["nasa_mm"].mean()), 1),
        "nasa_vs_station_pct": round(float((wet["nasa_mm"].sum() / wet["station_mm"].sum() - 1) * 100), 1),
    },
    "driest_10pct_of_months": {
        "station_at_most_mm": round(float(dry_cut), 1), "months": int(len(dry)),
        "station_mean_mm": round(float(dry["station_mm"].mean()), 1),
        "nasa_mean_mm": round(float(dry["nasa_mm"].mean()), 1),
    },
    "mean_by_calendar_month_mm": {
        MONTH_NAMES[m - 1]: {"station": float(r["station_mm"]), "nasa": float(r["nasa_mm"])}
        for m, r in by_month.iterrows()},
    "method": {
        "nasa": "NASA POWER daily PRECTOTCORR summed to calendar months (grid cell about 0.5 x 0.625 degrees)",
        "station": "Rothamsted Meteorological Station monthly totals (one rain gauge)",
        "gauge_correction": f"station months in 2004-2020 divided by {GAUGE_CORRECTION} "
                            "(ARG100 gauge, per the dataset ReadMe)",
        "difference": "NASA minus station; positive = NASA wetter",
    },
    "station_source": ("Perryman S.A.M. & Scott T. (2025) Total Monthly and Annual Rain at Rothamsted "
                       "March 1853-2024. Electronic Rothamsted Archive, Rothamsted Research. "
                       "DOI 10.23637/rmsTMArain1853-2024-01. CC BY 4.0."),
}

# ==========================================
# 6. Save and print
# ==========================================

both[["year", "month", "station_raw_mm", "station_mm", "nasa_mm", "diff_mm", "diff_raw_mm"]] \
    .round(1).to_csv(MONTHLY_FILE, index=False)
yearly.reset_index().to_csv(YEARLY_FILE, index=False)
SUMMARY_FILE.write_text(json.dumps(summary, indent=2), encoding="utf-8")

a = summary["monthly_agreement_corrected_station"]
print("\n========== NASA POWER vs ROTHAMSTED RAIN GAUGE ==========")
print(f"Mean annual rain:  station {summary['mean_annual_rain_mm']['station_corrected']} mm "
      f"(raw {summary['mean_annual_rain_mm']['station_raw']})   "
      f"NASA {summary['mean_annual_rain_mm']['nasa_power']} mm")
print(f"Monthly: bias {a['bias_mm_per_month']:+} mm ({a['bias_pct']:+}%), "
      f"typical error {a['mean_abs_error_mm']} mm, correlation {a['correlation']}")
print(f"Yearly correlation: {summary['yearly_correlation']}")
print("\nBy season (mm per month):")
for name, s in seasons.items():
    print(f"  {name:18} station {s['station_mm_per_month']:5}  NASA {s['nasa_mm_per_month']:5}  "
          f"bias {s['bias_pct']:+5}%  correlation {s['correlation']}")
w, d = summary["wettest_10pct_of_months"], summary["driest_10pct_of_months"]
print(f"\nWettest 10% of months: station {w['station_mean_mm']} mm, NASA {w['nasa_mean_mm']} mm "
      f"({w['nasa_vs_station_pct']:+}%)")
print(f"Driest 10% of months:  station {d['station_mean_mm']} mm, NASA {d['nasa_mean_mm']} mm")
print("\nCreated:")
for f in (MONTHLY_FILE, YEARLY_FILE, SUMMARY_FILE):
    print(f)
