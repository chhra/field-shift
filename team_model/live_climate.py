"""Build a farm climate summary + daily weather for ANY UK coordinates, live.

The committed Broadbalk files (farm_climate_summary.json, nasa_power_clean.csv)
are built once by scripts/climate/*. This module does the same computation on the
fly for a point the farmer enters on the Home page, using NASA POWER (no API key),
so the UK rotation model can run at their own location, not only at Rothamsted.

Public entry point
    build_farm_from_power(lat, lon) -> (farm_summary_dict, daily_weather_df)

The farm dict has the same keys as team_model.model.FAKE_FARM (plus the extras the
UK page shows); the weather df has the same columns as nasa_power_clean.csv, indexed
by date, full calendar years only — exactly what model.recommend() consumes.

The climate maths below mirror scripts/climate/build_farm_climate.py. Kept here as a
self-contained function so the live path never touches the committed demo files.
"""

from __future__ import annotations

import datetime as _dt
import math

import numpy as np
import pandas as pd

from fieldshift.data.extract_power import fetch_power_daily

# United Kingdom bounding box (generous; includes the isles). The crop knowledge
# base and agronomy rules are UK-specific, so locations outside this box are
# rejected rather than scored with UK crops on a foreign climate.
UK_BOUNDS = {"lat_min": 49.5, "lat_max": 61.0, "lon_min": -8.7, "lon_max": 2.1}

# Same thresholds as scripts/climate/build_farm_climate.py.
FROST_C = 0.0
HARD_FROST_C = -5.0
HOT_DAY_C = 25.0
WET_MONTHS_N = 4
FROST_MONTH_DAYS = 1.0
GROWING_MONTHS = [4, 5, 6, 7, 8, 9]
SUMMER_MONTHS = [6, 7, 8]
RECENT_YEARS = 10
TREND_CHANGE = 0.10

# How many years of NASA POWER to request (full years only are kept).
_FETCH_YEARS = 20


def in_uk(lat: float, lon: float) -> bool:
    """True if (lat, lon) is inside the UK bounding box."""
    return (
        UK_BOUNDS["lat_min"] <= lat <= UK_BOUNDS["lat_max"]
        and UK_BOUNDS["lon_min"] <= lon <= UK_BOUNDS["lon_max"]
    )


def _extraterrestrial_radiation_mm(lat_deg: float, doy) -> np.ndarray:
    """FAO-56 top-of-atmosphere radiation in mm/day (for Hargreaves ET0)."""
    lat = math.radians(lat_deg)
    j = np.asarray(doy, dtype=float)
    dr = 1 + 0.033 * np.cos(2 * math.pi / 365 * j)
    delta = 0.409 * np.sin(2 * math.pi / 365 * j - 1.39)
    ws = np.arccos(np.clip(-np.tan(lat) * np.tan(delta), -1, 1))
    ra_mj = (
        24 * 60 / math.pi * 0.0820 * dr
        * (ws * np.sin(lat) * np.sin(delta) + np.cos(lat) * np.cos(delta) * np.sin(ws))
    )
    return ra_mj / 2.45  # MJ/m2/day -> mm/day


def _clean_daily(lat: float, lon: float) -> pd.DataFrame:
    """Fetch NASA POWER and return a daily frame shaped like nasa_power_clean.csv.

    Columns: latitude, longitude, t2m, t2m_max, t2m_min, prectotcorr, rh2m
    (lower-case), tz-naive date index, full calendar years only.
    """
    end = _dt.date.today() - _dt.timedelta(days=10)  # POWER lags ~a week
    start = _dt.date(end.year - _FETCH_YEARS, 1, 1)
    raw = fetch_power_daily(
        lat, lon, start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
    )
    if raw.empty:
        raise RuntimeError("NASA POWER returned no data for this location.")

    # Uppercase POWER names -> the model's lower-case columns; drop tz.
    idx = raw.index.tz_convert(None) if raw.index.tz is not None else raw.index
    rename = {
        "T2M": "t2m",
        "T2M_MAX": "t2m_max",
        "T2M_MIN": "t2m_min",
        "PRECTOTCORR": "prectotcorr",
        "RH2M": "rh2m",
    }
    df = raw.rename(columns=rename)
    df.index = idx
    df.index.name = "date"
    keep = [c for c in ("t2m", "t2m_max", "t2m_min", "prectotcorr", "rh2m") if c in df]
    df = df[keep].copy()
    df["latitude"] = float(lat)
    df["longitude"] = float(lon)

    # Keep whole years only, so a part year can't bias the averages.
    days = df.groupby(df.index.year).size()
    full_years = days[days >= 365].index
    df = df[df.index.year.isin(full_years)]
    if df.empty:
        raise RuntimeError("NASA POWER returned no complete years for this location.")
    return df.sort_index()


def _summarize(df: pd.DataFrame) -> dict:
    """Farm summary dict (same keys as model.FAKE_FARM + the UK page extras)."""
    latitude = float(df["latitude"].iloc[0])
    longitude = float(df["longitude"].iloc[0])
    full_years = sorted(df.index.year.unique().tolist())

    tmean = (df["t2m_max"] + df["t2m_min"]) / 2
    ra = _extraterrestrial_radiation_mm(latitude, df.index.dayofyear)
    df = df.assign(
        et0_mm=np.maximum(
            0.0023 * (tmean + 17.8)
            * np.sqrt((df["t2m_max"] - df["t2m_min"]).clip(lower=0)) * ra,
            0,
        ),
        frost=df["t2m_min"] <= FROST_C,
        hard_frost=df["t2m_min"] <= HARD_FROST_C,
        hot=df["t2m_max"] >= HOT_DAY_C,
    )

    # Monthly profile averaged across years.
    ym = df.groupby([df.index.year, df.index.month]).agg(
        rain_mm=("prectotcorr", "sum"),
        et0_mm=("et0_mm", "sum"),
        t2m_mean_c=("t2m", "mean"),
        frost_days=("frost", "sum"),
    )
    ym.index.names = ["year", "month"]
    monthly = ym.groupby("month").mean()
    monthly["water_balance_mm"] = monthly["rain_mm"] - monthly["et0_mm"]
    monthly = monthly.reset_index()

    # Yearly table.
    summer = df[df.index.month.isin(SUMMER_MONTHS)]
    yearly = pd.DataFrame(
        {
            "rain_mm": df.groupby(df.index.year)["prectotcorr"].sum(),
            "summer_rain_mm": summer.groupby(summer.index.year)["prectotcorr"].sum(),
            "coldest_tmin_c": df.groupby(df.index.year)["t2m_min"].min(),
            "frost_days": df.groupby(df.index.year)["frost"].sum(),
            "hot_days": df.groupby(df.index.year)["hot"].sum(),
            "last_spring_frost": df.groupby(df.index.year).apply(_last_spring_frost),
            "first_autumn_frost": df.groupby(df.index.year).apply(_first_autumn_frost),
        }
    )
    yearly.index.name = "year"
    yearly = yearly.reset_index()
    yearly["frost_free_days"] = yearly.apply(_frost_free_days, axis=1)

    recent = yearly[yearly["year"] > full_years[-1] - RECENT_YEARS]
    earlier = yearly[yearly["year"] <= full_years[-1] - RECENT_YEARS]
    summer_recent = float(recent["summer_rain_mm"].mean())
    summer_earlier = float(earlier["summer_rain_mm"].mean()) if len(earlier) else summer_recent
    hot_recent = float(recent["hot_days"].mean())
    hot_earlier = float(earlier["hot_days"].mean()) if len(earlier) else hot_recent

    return {
        # keys the rotation model uses (same as FAKE_FARM)
        "annual_rain_mm": round(float(yearly["rain_mm"].mean())),
        "wet_months": sorted(
            monthly.nlargest(WET_MONTHS_N, "water_balance_mm")["month"].astype(int).tolist()
        ),
        "dry_months": monthly.loc[
            monthly["water_balance_mm"] < 0, "month"
        ].astype(int).tolist(),
        "frost_months": monthly.loc[
            monthly["frost_days"] >= FROST_MONTH_DAYS, "month"
        ].astype(int).tolist(),
        "coldest_temp_c": round(float(yearly["coldest_tmin_c"].median()), 1),
        "growing_temp_c": round(
            float(df.loc[df.index.month.isin(GROWING_MONTHS), "t2m"].mean()), 1
        ),
        "summer_drying": bool(_changed(summer_recent, summer_earlier, -1)),
        "heat_rising": bool(_changed(hot_recent, hot_earlier, +1)),
        # extras shown on the UK page
        "frost_days_per_year": round(float(yearly["frost_days"].mean()), 1),
        "median_frost_free_days": round(float(yearly["frost_free_days"].median()))
        if yearly["frost_free_days"].notna().any()
        else None,
        "summer_rain_recent_mm": round(summer_recent, 1),
        "summer_rain_earlier_mm": round(summer_earlier, 1),
        "hot_days_recent": round(hot_recent, 1),
        "hot_days_earlier": round(hot_earlier, 1),
        "recent_period": f"{int(recent['year'].min())}-{int(recent['year'].max())}",
        "earlier_period": f"{int(earlier['year'].min())}-{int(earlier['year'].max())}"
        if len(earlier)
        else f"{full_years[0]}-{full_years[-1]}",
        # provenance
        "latitude": latitude,
        "longitude": longitude,
        "years": f"{full_years[0]}-{full_years[-1]}",
        "source": "NASA POWER daily, fetched live; ET0 by Hargreaves-Samani",
    }


def _last_spring_frost(g: pd.DataFrame):
    d = g.index[(g.index.month <= 6) & g["frost"]]
    return d.max().strftime("%m-%d") if len(d) else None


def _first_autumn_frost(g: pd.DataFrame):
    d = g.index[(g.index.month >= 7) & g["frost"]]
    return d.min().strftime("%m-%d") if len(d) else None


def _frost_free_days(row):
    if row["last_spring_frost"] is None or row["first_autumn_frost"] is None:
        return np.nan
    y = row["year"]
    return (
        pd.Timestamp(f"{y}-{row['first_autumn_frost']}")
        - pd.Timestamp(f"{y}-{row['last_spring_frost']}")
    ).days - 1


def _changed(recent_value: float, earlier_value: float, direction: int) -> bool:
    if earlier_value == 0:
        return direction * recent_value > 0
    return direction * (recent_value - earlier_value) / earlier_value > TREND_CHANGE


def build_farm_from_power(lat: float, lon: float) -> tuple[dict, pd.DataFrame]:
    """Fetch NASA POWER for (lat, lon) and return (farm_summary, daily_weather).

    Raises ValueError if the point is outside the UK box, RuntimeError if the
    NASA POWER request fails or returns no usable data.
    """
    if not in_uk(lat, lon):
        raise ValueError(
            f"Location {lat:.3f}, {lon:.3f} is outside the UK. The UK model's crops "
            "and agronomy rules only apply to UK fields."
        )
    weather = _clean_daily(lat, lon)
    farm = _summarize(weather)
    return farm, weather
