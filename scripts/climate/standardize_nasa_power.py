
from pathlib import Path
import pandas as pd
import json
import hashlib

# ==========================================
# 1. Project paths
# ==========================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "nasa_power_clean.csv"
)

OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "climate"
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"

PARQUET_FILE = OUTPUT_DIR / "nasa_power.parquet"
DICTIONARY_FILE = METADATA_DIR / "nasa_power_data_dictionary.md"
MANIFEST_FILE = METADATA_DIR / "nasa_power_manifest.json"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
METADATA_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================
# 2. Read original dataset
# ==========================================

if not INPUT_FILE.exists():
    raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

print("Loading original NASA POWER dataset...")

df = pd.read_csv(INPUT_FILE)

original_hash = hashlib.sha256(INPUT_FILE.read_bytes()).hexdigest()

print(f"Original rows: {len(df)}")


# ==========================================
# 3. Standardize column names
# ==========================================

df.columns = (
    df.columns
    .str.strip()
    .str.lower()
)

required_columns = [
    "date",
    "latitude",
    "longitude",
    "t2m",
    "t2m_max",
    "t2m_min",
    "prectotcorr",
    "rh2m"
]

missing_columns = set(required_columns) - set(df.columns)

if missing_columns:
    raise ValueError(
        f"Missing required columns: {missing_columns}"
    )

# Keep only the defined dataset schema.
df = df[required_columns].copy()


# ==========================================
# 4. Standardize data types
# ==========================================

df["date"] = pd.to_datetime(
    df["date"],
    errors="raise"
)

numeric_columns = [
    "latitude",
    "longitude",
    "t2m",
    "t2m_max",
    "t2m_min",
    "prectotcorr",
    "rh2m"
]

for column in numeric_columns:
    df[column] = pd.to_numeric(
        df[column],
        errors="raise"
    )

# Use float64 for numeric measurements.
for column in numeric_columns:
    df[column] = df[column].astype("float64")


# ==========================================
# 5. Validate dataset
# ==========================================

if df.isnull().any().any():
    raise ValueError(
        "Missing values detected. Resolve them before export."
    )

if df.duplicated(
    subset=["date", "latitude", "longitude"]
).any():
    raise ValueError(
        "Duplicate date/location records detected."
    )

if (df["prectotcorr"] < 0).any():
    raise ValueError("Negative precipitation detected.")

if not df["rh2m"].between(0, 100).all():
    raise ValueError("Humidity outside 0-100% range.")

if (df["t2m_min"] > df["t2m_max"]).any():
    raise ValueError("Minimum temperature exceeds maximum.")

if not (
    df["t2m_min"] <= df["t2m"]
).all() or not (
    df["t2m"] <= df["t2m_max"]
).all():
    raise ValueError("Mean temperature outside daily range.")

# Sort records consistently.
df = df.sort_values(
    ["latitude", "longitude", "date"]
).reset_index(drop=True)


# ==========================================
# 6. Export Parquet
# ==========================================

print("Exporting Parquet dataset...")

df.to_parquet(
    PARQUET_FILE,
    engine="pyarrow",
    index=False,
    compression="snappy"
)

# Read it back to verify the exported file.
check_df = pd.read_parquet(PARQUET_FILE)

if not df.equals(check_df):
    raise ValueError("Parquet round-trip validation failed.")

print("Parquet export and verification successful.")


# ==========================================
# 7. Calculate metadata
# ==========================================

locations = (
    df[["latitude", "longitude"]]
    .drop_duplicates()
    .to_dict(orient="records")
)

expected_days = (
    df["date"].max() - df["date"].min()
).days + 1

missing_days_by_location = {}

for (lat, lon), group in df.groupby(
    ["latitude", "longitude"]
):
    expected = pd.date_range(
        group["date"].min(),
        group["date"].max(),
        freq="D"
    )

    missing = expected.difference(group["date"])

    missing_days_by_location[f"{lat},{lon}"] = len(missing)

manifest = {
    "dataset_name": "NASA POWER Climate Dataset",
    "dataset_version": "1.0",
    "source": "NASA POWER",
    "source_file": str(INPUT_FILE.relative_to(PROJECT_ROOT)),
    "output_file": str(PARQUET_FILE.relative_to(PROJECT_ROOT)),
    "format": "Parquet",
    "compression": "Snappy",
    "created_by": "FieldShift Data Preparation Pipeline",
    "temporal_resolution": "Daily",
    "start_date": str(df["date"].min().date()),
    "end_date": str(df["date"].max().date()),
    "expected_calendar_days_per_location": expected_days,
    "total_rows": len(df),
    "number_of_locations": len(locations),
    "locations": locations,
    "missing_values": int(df.isnull().sum().sum()),
    "duplicate_records": int(
        df.duplicated(
            subset=["date", "latitude", "longitude"]
        ).sum()
    ),
    "missing_days_by_location": missing_days_by_location,
    "columns": list(df.columns),
    "input_sha256": original_hash,
    "verified_parquet_round_trip": True
}

with open(MANIFEST_FILE, "w", encoding="utf-8") as file:
    json.dump(
        manifest,
        file,
        indent=4,
        ensure_ascii=False
    )


# ==========================================
# 8. Create Data Dictionary
# ==========================================

dictionary = """# NASA POWER Climate Dataset
## Data Dictionary

### Dataset description

This dataset contains daily climate observations
retrieved from NASA POWER and cleaned by FieldShift.

### Columns

| Column | Data type | Unit | Description |
|---|---|---|---|
| date | datetime | YYYY-MM-DD | Observation date |
| latitude | float64 | decimal degrees | Latitude of the location |
| longitude | float64 | decimal degrees | Longitude of the location |
| t2m | float64 | degrees Celsius | Daily mean temperature at 2 metres |
| t2m_max | float64 | degrees Celsius | Daily maximum temperature at 2 metres |
| t2m_min | float64 | degrees Celsius | Daily minimum temperature at 2 metres |
| prectotcorr | float64 | mm/day | Corrected total precipitation |
| rh2m | float64 | percent | Relative humidity at 2 metres |

### Temporal information

- Temporal resolution: Daily
- Start date: {start_date}
- End date: {end_date}

### Spatial information

- Number of unique locations: {location_count}
- Coordinates are expressed in decimal degrees.

### Quality information

- Total records: {rows}
- Missing values: {missing}
- Duplicate date/location records: {duplicates}
- Missing calendar days per location: {missing_days}

### Provenance

- Source: NASA POWER
- Original input: data/processed/nasa_power_clean.csv
- Output: data/processed/climate/nasa_power.parquet
- Processing: FieldShift standardization script

### Important limitations

This dataset represents the downloaded NASA POWER
location and period only. It does not represent
global climate coverage.

NASA POWER grid resolution and parameter definitions
should be documented from the exact product/API metadata
used for the original download.
"""

dictionary = dictionary.format(
    start_date=df["date"].min().date(),
    end_date=df["date"].max().date(),
    location_count=len(locations),
    rows=len(df),
    missing=int(df.isnull().sum().sum()),
    duplicates=int(
        df.duplicated(
            subset=["date", "latitude", "longitude"]
        ).sum()
    ),
    missing_days=sum(missing_days_by_location.values())
)

DICTIONARY_FILE.write_text(
    dictionary,
    encoding="utf-8"
)


# ==========================================
# 9. Verify original file was not modified
# ==========================================

final_hash = hashlib.sha256(INPUT_FILE.read_bytes()).hexdigest()

if original_hash != final_hash:
    raise RuntimeError("Original CSV file has changed!")

print("\n===================================")
print("NASA POWER STANDARDIZATION COMPLETE")
print("===================================")
print(f"Rows: {len(df)}")
print(f"Locations: {len(locations)}")
print(f"Date range: {df['date'].min()} to {df['date'].max()}")
print(f"Parquet: {PARQUET_FILE}")
print(f"Data Dictionary: {DICTIONARY_FILE}")
print(f"Manifest: {MANIFEST_FILE}")
print("Original CSV unchanged: YES")
print("Parquet verification: PASSED")
