import pandas as pd

path = "data/raw/ecocrop/ecocrop.csv"
df = pd.read_csv(path)

print("=" * 55)
print("ECOCROP DATA QUALITY PROFILE")
print("=" * 55)

print("\n1. DATASET")
print("Rows:", len(df))
print("Columns:", len(df.columns))
print("Numeric columns:", len(df.select_dtypes(include="number").columns))
print("Text columns:", len(df.select_dtypes(include="object").columns))

print("\n2. MISSING VALUES")
missing = pd.DataFrame({
     "missing_count": df.isna().sum(),
     "missing_percent": (df.isna().mean() * 100).round(2)
})
print(missing[missing["missing_count"] > 0].to_string())

print("\n3. DUPLICATES")
print("Duplicate rows:", df.duplicated().sum())
print("Duplicate ecoportcodes:", df["ecoportcode"].duplicated().sum())
print("Duplicate scientific names:", df["scientificname"].duplicated().sum())

print("\n4. NUMERIC SUMMARY")
print(df.describe().T.to_string())

print("\n5. MULTI-VALUE TEXT FIELDS")
for col in df.select_dtypes(include="object").columns:
     sample = df[col].dropna().astype(str)
     multi = sample.str.contains(r"\[.*\]", regex=True).sum()
     if multi:
         print(f"{col}: {multi} records look like serialized lists")

print("\n6. POSSIBLE RANGE ISSUES")
checks = [
     ("topmn > topmx", "topmn", "topmx"),
     ("tmin > tmax", "tmin", "tmax"),
     ("ropmn > ropmx", "ropmn", "ropmx"),
     ("rmin > rmax", "rmin", "rmax"),
     ("phopmn > phopmx", "phopmn", "phopmx"),
     ("phmin > phmax", "phmin", "phmax"),
     ("gmin > gmax", "gmin", "gmax"),
]

for label, lower, upper in checks:
     invalid = df[lower].notna() & df[upper].notna() & (df[lower] > df[upper])
     print(f"{label}: {invalid.sum()}")

print("\n7. LATITUDE OUTSIDE VALID GEOGRAPHIC RANGE")
for col in ["latopmn", "latopmx", "latmn", "latmx"]:
     invalid = df[col].notna() & (df[col].abs() > 90)
     print(f"{col}: {invalid.sum()}")

print("\nPROFILE COMPLETE")
