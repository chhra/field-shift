
from pathlib import Path
import pandas as pd

# ==========================================
# 1. Project paths
# ==========================================

ROOT = Path(__file__).resolve().parent

INPUT_FILE = (
    ROOT / "data" / "raw" /
    "nasa_power_peartree_2000_2026.csv"
)

OUTPUT_DIR = ROOT / "data" / "processed"
OUTPUT_FILE = OUTPUT_DIR / "nasa_power_clean.csv"
REPORT_FILE = OUTPUT_DIR / "nasa_power_quality_report.txt"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ==========================================
# 2. Load data
# ==========================================

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Input file not found: {INPUT_FILE}\n"
        "Check the filename and location."
    )

df = pd.read_csv(INPUT_FILE)

print("Original dataset loaded.")
print("Rows:", len(df))
print("Columns:", list(df.columns))

# Normalize column names
df.columns = df.columns.str.strip().str.lower()

# Expected columns
required_columns = [
    "date",
    "latitude",
    "longitude",
    "t2m",
    "t2m_max",
    "t2m_min",
    "prectotcorr",
    "rh2m",
]

missing_columns = [
    col for col in required_columns
    if col not in df.columns
]

if missing_columns:
    raise ValueError(
        f"Missing required columns: {missing_columns}"
    )

# ==========================================
# 3. Clean dates
# ==========================================

df["date"] = pd.to_datetime(
    df["date"],
    errors="coerce"
)

invalid_dates = int(df["date"].isna().sum())

# Remove rows without a valid date
df = df.dropna(subset=["date"]).copy()

# ==========================================
# 4. Convert climate columns to numeric
# ==========================================

numeric_columns = [
    "latitude",
    "longitude",
    "t2m",
    "t2m_max",
    "t2m_min",
    "prectotcorr",
    "rh2m",
]

for col in numeric_columns:
    df[col] = pd.to_numeric(
        df[col],
        errors="coerce"
    )

# ==========================================
# 5. Handle NASA POWER missing values
# ==========================================

# NASA POWER commonly uses -999 for missing data.
df[numeric_columns] = df[numeric_columns].replace(
    [-999, -999.0],
    float("nan")
)

# ==========================================
# 6. Validate climate values
# ==========================================

invalid_counts = {}

# Temperature sanity checks (degrees Celsius)
temperature_columns = [
    "t2m",
    "t2m_max",
    "t2m_min",
]

for col in temperature_columns:
    invalid = (
        (df[col] < -90) |
        (df[col] > 60)
    )

    invalid_counts[col] = int(invalid.sum())
    df.loc[invalid, col] = float("nan")

# Relative humidity must be between 0 and 100
invalid_rh = (
    (df["rh2m"] < 0) |
    (df["rh2m"] > 100)
)

invalid_counts["rh2m"] = int(invalid_rh.sum())

df.loc[invalid_rh, "rh2m"] = float("nan")

# Precipitation cannot be negative
invalid_rain = df["prectotcorr"] < 0

invalid_counts["prectotcorr"] = int(invalid_rain.sum())

df.loc[invalid_rain, "prectotcorr"] = float("nan")

# Check consistency between daily minimum and maximum
invalid_temp_range = (
    df["t2m_min"].notna() &
    df["t2m_max"].notna() &
    (df["t2m_min"] > df["t2m_max"])
)

invalid_counts["tmin_greater_than_tmax"] = int(
    invalid_temp_range.sum()
)

# If minimum > maximum, invalidate all three temperature values
df.loc[
    invalid_temp_range,
    temperature_columns
] = float("nan")

# Mean temperature should be between minimum and maximum
invalid_mean = (
    df["t2m"].notna() &
    df["t2m_min"].notna() &
    df["t2m_max"].notna() &
    (
        (df["t2m"] < df["t2m_min"]) |
        (df["t2m"] > df["t2m_max"])
    )
)

invalid_counts["t2m_outside_daily_range"] = int(
    invalid_mean.sum()
)

df.loc[invalid_mean, "t2m"] = float("nan")

# ==========================================
# 7. Remove duplicate observations
# ==========================================

before_duplicates = len(df)

# Include coordinates in the key so that observations
# from different locations are not merged.
duplicate_keys = ["date", "latitude", "longitude"]

df = df.drop_duplicates(
    subset=duplicate_keys,
    keep="last"
)

duplicates_removed = before_duplicates - len(df)

# ==========================================
# 8. Sort data
# ==========================================

df = df.sort_values(
    ["date", "latitude", "longitude"]
).reset_index(drop=True)

# ==========================================
# 9. Missing values report
# ==========================================

missing_values = df[required_columns].isna().sum()

missing_percentages = (
    df[required_columns].isna().mean() * 100
).round(2)

# ==========================================
# 10. Check date coverage
# ==========================================

if not df.empty:
    start_date = df["date"].min()
    end_date = df["date"].max()

    expected_days = (
        end_date - start_date
    ).days + 1

    # This check assumes one location.
    locations = df[
        ["latitude", "longitude"]
    ].drop_duplicates()

    if len(locations) == 1:
        observed_days = df["date"].nunique()
        missing_days = expected_days - observed_days
    else:
        observed_days = None
        missing_days = None
else:
    start_date = None
    end_date = None
    expected_days = 0
    observed_days = None
    missing_days = None

# ==========================================
# 11. Save cleaned data
# ==========================================

df.to_csv(
    OUTPUT_FILE,
    index=False,
    date_format="%Y-%m-%d"
)

# ==========================================
# 12. Create quality report
# ==========================================

report = []

report.append("NASA POWER DATA QUALITY REPORT")
report.append("=" * 45)

report.append(f"Original rows: {len(pd.read_csv(INPUT_FILE))}")
report.append(f"Cleaned rows: {len(df)}")
report.append(f"Duplicates removed: {duplicates_removed}")
report.append(f"Invalid dates removed: {invalid_dates}")

report.append(f"Start date: {start_date}")
report.append(f"End date: {end_date}")

report.append(f"Expected daily observations: {expected_days}")
report.append(f"Observed daily observations: {observed_days}")
report.append(f"Missing calendar days: {missing_days}")

report.append("\nInvalid values converted to missing:")
for col, count in invalid_counts.items():
    report.append(f"{col}: {count}")

report.append("\nMissing values by column:")
for col in required_columns:
    report.append(
        f"{col}: {missing_values[col]} "
        f"({missing_percentages[col]}%)"
    )

report.append("\nFinal dataset information:")
report.append(df[required_columns].describe().to_string())

REPORT_FILE.write_text(
    "\n".join(report),
    encoding="utf-8"
)

# ==========================================
# 13. Display results
# ==========================================

print("\nCleaning completed!")
print("Cleaned rows:", len(df))
print("Duplicates removed:", duplicates_removed)

print("\nMissing values:")
print(missing_values)

print("\nSaved files:")
print(OUTPUT_FILE)
print(REPORT_FILE)
