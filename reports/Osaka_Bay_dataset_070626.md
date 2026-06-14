# Osaka Bay Environmental and Biological Datasets Overview

This report provides a comprehensive overview of the shapes, schemas, temporal coverages, and spatial structures of all available datasets for the Osaka Bay hypoxia and benthic community analysis.

**Date:** June 7, 2026
**Project:** Seto Inland Sea (SIS) Analysis Pipeline

---

## 1. Summary Table of Osaka Bay Datasets

| Dataset Name | File Path | Shape (Rows × Cols) | Temporal Range | Coordinate Format | Key Parameters | Role in Analysis | Limitations / Mismatches |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Water Quality Search Results** | `data/raw/Osaka Bay/検索結果＿大阪湾＿水質.csv` | 17,220 × 40 | 1997 – 2012 (Monthly) | Decimal Degrees (e.g., 134.9006, 34.3455) | **DO**, Temperature, Salinity, pH, Nutrients, COD, Chl-a | Direct mapping of bottom DO and hypoxic zone boundaries | Ended in 2012; does not temporally overlap with the new biological CSV |
| **Biological Search Results** | `data/raw/Osaka Bay/検索結果＿大阪湾＿生物.csv` | 180 × 24 | 1982 – 1983 (Seasonal) | Decimal Degrees (e.g., 135.2375, 34.6782) | Species count, abundance, biomass, top 5 dominant species | Analysis of community structure and indicator species shifts | Ended in 1983; must be linked to water quality via climatological baselines |
| **Bottom Sediment Quality** | `data/raw/benthos_data/bottom_2023.xlsx` | 132 × 51 (Osaka subset) | 1991 – 2024 (Semi-annual) | Degrees-Minutes-Seconds (DMS) conversion | TOC, ORP (redox), Sulfides, COD, Clay, Depth | Tracks sediment oxygen demand and inputs to Random Forest model | Coordinates require DMS to decimal conversion |
| **Macrobenthos Database** | `data/raw/benthos_data/benthos_2023.xlsx` | 68 × 254 (Osaka subset) | 1991 – 2024 (Semi-annual) | Lookup from sediment data | 62 species occurrences, abundance, wet weight | Decadal benthos community tracking; directly overlaps WQ CSV | Wide columns (62 species) with shifting cell errors |
| **Fixed-line Survey Osaka** | `data/raw/Fixed_line_survey/fixed_line_survey_long_osaka.csv` | 1,143 × 5 | 2016 (Monthly) | Linked via `station_meta.csv` | Temperature, Salinity, Depth (profiles) | Physical water column stratification characterization | Lacks direct DO measurements; relies on thermocline proxy |
| **Merged Water Quality GDF** | `data/processed/merged_gdf.feather` | 3,440 × 68 (Osaka subset) | 1981 – 2024 (Seasonal) | Decimal Degrees (GDM2000, EPSG:4742) | **DO** (surface/bottom), Temp, Salinity, Density, Stratification, Nutrients | Multi-decadal baseline for both WQ and benthos | Limited to 10 fixed monitoring stations |

---

## 2. Detailed Dataset Profiles

### A. Water Quality Survey (`検索結果＿大阪湾＿水質.csv`)
* **Shape:** 17,220 rows × 40 columns.
* **Encoding:** `cp932` (Shift_JIS).
* **Metadata Columns:** Survey Name (`調査名称`), Station Name (`地点名称`), coordinates (`経度`/`緯度`), date (`調査年月日` in `YYYY/MM/DD`), and total depth (`全水深`).
* **Sampling Depth & Layers:** Sampling Layer (`採取層` - e.g., `上層` (surface), `中層` (middle), `下層` (bottom)) and sampling depth (`採取水深`).
* **Parameters and V2 Column Upgrades:**
  - Includes: Dissolved Oxygen (DO), Water Temperature, Salinity, pH, Turbidity, SS, COD, Nutrients (T-N, T-P, NO2-N, NO3-N, NH4-N, PO4-P), and Chlorophyll-a.
  - **V2 Columns (Dual-Column Pattern):** Several parameters exist in dual columns: a primary column (e.g., `do_`, `salt`, `ph`, `chlorophyl`) and a secondary "V2" column ending in `2` or `_1` (e.g., `do_2`, `salt2`, `ph2`, `chloroph_1`).
  - **Data Quality Differences:** The primary columns are often stored as string/object arrays containing qualitative flag comments. The V2 columns are natively cast as numeric `float64` and are more complete (e.g., across the complete regional dataset, `do_2` has +377 observations over `do_`, and `chloroph_1` has +706 over `chlorophyl`).
  - **Ingestion Override:** The data loader pipeline in `scripts/data_loader.py` dynamically resolves these. If a V2 column is detected as numeric and has equal or greater completeness than the primary column, the primary column values are overridden by the V2 values during raw data cleaning.
* **Temporal Coverage:** April 2, 1997, to March 13, 2012. Sampling is extremely balanced across all 12 calendar months (~1,400 to 1,460 samples per month).

### B. Biological Survey (`検索結果＿大阪湾＿生物.csv`)
* **Shape:** 180 rows × 24 columns.
* **Encoding:** `cp932` (Shift_JIS).
* **Metadata Columns:** Survey name, coordinates, date, time, and total depth.
* **Biological Metrics:** Species richness (`種類数`), total abundance (`個体数`) in `個体数/0.1m2`, wet biomass weight (`湿重量`) in `g/0.1m2`, and number of dominant species (`主要種数`).
* **Dominant Species Breakdown:** Contains names and counts for the top 5 dominant species, such as opportunistic polychaete species:
  - `ヨツバネスピオ` (*Prionospio pinnata*)
  - `ハナオカカギゴカイ` (*Sigambra tentaculata*)
  - `Lumbrineris Longifolia`
  - `Prionospio cirrifera`
  - `Euchone sp.`
* **Temporal Coverage:** June 2, 1982, to January 22, 1983. Focuses on seasonal snapshots: June, July, August (summer), October (autumn), and January (winter).

### C. Bottom Sediment Quality (`bottom_2023.xlsx` - Osaka subset)
* **Osaka Shape:** 132 rows × 51 columns.
* **Encoding:** standard Excel format, sheet named `底質_累積2023`.
* **Key Features:** Latitude/longitude in DMS format, water depth (`水深`), COD, TN, TP, TOC, and Sulfides (`硫化物`).
* **Temporal Coverage:** 1991 to 2024 (semi-annual surveys in summer and winter).

### D. Macrobenthos Database (`benthos_2023.xlsx` - Osaka subset)
* **Osaka Shape:** 68 rows × 254 columns.
* **Encoding:** standard Excel format, sheet named `底生生物_累積2023`.
* **Key Features:** Wide occurrence-level dataset with up to 62 species' scientific names, common names, counts, and biomass wet weights per row. Requires realignment for shifted rows and parsing of qualitative abundance qualifiers (`+`, `G`).
* **Temporal Coverage:** 1991 to 2024 (semi-annual).

### E. Osaka Fixed-line Survey (`fixed_line_survey_long_osaka.csv`)
* **Shape:** 1,143 rows × 5 columns.
* **Key Features:** Monthly vertical profiles at 20 stations for temperature and salinity. Station coordinates are linked via `station_meta.csv`.
* **Temporal Coverage:** 2016.

### F. Merged Water Quality Geodataframe (`merged_gdf.feather` - Osaka Bay Portion)
* **Shape:** 3,440 rows × 68 columns.
* **Temporal Coverage:** 1981 to 2024. Organized seasonally across four quarters: Winter (Jan/Feb), Spring (May), Summer (Jul/Aug), and Autumn (Oct). Each season contains exactly 860 rows (430 unique sampling dates × 2 depth layers).
* **Spatial Structure:** Comprises 10 fixed monitoring stations in Osaka Bay:
  - 3 Hyogo Prefecture stations: `兵庫県11` (Lat ~34.695, Lon ~135.331), `兵庫県23` (Lat ~34.658, Lon ~135.264), `兵庫県48` (Lat ~34.610, Lon ~135.092)
  - 7 Osaka Prefecture stations: `大阪府2` (Lat ~34.658, Lon ~135.409), `大阪府5` (Lat ~34.556, Lon ~135.412), `大阪府25` (Lat ~34.549, Lon ~135.268), `大阪府37` (Lat ~34.385, Lon ~135.203), `大阪府44` (Lat ~34.440, Lon ~135.137), `大阪府50` (Lat ~34.494, Lon ~135.072), `大阪府58` (Lat ~34.331, Lon ~135.007)
  - Each station contains exactly 344 rows (172 unique dates × 2 layers) spanning 1981–2024.
* **Sampling Depth & Layers:** Segmented by depth layer (`saisuipoin`):
  - `saisuipoin == 1`: Surface layer (typically 0.5m depth). Mean DO = 8.72 mg/L, min = 0.0 mg/L, max = 18.0 mg/L.
  - `saisuipoin == 2`: Bottom layer (typically 1.5–2.0m above sea floor). Mean DO = 6.27 mg/L, min = 0.0 mg/L, max = 11.0 mg/L.
* **Parameters & Calculations:**
  - Water quality measures: Dissolved Oxygen (`do_`), Water Temperature (`wtemp`), Air Temperature (`temp`), Salinity (`salt`), pH (`ph`), Nutrients (`nh4n`, `no2n`, `no3n`, `tn`, `po4p`, `tp`), Chlorophyll-a (`chlorophyl`), TOC (`toc`), and DOC (`doc`).
  - **V2 Column Identity:** Primary columns like `do_`, `salt`, and `ph` are identical to their V2 variants (`do_2`, `salt2`, `ph2`) because the pipeline's ingestion module (`scripts/data_loader.py`) has already run and replaced the primary column values with the superior-quality numeric float64 V2 values.
  - Derived physical metrics: Water Density (`density`), Stratification index (`stratification` - density difference between bottom and surface), and Stratification Gradient (`stratification_gradient`).
* **CRS:** Recorded in metadata as Geographic CRS GDM2000 (EPSG:4742) using decimal degrees.

---

## 3. Scientific Synthesis and Integration Strategy

The temporal mismatch between the new biological survey (**1982–1983**) and the new water quality survey (**1997–2012**) necessitates a structured integration methodology. Three pathways are available:

### Method A: Climatological Mapping (Recommended for the New CSVs)
Because summer bottom-water hypoxia in Osaka Bay is a highly recurring seasonal phenomenon driven by fixed bathymetry and annual thermal stratification, we can:
1. Use either the 1997–2012 water quality dataset or the long-term **`merged_gdf.feather`** dataset (1981–2024) to build a **climatological baseline map of summer bottom DO** in Osaka Bay.
2. Calculate the average historical hypoxic exposure risk at each coordinate.
3. Overlay the 1982–1983 biological station coordinates onto this climatological risk map to analyze if communities sampled in 1982 reflect the climatological hypoxic footprint.

### Method B: Exact Temporal Matching (Using the Broader Benthos Database)
If exact temporal matching (same year and month) is required:
1. Use the Osaka subset of the decadal benthos database (**`benthos_2023.xlsx`**), which runs from **1991 to 2024**.
2. This dataset directly overlaps with the 1997–2012 water quality CSV and the **`merged_gdf.feather`** Osaka subset, allowing us to perform exact spatial-temporal joins (e.g., matching a July 2005 benthos sample with the actual July 2005 bottom DO map).

### Method C: Long-term Stratification & Hypoxia Trend Modeling (Bridging the Gaps)
The **`merged_gdf.feather`** dataset (1981–2024) acts as a perfect temporal bridge between the 1982–1983 biological survey, the 1997–2012 water quality CSV, and the 1991–2024 decadal macrobenthos database:
1. Since the 10 fixed stations in `merged_gdf.feather` have continuous seasonal records from 1981 onwards, we can trace the exact historical progression of bottom hypoxia (`do_` at `saisuipoin == 2`) and physical stratification (`stratification_gradient`) spanning both biological datasets.
2. This allows for validation of whether the 1982–1983 benthic community was sampled during a period of comparable hypoxia intensity to the later decades.
