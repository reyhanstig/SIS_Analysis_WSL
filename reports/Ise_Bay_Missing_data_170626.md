# Ise Bay Missing Data Investigation Report

**Date:** 2026-06-17

## Issue Description
During analysis of hypoxia frequency trends (`55_hypoxia_frequency_trend_v2.ipynb`), it was observed that Ise Bay plots lacked data after the year 2012. Up until 2012, Ise Bay consistently maintained around 264 environmental sampling points per year, but completely disappeared from subsequent years in the processed data.

## Root Cause Analysis
An investigation into the raw shapefiles within `data/raw/environmental_data/` revealed that spatial data for Ise Bay **did exist** up to 2023 (e.g., `2013_Ise_wq-raw`, `2023_Ise_wq-raw`). The data was not missing from the source; rather, it was being silently dropped during the data integration pipeline.

The root cause was traced to a metadata mismatch in `scripts/data_loader.py`:
1. The pipeline joins raw shapefiles with `water_manual.xls` to assign human-readable region names (e.g., mapping code `200` to `Ise Bay`).
2. Prior to 2013, the raw shapefiles strictly used `watercode = 200` for Ise Bay.
3. Starting precisely in 2013, the structure of the Ise Bay raw shapefiles changed. The `watercode` values were split into sub-codes `201` and `202` (likely delineating Ise Bay from Mikawa Bay internally).
4. Because the codes `201` and `202` do not exist in the project's `water_manual.xls` dictionary, the SQL-like merge operation yielded `NaN` for the `watermass_name` column for these 264 points every year.
5. Consequently, any subsequent downstream notebook that filtered for `Ise Bay` silently excluded the entire 2013-2023 dataset.

*(Note: A similarly documented issue exists for Osaka Bay where a specific CSV dataset genuinely ended in 2012, as noted in `reports/Osaka_Bay_dataset_070626.md`. This coincidence initially obscured the true metadata issue for Ise Bay).*

## Resolution
A hotfix was deployed directly into the `clean_and_process_data` logic within `scripts/data_loader.py`. 

Before merging the dictionaries:
```python
merged_gdf['watercode'] = merged_gdf['watercode'].replace({201: 200, 202: 200})
```
This forces the newer sub-codes (`201`, `202`) to map back to the primary parent code (`200`), successfully mapping them to `Ise Bay` in the final feather file.

## Verification
An automated data rebuild (`force_reload=True`) was triggered. A secondary verification script confirmed that `Ise Bay` is now explicitly labeled and fully populated with its ~264 annual data points continuously up to 2023.
