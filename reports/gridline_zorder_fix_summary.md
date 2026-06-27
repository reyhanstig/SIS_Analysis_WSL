# Gridline Z-Order Fix Summary

## Background
During the spatial mapping stages of the SIS Analysis pipeline (specifically in `step4_PCA_analysis/13_plot_pca_eof_map.py`), gridlines were drawing underneath the high-resolution Geopandas landmass boundaries, despite being explicitly assigned a `zorder` of 10. 

## Root Cause
The root cause of this rendering bug was isolated to a quirk in the Cartopy `Gridliner` object.
- When `ax.gridlines(zorder=MappingConfig.ZORDER_GRIDLINES)` is called, Cartopy correctly propagates the target zorder (10) to the underlying Line2D gridline artists.
- However, the parent `Gridliner` object itself defaults to a hardcoded `zorder` of **2**.
- Matplotlib's draw cycle executes the `Gridliner`'s internal `draw()` method based on its parent `zorder`. Because the `Gridliner` executed at zorder 2, the gridlines were physically rendered onto the canvas *before* the Geopandas land polygons were drawn at zorder 4. Consequently, the high-resolution landmasses painted over the gridlines.

## The Solution
To force Matplotlib to delay the rendering of the gridlines until after the landmasses are drawn, the `Gridliner` object itself must be explicitly updated to reflect the desired high zorder.

This was resolved by appending the following line immediately after instantiation:
```python
gl.set_zorder(MappingConfig.ZORDER_GRIDLINES)
```

## Applied Fixes
The global fix was applied to the centralized mapping configuration:
- **`utils/mapping_config.py`**: The `MappingConfig.apply_gridlines()` helper function was updated to include the explicit `set_zorder()` fix. Any scripts relying on this helper (such as `step4_PCA_analysis`) automatically inherit the fix.
- **`reports/SIS_mapping_standard.md`**: The mapping documentation was updated to reflect this critical technical requirement for anyone creating custom maps.

Additionally, to ensure complete consistency across the entire production pipeline, the following scripts were refactored to use the centralized `MappingConfig.apply_gridlines(ax)` helper instead of calling `ax.gridlines` manually:

### Step 2: Hypoxia Frequency Calculation
- `step2_hypoxia_frequency_calculation/10_hypoxia_frequency_trend_all.py`
- `step2_hypoxia_frequency_calculation/20_hypoxia_frequency_trend_mapping_all_division.py`

### Step 3: Decorrelation Scale Analysis
- `step3_decorrelation_scale_analysis/10_calculate_bay_decorrelation_scales.py`
- `step3_decorrelation_scale_analysis/30_decorrelation_seasonal.py`
- `step3_decorrelation_scale_analysis/40_calculate_decorrelation_scale_per_bay.py`
- `step3_decorrelation_scale_analysis/50_plot_decorrelation_scale_complete.py`

## Verification
Verification was conducted by inspecting the updated PC1 EOF map (`figures/step4_PCA_analysis/13_plot_pca_eof_map/eof_map_pc1.png`). The gridlines correctly rendered over the high-resolution grey landmasses while obeying all formatting constraints. No further action is required for geospatial mapping components.
