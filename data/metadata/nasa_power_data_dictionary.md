# NASA POWER Climate Dataset
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
- Start date: 2000-01-01
- End date: 2026-11-11

### Spatial information

- Number of unique locations: 1
- Coordinates are expressed in decimal degrees.

### Quality information

- Total records: 9812
- Missing values: 0
- Duplicate date/location records: 0
- Missing calendar days per location: 0

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
