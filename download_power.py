
from pathlib import Path

import pandas as pd
import requests
import json


# --------------------------------------------------
# 1. Farm reference location
# --------------------------------------------------

# Rothamsted Research, Broadbalk field, Harpenden, Hertfordshire (TL123 136).
# Coordinates: Poulton et al. (Rothamsted repository) 51.8095, -0.3730;
# Geograph 51.809146, -0.373222. Previous location (Pear Tree, Norfolk Fens):
# 52.7045524, 0.2431611 - its files are kept as nasa_power_peartree_*.
LATITUDE = 51.809
LONGITUDE = -0.373

FARM_NAME = "Rothamsted Broadbalk"
FARM_ID = "broadbalk"   # used in the output file names

# Historical period: 2000 to 2026
START_DATE = "20000101"
END_DATE = "20261111"


# --------------------------------------------------
# 2. NASA POWER API configuration
# --------------------------------------------------

BASE_URL = (
    "https://power.larc.nasa.gov/api/temporal/daily/point"
)

PARAMETERS = [
    "T2M",
    "T2M_MAX",
    "T2M_MIN",
    "PRECTOTCORR",
    "RH2M",
]

params = {
    "parameters": ",".join(PARAMETERS),
    "community": "AG",
    "longitude": LONGITUDE,
    "latitude": LATITUDE,
    "start": START_DATE,
    "end": END_DATE,
    "format": "JSON",
    "time-standard": "UTC",
}


# --------------------------------------------------
# 3. Create output directory
# --------------------------------------------------

# built from this file's location, so it works from any folder
output_dir = Path(__file__).resolve().parent / "data" / "raw"
output_dir.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# 4. Request data from NASA POWER
# --------------------------------------------------

print("Requesting data from NASA POWER...")

try:
    response = requests.get(
        BASE_URL,
        params=params,
        timeout=90,
    )

    response.raise_for_status()
    payload = response.json()

except requests.RequestException as error:
    raise SystemExit(f"NASA POWER request failed: {error}")

except ValueError:
    raise SystemExit("NASA POWER returned an invalid JSON response.")


# --------------------------------------------------
# 5. Extract daily parameters
# --------------------------------------------------

parameter_data = (
    payload.get("properties", {})
           .get("parameter")
)

if not parameter_data:
    raise SystemExit(
        "No parameter data found. API response:\n"
        + json.dumps(payload, indent=2)[:3000]
    )

df = pd.DataFrame(parameter_data)

df.index = pd.to_datetime(
    df.index,
    format="%Y%m%d",
)

df.index.name = "date"
df = df.reset_index()

# NASA POWER may use -999 as a missing-data value.
df = df.replace(-999, float("nan"))

# Keep location information in the dataset.
df.insert(1, "latitude", LATITUDE)
df.insert(2, "longitude", LONGITUDE)


# --------------------------------------------------
# 6. Save raw JSON and processed CSV
# --------------------------------------------------

json_path = output_dir / f"nasa_power_{FARM_ID}_2000_2026.json"
csv_path = output_dir / f"nasa_power_{FARM_ID}_2000_2026.csv"

with open(json_path, "w", encoding="utf-8") as file:
    json.dump(payload, file, indent=2)

df.to_csv(csv_path, index=False)


# --------------------------------------------------
# 7. Display results
# --------------------------------------------------

print("\nDownload successful!")

print(f"Farm: {FARM_NAME}")
print(f"Rows: {len(df)}")
print(f"Columns: {list(df.columns)}")

print("\nFirst 5 records:")
print(df.head().to_string(index=False))

print("\nMissing values:")
print(df.isna().sum())

print(f"\nCSV saved to: {csv_path}")
print(f"JSON saved to: {json_path}")
