# Incident Report: Inconsistent Station Point Sizes in Dynamically Zoomed Maps

## Issue Description
Following the implementation of dynamic map extents, the sizes of station circle markers became visually inconsistent across different regions. While absolute point sizes remained constant in the code, the tighter zoom applied to smaller regions (e.g., Tokyo Bay and Ise-Mikawa Bay) caused the geographic map elements to render much larger. This disparity made the station points appear inappropriately small relative to the map scale when compared to the global Seto Inland Sea maps.

## Root Cause Analysis
- **Absolute Point Sizing:** Matplotlib's `scatter` method defines marker sizes in absolute units (points squared). These sizes are independent of the geographic map scale.
- **Relativity to Map Zoom:** Because the prior mapping fix dynamically changed bounding boxes and aspect ratios to zoom closely into target bays, the underlying cartesian coordinate space scaled up on the screen. Since the static scatter sizes did not scale along with the geographic map elements, it led to a disparity in visual weighting between wide-extent maps and small-extent maps.

## Resolution
1. **Zoom Factor Calculation:** Introduced a dynamic `zoom_factor` metric in the plotting scripts. This factor is calculated relative to a baseline region extent (approximately 4.5 degrees wide, the width of the Seto Inland Sea). `zoom_factor = max(4.5 / extent_width, 1.0)`.
2. **Proportional Sizing:** The absolute size parameters for the scatter plots were multiplied by this `zoom_factor`. This logic ensures the circle markers appropriately scale up as the geographic map zooms in on smaller areas.
3. **Pipeline Refactor:** The scaling factor logic was successfully retrofitted to all relevant scripts containing `ax.scatter` spatial mappings:
   - **Step 2:** `process12_hypoxia_frequency_map.py`, `process13_do_trend_spatial_mapping.py`
   - **Step 3:** `process01_calculate_bay_decorrelation_scales.py`, `process11_calculate_decorrelation_scale_per_bay.py`, `process12_plot_decorrelation_scale_complete.py`, `process03_decorrelation_seasonal.py`
   - **Step 4:** `process03_plot_pca_eof_map_raw.py`, `process13_plot_pca_eof_map_per_bay_raw.py`
   - **Step 5:** `process41_spatial_correlation_maps.py`
   - **Step 6:** `process01_pc_driver_temporal_analysis.py`

## Status
**Resolved.** The visual size of station markers is now consistently proportional across all map extents and zoom levels, maintaining data legibility and design uniformity across both narrow bay-specific plots and wide regional overviews.
