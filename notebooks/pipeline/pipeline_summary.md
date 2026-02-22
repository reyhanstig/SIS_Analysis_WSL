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

## 3. Pipeline Stages

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
-   **Goal**: Split merged data into 8 season × layer subsets (yearly DO per station).
-   **Notebook**: `notebooks/pipeline/02_Create_Seasonal_Datasets.ipynb`
-   **Inputs**: `merged_gdf.feather`
-   **Outputs** (one directory per combination):
    -   `data/processed/seasonal/{season}_{layer}/yearly_do_df.csv`
-   **Combinations**: Spring/Summer/Autumn/Winter × surface(`saisuipoin=1`) / bottom(`saisuipoin=2`)
-   **Method**: Each season uses a **single representative month** (May/Jul/Oct/Jan) rather than averaging all months in the season. This was validated by `notebooks/sampling_months_check.ipynb`, which showed that >93% of observations already come from the dominant month.
-   **Note**: The shared distance matrix (`dist_matrix_km.csv`) is **not** recomputed here — it is produced once by Stage 2.

### Stage 2: `decorrelation`
-   **Goal**: Analyze spatial decorrelation scales for each station.
-   **Notebook**: `notebooks/pipeline/08_Decorrelation_Analysis_v3.ipynb`
-   **Key parameter**: `subset_dir` — path to a seasonal subset directory (defaults to `summer_bottom`)
-   **Inputs**: `data/processed/seasonal/{subset}/yearly_do_df.csv`, `merged_gdf.feather` (for station coordinates)
-   **Outputs**:
    -   `data/processed/dist_matrix_km.csv` (**shared** station distance matrix, written once for `summer_bottom`)
    -   `data/processed/seasonal/{subset}/stations_decorrelation_scale.csv`

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

---

## 4. Key Artifacts (Path Constants)

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
| `SEASONAL_DATA_DIR` | `data/processed/seasonal/` | Root directory for all seasonal subsets |
| `get_subset_dir(season, layer)` | `data/processed/seasonal/{season}_{layer}/` | Helper method — returns subset directory |

