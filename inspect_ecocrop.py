
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
file = ROOT / "data" / "raw" / "ecocrop" / "ecocrop.csv"

df = pd.read_csv(file)

# Inspect one crop
crop = df[df["scientificname"].str.contains(
    "Abelmoschus esculentus",
    case=False,
    na=False
)]

print("Number of records:", len(df))
print("\nOkra record:")
print(crop.to_string(index=False))

# Inspect numerical ranges
print("\nNumerical column statistics:")
print(df.describe(include="all").T.to_string())

# Missing values
print("\nMissing values:")
print(df.isna().sum().sort_values(ascending=False).to_string())
