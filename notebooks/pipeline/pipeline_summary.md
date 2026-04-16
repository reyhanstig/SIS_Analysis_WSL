# SIS Analysis Pipeline Summary

This document provides a detailed overview of the current analysis pipeline. It serves as the source of truth for understanding how data flows through the project.

**Last Updated:** 2026-02-21

---

## 1. Pipeline Overview

The pipeline is managed by **DVC (Data Version Control)** and orchestrated via `dvc.yaml`. It automates the transition from raw environmental data to finalized PCA analysis results.

**Key Command:** `dvc repro` (Runs the entire pipeline)

---

## 2. Global Parameters (`params.yaml`)

These parameters control the behavior of the analysis steps. Adjusting them here and running `dvc repro` will propagate changes throughout the pipeline.

### Seasonal Subsets
| Parameter | Value | Description |
| :--- | :--- | :--- |
| `min_periods` | `15` | Minimum number of years required for a station to be included |
| `representative_months` | `{Spring: 5, Summer: 7, Autumn: 10, Winter: 1}` | Single month used to represent each season (May/Jul/Oct/Jan) |

### Interpolation
| Parameter | Value | Description |
| :--- | :--- | :--- |
| `weighting_func` | `gaussian` | Function used for spatial interpolation weighting |
| `min_weight` | `0.01` | Minimum weight threshold for interpolation |
| `search_radius_factor` | `2.0` | Multiplier for search radius determination |

### Decorrelation Analysis
| Parameter | Value | Description |
| :--- | :--- | :--- |
| `min_periods` | `15` | Minimum number of years required for a station to be included |
| `r_crit_alpha` | `0.01` | Significance level ($p$-value) for critical correlation ($r_{crit}$) |
| `distance_cutoff_km` | `100` | Maximum distance to consider for neighbor counting |

---

## 3. Data Field Definitions

Based on verification in `notebooks/26_check_temp_wtemp.ipynb`, target variables are defined as follows:

| Field | Meaning | Description |
| :--- | :--- | :--- |
| `temp` | **Air Temperature** | Ambient air temperature at the station; independent of sampling depth. |
| `wtemp` | **Water Temperature** | Temperature of the water column at the specified depth layer. |
| `saisuipoin` | **Depth Layer** | `1` = Surface Layer, `2` = Bottom Layer. |
| `do_` | **Dissolved Oxygen** | Concentration in mg/L. |
| `salt` | **Salinity** | Measurement of salt content. |

> **Note on Parameter Aliasing:** Data processing automatically detects alternative "v2" columns (e.g., `do_2`, `salt2`) present in raw shapefiles, which often have better numerical data typing (`float64`) and fewer null values. The pipeline natively replaces the primary column data with these superior "v2" variants during ingestion, meaning standard aliases like `do_` silently represent `do_2` values throughout analytical notebooks.

---

## 4. Pipeline Stages


### Stage 0: `bathymetry_check` (Exploration)
-   **Goal**: Evaluate bathymetry sources (GEBCO vs JODC) for environmental mapping.
-   **Notebook**: `notebooks/31_bathymetry_check.ipynb`
-   **Inputs**:
-       - GEBCO: `data/raw/GEBCO_10_Mar_2026_d2286085bd59/`
-       - JODC: `data/raw/JODC_mesh500_SIS/`
-   **Outputs**: Visual comparisons of resolution and accuracy.
-   **Note**: Not yet integrated into `dvc repro` pipeline, pending dataset selection.

### Stage 1: `process_data`
-   **Goal**: Clean and merge raw datasets into a unified format.
-   **Notebook**: `notebooks/pipeline/01_Data_Processing.ipynb`
-   **Inputs**: Raw data (via `scripts/data_loader.py`)
-   **Outputs**:
    -   `data/processed/merged_gdf.feather` (Cleaned geospatial dataframe)

### Stage 1.1: `hypoxia_mapping`
-   **Goal**: Visualize hypoxia frequency for specific seasons and sampling points.
-   **Notebook**: `notebooks/pipeline/04_Hypoxia_Mapping.ipynb`
-   **Inputs**: `merged_gdf.feather`
-   **Outputs**:
    -   `figures/hypoxia_map_summer_point2.png` (Hypoxia frequency map)

### Stage 1.5: `create_seasonal_datasets`
-   **Goal**: Split merged data into 8 season × layer subsets (yearly parameter mean per station).
-   **Notebook**: `notebooks/pipeline/02_Create_Seasonal_Datasets.ipynb`
-   **Inputs**: `merged_gdf.feather`
-   **Outputs** (one directory per combination):
    -   `data/processed/seasonal/{season}_{layer}/yearly_{param}_df.csv` (where `param` is one of `do_`, `temp`, `wtemp`, `salt`)
-   **Combinations**: Spring/Summer/Autumn/Winter × surface(`saisuipoin=1`) / bottom(`saisuipoin=2`)
-   **Method**: Each season uses a **single representative month** (May/Jul/Oct/Jan) rather than averaging all months in the season. This was validated by `notebooks/sampling_months_check.ipynb`, which showed that >93% of observations already come from the dominant month.
-   **Note**: The shared distance matrix (`dist_matrix_km.csv`) is **not** recomputed here — it is produced once by Stage 2.

**Important Data Caveat:** Seasonal subsets only extract data from a single representative month (Spring=5, Summer=7, Autumn=10, Winter=1) to prevent sampling bias. Consequently, some years (like 1981 and 1983 for Summer) are missing entirely from downstream pipelines because no sampling occurred during the strict representative month for that year.


### Stage 2: `decorrelation`
-   **Goal**: Analyze spatial decorrelation scales for each station.
-   **Notebook**: `notebooks/pipeline/08_Decorrelation_Analysis_v3.ipynb`
-   **Key parameter**: `subset_dir` — path to a seasonal subset directory (defaults to `summer_bottom`)
-   **Inputs**: `data/processed/seasonal/{subset}/yearly_do_df.csv`, `merged_gdf.feather` (for station coordinates)
-   **Outputs**:
    -   `data/processed/dist_matrix_km.csv` (**shared** station distance matrix, written once for `summer_bottom`)
    -   `data/processed/seasonal/{subset}/stations_decorrelation_scale.csv`

### Stage 2.1: `decorrelation_analysis_continue` (Exploration)
-   **Goal**: Explore correlations between spatial decorrelation scales and environmental factors like station depth and hypoxia frequency.
-   **Notebook**: `notebooks/30_decorrelation_analysis_continue.ipynb`
-   **Inputs**: `stations_decorrelation_scale.csv`, `merged_gdf.feather`
-   **Outputs**: Scatter plots and correlation analysis.

### Stage 2.2: `decorrelation_tokyo`
-   **Goal**: Analyze spatial decorrelation scales specifically for Tokyo Bay stations, adhering to the standard 2-parameter Gaussian model methodology.
-   **Notebook**: `notebooks/pipeline/39a_Decorrelation_Analysis_Tokyo_Bay.ipynb`
-   **Inputs**: `data/processed/seasonal/{subset}/yearly_do_df.csv`, `merged_gdf.feather`
-   **Outputs**:
    -   `data/processed/seasonal/{subset}/tokyo_bay_decorrelation_scale.csv`
    -   `figures/tokyo_bay_decorrelation_scale.png`

### Stage 2.3: `decorrelation_ise`
-   **Goal**: Analyze spatial decorrelation scales specifically for Ise Bay stations, adhering to the standard 2-parameter Gaussian model methodology.
-   **Notebook**: `notebooks/pipeline/39b_Decorrelation_Analysis_Ise_Bay.ipynb`
-   **Inputs**: `data/processed/seasonal/{subset}/yearly_do_df.csv`, `merged_gdf.feather`
-   **Outputs**:
    -   `data/processed/seasonal/{subset}/ise_bay_decorrelation_scale.csv`
    -   `figures/ise_bay_decorrelation_scale.png`

### Stage 3: `interpolation`
-   **Goal**: Fill missing DO data using spatial interpolation based on decorrelation scales.
-   **Notebook**: `notebooks/pipeline/09_Spatial_Interpolation_v2.ipynb`
-   **Key parameter**: `subset_dir` — path to a seasonal subset directory (defaults to `summer_bottom`)
-   **Inputs**: `yearly_do_df.csv` and `stations_decorrelation_scale.csv` from `subset_dir`; shared `dist_matrix_km.csv`
-   **Outputs**:
    -   `data/processed/seasonal/{subset}/interpolated_do_df.csv`

### Stage 4: `pca_analysis`
-   **Goal**: Perform Principal Component Analysis (PCA) to identify dominant spatiotemporal patterns.
-   **Notebook**: `notebooks/pipeline/10_PCA_Analysis.ipynb`
-   **Key parameter**: `subset_dir` — path to a seasonal subset directory (defaults to `summer_bottom`)
-   **Inputs**: `interpolated_do_df.csv` from `subset_dir`
-   **Outputs**:
    -   `data/processed/seasonal/{subset}/pca_scores.csv`
    -   `data/processed/seasonal/{subset}/pca_loadings.csv`
    -   `data/processed/seasonal/{subset}/pca_variance.csv`

### Stage 4.1: `pca_env_corr`
-   **Goal**: Calculate Pearson correlations between PCA scores and environmental parameters per station over time.
-   **Script**: `notebooks/pipeline/33_DO_PCA_corr.py`
-   **Inputs**: `data/processed/merged_gdf.feather`, `data/processed/seasonal/{subset}/pca_scores.csv`
-   **Outputs**:
    -   `data/processed/seasonal/{subset}/pca_env_corr_pc1.csv`
    -   `data/processed/seasonal/{subset}/pca_env_corr_pc2.csv`

---

## 5. Key Artifacts (Path Constants)

All file paths are centrally managed in `scripts/paths.py`.

| Constant Name | Path | Description |
| :--- | :--- | :--- |
| `MERGED_DATA_FILE` | `data/processed/merged_gdf.feather` | Primary cleaned dataset |
| `YEARLY_DO_FILE` | `data/processed/yearly_do_df.csv` | Legacy summer_bottom flat file (kept for comparison) |
| `DIST_MATRIX_FILE` | `data/processed/dist_matrix_km.csv` | **Shared** station distance matrix |
| `DECORRELATION_SCALE_FILE` | `data/processed/stations_decorrelation_scale.csv` | Legacy decorrelation results |
| `INTERPOLATED_DO_FILE` | `data/processed/interpolated_do_df.csv` | Legacy interpolated grid |
| `PCA_SCORES_FILE` | `data/processed/pca_scores.csv` | Legacy PCA temporal results |
| `PCA_LOADINGS_FILE` | `data/processed/pca_loadings.csv` | Legacy PCA spatial results |
| `PCA_VARIANCE_FILE` | `data/processed/pca_variance.csv` | Legacy PCA variance results |
| `PCA_ENV_CORR_PC1_FILE` | `data/processed/pca_env_corr_pc1.csv` | PCA PC1 vs Environmental Correlation results |
| `PCA_ENV_CORR_PC2_FILE` | `data/processed/pca_env_corr_pc2.csv` | PCA PC2 vs Environmental Correlation results |
| `SEASONAL_DATA_DIR` | `data/processed/seasonal/` | Root directory for all seasonal subsets |
| `get_subset_dir(season, layer)` | `data/processed/seasonal/{season}_{layer}/` | Helper method — returns subset directory |


### 6. `generate_seasonal_plots`
- **Script:** `scripts/generate_seasonal_plots.py`
- **Purpose:** Automates the creation of high-quality spatial interpolation matrices and visual maps for seasonal parameters across multiple years, utilizing multiprocessing for maximum CPU efficiency. Creates individual maps, 2x2 seasonal grids, and yearly progressions.
- **Dependencies:** `scripts/generate_seasonal_plots.py`, `params.yaml`, `data/boundaries/SIS water mass polygon/sea_area_mask_simplified.shp`, `data/processed/merged_gdf.feather`
- **Output:** Nested directories and mapped figures within `figures/seasonal_plots/`
