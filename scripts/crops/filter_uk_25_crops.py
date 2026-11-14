
from pathlib import Path
import pandas as pd
import ast
import re

# Run from the project root
INPUT = Path("data/raw/ecocrop/ecocrop.csv")
OUTPUT = Path("data/processed/ecocrop_uk_25_crops.csv")
REPORT = Path("data/processed/ecocrop_uk_25_matching_report.csv")

# The 25 selected UK crop entries
crops = [
    ("Winter wheat", "Triticum aestivum", "Cereal", "Winter"),
    ("Winter barley", "Hordeum vulgare", "Cereal", "Winter"),
    ("Spring barley", "Hordeum vulgare", "Cereal", "Spring"),
    ("Spring oats", "Avena sativa", "Cereal", "Spring"),
    ("Maize", "Zea mays", "Cereal", "Spring/Summer"),
    ("Winter field beans", "Vicia faba", "Legume", "Winter"),
    ("Spring peas", "Pisum sativum", "Legume", "Spring"),
    ("Winter oilseed rape", "Brassica napus", "Oilseed", "Winter"),
    ("Potatoes", "Solanum tuberosum", "Vegetable", "Spring"),
    ("Sugar beet", "Beta vulgaris var. saccharifera", "Root crop", "Spring"),
    ("Grass ley (ryegrass)", "Lolium perenne", "Forage", "Perennial"),
    ("Red clover ley", "Trifolium pratense", "Forage", "Perennial"),
    ("Rye", "Secale cereale", "Cereal", "Winter"),
    ("Triticale", "× Triticosecale", "Cereal", "Winter"),
    ("Spring field beans", "Vicia faba", "Legume", "Spring"),
    ("Winter peas", "Pisum sativum", "Legume", "Winter"),
    ("Carrots", "Daucus carota", "Vegetable", "Spring"),
    ("Onions", "Allium cepa", "Vegetable", "Spring"),
    ("Cabbage", "Brassica oleracea", "Vegetable", "Spring"),
    ("Broccoli", "Brassica oleracea var. italica", "Vegetable", "Spring"),
    ("Lettuce", "Lactuca sativa", "Vegetable", "Spring"),
    ("Strawberries", "Fragaria × ananassa", "Fruit", "Perennial"),
    ("Apples", "Malus domestica", "Fruit", "Perennial"),
    ("Raspberries", "Rubus idaeus", "Fruit", "Perennial"),
    ("Field mustard", "Brassica juncea", "Oilseed", "Spring"),
]

# Known taxonomic alternatives for matching.
# These are candidates for review, not automatic proof of equivalence.
aliases = {
    "Beta vulgaris var. saccharifera": ["Beta vulgaris"],
    "Brassica oleracea var. italica": ["Brassica oleracea"],
}

def normalise(value):
    if pd.isna(value):
        return ""
    value = str(value).strip().lower()
    value = value.replace("×", "x")
    value = re.sub(r"\s+", " ", value)
    return value

def parse_list(value):
    """Read EcoCrop synonym/common-name list fields safely."""
    if pd.isna(value):
        return []
    try:
        parsed = ast.literal_eval(str(value))
        if isinstance(parsed, list):
            return [normalise(x) for x in parsed]
    except (ValueError, SyntaxError):
        pass
    return [normalise(value)]

if not INPUT.exists():
    raise FileNotFoundError(f"Input file not found: {INPUT}")

df = pd.read_csv(INPUT, dtype=str, keep_default_na=True)
df.columns = [c.strip() for c in df.columns]

required = {"scientificname", "syno"}
missing_columns = required - set(df.columns)
if missing_columns:
    raise ValueError(f"Missing required columns: {missing_columns}")

df["_scientific_normalised"] = df["scientificname"].apply(normalise)
df["_synonyms"] = df["syno"].apply(parse_list)

results = []
report = []

for crop_name,  scientific, crop_type, season in crops:
    candidates = [scientific] + aliases.get(scientific, [])
    candidate_keys = {normalise(x) for x in candidates}

    # Prefer exact scientific-name matches.
    exact = df[df["_scientific_normalised"].isin(candidate_keys)].copy()

    if not exact.empty:
        matches = exact
        match_type = (
            "Exact" if normalise(scientific) in set(exact["_scientific_normalised"])
            else "Taxonomic alternative - review"
        )
    else:
        # Search the synonym field if no exact match exists.
        synonym_mask = df["_synonyms"].apply(
            lambda values: bool(candidate_keys.intersection(values))
        )
        matches = df[synonym_mask].copy()
        match_type = "Synonym - review" if not matches.empty else "Missing"

    report.append({
        "crop_name": crop_name,
        "scientific_name_requested": scientific,
        "match_type": match_type,
        "matching_ecocrop_records": len(matches),
        "matched_scientific_names": (
            "; ".join(matches["scientificname"].dropna().unique())
            if not matches.empty else ""
        )
    })

    # Keep one output row per selected crop entry.
    # If multiple EcoCrop records match, select the first and report
    # the count above so it can be reviewed.
    if matches.empty:
        eco_record = {col: pd.NA for col in df.columns
                      if not col.startswith("_")}
    else:
        eco_record = matches.iloc[0].drop(
            labels=["_scientific_normalised", "_synonyms"]
        ).to_dict()

    results.append({
        "crop_name": crop_name,
        "target_scientific_name": scientific,
        "crop_type": crop_type,
        "season": season,
        "ecocrop_match_status": match_type,
        **eco_record
    })

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

result_df = pd.DataFrame(results)
report_df = pd.DataFrame(report)

result_df.to_csv(OUTPUT, index=False, encoding="utf-8-sig")
report_df.to_csv(REPORT, index=False, encoding="utf-8-sig")

print("\n========== FILTERING SUMMARY ==========")
print("Selected crop entries:", len(crops))
print("Output rows:", len(result_df))
print("Exact matches:", (report_df["match_type"] == "Exact").sum())
print("Synonym matches:", (report_df["match_type"] == "Synonym - review").sum())
print("Taxonomic alternatives:", (
    report_df["match_type"] == "Taxonomic alternative - review"
).sum())
print("Missing:", (report_df["match_type"] == "Missing").sum())

print("\n========== MATCHING REPORT ==========")
print(report_df.to_string(index=False))

print("\nCreated:")
print(OUTPUT)
print(REPORT)
