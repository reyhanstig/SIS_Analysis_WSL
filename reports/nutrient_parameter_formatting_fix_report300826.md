# Nutrient Parameter Formatting Fix Report

## Overview
During the execution and visualization of the SIS Analysis pipeline, it was identified that several nutrient parameters (e.g., `NH4N`, `NO3N`, `NO2N`, `PO4P`) were being displayed without standard hyphenation conventions in figures, UI applications, and output files. 

A global formatting fix was introduced to automatically map these raw parameter variables to their standard presentation format (`NH4-N`, `NO3-N`, `NO2-N`, `PO4-P`) during visualization. Importantly, the underlying dataframes and config logic were left unchanged to prevent breaking dependencies.

## Fix Details

### 1. File Naming Convention Fix (`safe_param` & `safe_title`)
When users ran `dvc repro`, output figures were initially still being named with the old naming convention. We intercepted variables like `safe_param` and `safe_title` prior to saving the matplotlib figures to ensure the output `.png` files appropriately reflect the hyphenated naming structure.

The following files were updated to enforce hyphenation on filenames:
**Step 5:**
- `process15_parameter_timeseries_plotting.py`
- `process32_loading_scatter_plots.py`
- `process41_spatial_correlation_maps.py`
- `process42_time_series_significant_stations_PC_correlation.py`
- `process43_confirm_env_parameter_relationship.py`

**Step 6:**
- `process01_pc_driver_temporal_analysis.py`
- `process02_time_series_significant_stations_PC_correlation.py`
- `process03_confirm_env_parameter_relationship.py`

### 2. X and Y Axes Formatting on Plotting Grids
Heatmaps and categorical boxplots generate their X/Y tick labels directly from dataset columns or dictionaries. To avoid modifying upstream datasets, formatting rules were injected explicitly onto the plot components prior to rendering.
- **`process33_correlation_heatmap.py`**: Intercepted the chunked y-axis label generation to iterate through the raw parameter columns.
- **`process14_significance_comparison.py`**: Added string replacement interception to the row indices of the correlation dataframe directly before generating the Seaborn heatmap.
- **`process12_pca_sensitivity.py` & `process13_raw_sensitivity.py`**: A transformation block was appended immediately after the boxplots were drawn. This fetches `ax.get_xticklabels()`, applies the hyphenated formatters, and sets them back using `ax.set_xticklabels()`.

### 3. Streamlit Dashboards
Interactive plots and UI labels in the local Streamlit dashboards were displaying variables utilizing `.upper()`, generating outputs like `NH4N`. This was intercepted and modified in the plotting wrapper block to ensure UI labels and Hover panels appropriately mirror the pipeline figure outputs.
- `apps/streamlit_app.py`
- `apps/streamlit_app_v2.py`

## Conclusion
The parameter styling logic is now normalized. Following a pipeline build (e.g., `dvc repro`), newly produced `.png` figures will dynamically embed formatted names (`NH4-N`) in both the plot titles and the absolute filepath nomenclature.
