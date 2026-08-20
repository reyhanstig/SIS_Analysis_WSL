# Incident Report: Sub-optimal Zoom Bounds and Distorted Aspect Ratios in Subdivision Maps

## Issue Description
During the pipeline generation of maps for individual bays and subdivisions (Steps 2-6), it was observed that the cartopy maps often displayed excessive empty padding around smaller bays. In some cases, the maps were extremely zoomed out, making the data for targeted bays appear very small. Furthermore, spatial aspect ratios were incorrectly handled, leading to distorted geographical shapes.

## Root Cause Analysis
- **Fixed Padding vs Proportional Bounds:** The mapping logic originally applied a fixed latitude/longitude buffer (e.g. `0.2` degrees) to all regions. While this fixed padding was appropriate for the entire Seto Inland Sea mapping standard, it caused significant problems for much smaller bays like Tokyo Bay, which resulted in maps dominated by empty background space.
- **Cartopy Aspect Ratio Limitations:** When rendering spatial projections, `cartopy` inherently enforces a spherical aspect ratio. However, specifying a Cartesian matplotlib `figsize` that did not precisely match the spherical bounding box resulted in Cartopy adding significant empty margins inside the figure to preserve the map projection ratio, creating large white borders.

## Resolution
1. **Dynamic Extent Logic:** The `MappingConfig.get_dynamic_extent()` method was rewritten to calculate a proportional padding of exactly 10-11% relative to the actual latitude/longitude span of each specific dataset bounding box, replacing the hard-coded fixed-degree buffers. A minimum `0.05` padding was retained as a fallback.
2. **Aspect-Ratio-Preserving Figsize:** A new helper `MappingConfig.get_dynamic_figsize()` was introduced. This method uses the center latitude of the map to calculate the correct Cartesian aspect ratio (incorporating a `1 / cos(lat)` correction) and outputs an exact `(width, height)` that flawlessly matches the geographic extent. This completely eliminated the unexpected white-space added by Cartopy.
3. **Global Extent Exclusion:** Added logic to enforce that if the mapping region is the entire "Seto Inland Sea", the proportional buffering is skipped in favor of strictly following the standardized fixed overview bounds defined in `reports/SIS_mapping_standard.md`.
4. **Pipeline Refactor:** The new configuration rules were standardized and applied to all mapping scripts across the pipeline:
   - **Step 2:** `process11_mean_climatological_do_map.py`, `process12_hypoxia_frequency_map.py`, `process13_do_trend_spatial_mapping.py`
   - **Step 3:** `process01_calculate_bay_decorrelation_scales.py`, `process11_calculate_decorrelation_scale_per_bay.py`, `process12_plot_decorrelation_scale_complete.py`, `process03_decorrelation_seasonal.py`
   - **Step 4:** `process03_plot_pca_eof_map_raw.py`, `process13_plot_pca_eof_map_per_bay_raw.py`
   - **Step 5:** `process11_trend_grouping_and_maps.py`, `process41_spatial_correlation_maps.py`
   - **Step 6:** `process01_pc_driver_temporal_analysis.py`
5. **Re-execution:** The pipeline orchestrator `step0_sandbox/68c_run_all_modified_plots.py` was created and executed to dynamically regenerate all maps for all bays and subdivisions across the pipeline. Note: During execution, a path bug referencing an outdated directory (`40_calculate_decorrelation_scale_per_bay`) was identified and hot-fixed to `process11_calculate_decorrelation_scale_per_bay`.

## Status
**Resolved.** All generated pipeline maps now zoom dynamically and proportionally to target subdivisions without geographic distortion or excessive padding, while the global Seto Inland Sea map continues to correctly follow the project standards.
