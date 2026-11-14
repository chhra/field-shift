
from pathlib import Path
import requests
import pandas as pd

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent

RAW_DIR = PROJECT_ROOT / "data" / "raw" / "ecocrop"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "ecocrop"

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# EcoCrop dataset snapshot
URL = (
    "https://digital-atlas.s3.amazonaws.com/"
    "cdh/data/ecocrop/ecocrop.parquet"
)

PARQUET_PATH = RAW_DIR / "ecocrop.parquet"
CSV_PATH = RAW_DIR / "ecocrop.csv"

print("Downloading FAO EcoCrop dataset...")

response = requests.get(URL, timeout=120)
response.raise_for_status()

PARQUET_PATH.write_bytes(response.content)

print(f"Downloaded: {PARQUET_PATH}")
print(f"File size: {PARQUET_PATH.stat().st_size:,} bytes")

# Load dataset
df = pd.read_parquet(PARQUET_PATH)

# Save a CSV copy for easier inspection
df.to_csv(CSV_PATH, index=False)

print("\nDownload completed successfully!")
print(f"Number of species: {len(df)}")
print(f"Number of columns: {len(df.columns)}")

print("\nAvailable columns:")
for column in df.columns:
    print(f"- {column}")

print("\nFirst 5 records:")
print(df.head().to_string())

print("\nMissing values (top 20 columns):")
print(df.isna().sum().sort_values(ascending=False).head(20))

print("\nSaved files:")
print(PARQUET_PATH)
print(CSV_PATH)
