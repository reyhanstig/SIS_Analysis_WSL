# Incident Report: Misclassified Tokyo Bay Station in Ise-Mikawa Bay Results

## Issue Description
During the PCA and decorrelation scale analysis (Steps 3 and 4) for Ise-Mikawa Bay, it was discovered that one station geographically located in Tokyo Bay was mistakenly included in the Ise-Mikawa Bay dataset.

## Root Cause Analysis
- **Station Involved:** `00001352` (Tokyo Bay)
- **Data Source Issue:** In the raw environmental shapefile data for the year **2022**, this station was erroneously assigned the `watercode` `200`, which corresponds to Ise Bay. 
- **Processing Impact:** The project's data loading pipeline (`utils/data_loader.py`) aggregates station information across all years. Because of the 2022 anomaly, the station acquired the `watermass_name` "Ise Bay" during the merge with the water mass dictionary. When the PCA analysis scripts queried the unique stations for Ise-Mikawa Bay, this station was inadvertently included in the bay's station list.

## Resolution
1. **Data Pipeline Hotfix:** A specific override was added to `clean_and_process_data` in `utils/data_loader.py`. The rule strictly forces the `watercode` for `zettaicode` `00001352` to `100` (Tokyo Bay) before merging with the watermass dictionary.
2. **Data Regeneration:** The central `merged_gdf.feather` file was forcibly regenerated via `load_and_process_data(force_reload=True)` to apply the correction globally.
3. **Re-analysis:** The following scripts were re-run for "Ise-Mikawa Bay" to refresh the datasets and figures without the misclassified station:
   - `40_calculate_decorrelation_scale_per_bay.py` (Step 3)
   - `21_calculate_pca_explained_variance_per_bay.py` (Step 4)
   - `22_plot_pca_timeseries_per_bay.py` (Step 4)
   - `23_plot_pca_eof_map_per_bay.py` (Step 4)

## Status
**Resolved.** The generated EOF maps, variance metrics, and timeseries plots for Ise-Mikawa Bay are now strictly scoped to the correct stations.
