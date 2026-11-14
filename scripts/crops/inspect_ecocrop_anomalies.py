
import pandas as pd

from pathlib import Path
import pandas as pd

# Find the project root directory
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Build the dataset path
DATA_PATH = PROJECT_ROOT / "data" / "raw" / "ecocrop" / "ecocrop.csv"

# Load original dataset
df = pd.read_csv(DATA_PATH)

print(f"Loaded dataset from: {DATA_PATH}")
print(f"Rows: {len(df)}")

columns = [
    "ecoportcode",
    "scientificname",
    "topmn", "topmx",
    "tmin", "tmax",
    "ropmn", "ropmx",
    "rmin", "rmax",
    "latopmn", "latopmx",
    "latmn", "latmx",
    "gmin", "gmax"
]

checks = {
    "Temperature optimal range": (
        df["topmn"].notna() & df["topmx"].notna()
        & (df["topmn"] > df["topmx"])
    ),
    "Rainfall optimal range": (
        df["ropmn"].notna() & df["ropmx"].notna()
        & (df["ropmn"] > df["ropmx"])
    ),
    "Growing cycle range": (
        df["gmin"].notna() & df["gmax"].notna()
        & (df["gmin"] > df["gmax"])
    ),
    "Latitude outside -90 to 90": (
        df[["latopmn", "latopmx", "latmn", "latmx"]]
        .abs().gt(90).any(axis=1)
    ),
    "Unusually high optimal minimum temperature": (
        df["topmn"] > 60
    )
}

for name, mask in checks.items():
    print("\n" + "=" * 65)
    print(name)
    print("=" * 65)

    result = df.loc[mask, columns]

    if result.empty:
        print("No records found.")
    else:
        print(result.to_string(index=False))

print("\nInspection complete. Original data was not modified.")


# Build a separate anomaly review report.
# The original EcoCrop dataset remains unchanged.

issue_flags = pd.DataFrame(checks)

flagged_mask = issue_flags.any(axis=1)

anomaly_review = df.loc[flagged_mask].copy()

anomaly_review.insert(
    0,
    "quality_flags",
    issue_flags.loc[flagged_mask].apply(
        lambda row: "; ".join(row.index[row].tolist()),
        axis=1
    )
)

output_dir = PROJECT_ROOT / "data" / "processed" / "ecocrop"
output_dir.mkdir(parents=True, exist_ok=True)

output_path = output_dir / "ecocrop_anomaly_review.csv"

anomaly_review.to_csv(output_path, index=False)

print("\n" + "=" * 65)
print("ANOMALY REVIEW REPORT")
print("=" * 65)
print(f"Flagged records: {len(anomaly_review)}")
print(f"Saved to: {output_path}")
print("Original dataset was not modified.")