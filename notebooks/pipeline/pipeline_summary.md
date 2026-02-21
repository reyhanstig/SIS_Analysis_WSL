# SIS Analysis Pipeline Summary

This document provides a detailed overview of the current analysis pipeline. It serves as the source of truth for understanding how data flows through the project.

**Last Updated:** 2026-02-19

---

## 1. Pipeline Overview

The pipeline is managed by **DVC (Data Version Control)** and orchestrated via `dvc.yaml`. It automates the transition from raw environmental data to finalized PCA analysis results.

**Key Command:** `dvc repro` (Runs the entire pipeline)

---

## 2. Global Parameters (`params.yaml`)

These parameters control the behavior of the analysis steps. Adjusting them here and running `dvc repro` will propagate changes throughout the pipeline.

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

### Stage 2: `decorrelation`
-   **Goal**: Analyze spatial decorrelation scales for each station.
-   **Notebook**: `notebooks/pipeline/08_Decorrelation_Analysis_v3.ipynb`
-   **Inputs**: `merged_gdf.feather`
-   **Outputs**:
    -   `data/processed/yearly_do_df.csv` (Yearly aggregated DO data)
    -   `data/processed/dist_matrix_km.csv` (Station-to-station distance matrix)
    -   `data/processed/stations_decorrelation_scale.csv` (Calculated decorrelation scales)

### Stage 3: `interpolation`
-   **Goal**: Fill missing DO data using spatial interpolation based on decorrelation scales.
-   **Notebook**: `notebooks/pipeline/09_Spatial_Interpolation_v2.ipynb`
-   **Inputs**: Yearly DO, Distance Matrix, Decorrelation Scales
-   **Outputs**:
    -   `data/processed/interpolated_do_df.csv` (Complete DO dataset with filled values)

### Stage 4: `pca_analysis`
-   **Goal**: Perform Principal Component Analysis (PCA) to identify dominant spatiotemporal patterns.
-   **Notebook**: `notebooks/pipeline/10_PCA_Analysis.ipynb`
-   **Inputs**: Interpolated DO, Decorrelation Scales
-   **Outputs**:
    -   `data/processed/pca_scores.csv` (Temporal PCA scores)
    -   `data/processed/pca_loadings.csv` (Spatial PCA loadings)
    -   `data/processed/pca_variance.csv` (Explained variance stats)

---

## 4. Key Artifacts (Path Constants)

All file paths are centrally managed in `scripts/paths.py`.

| Constant Name | Path (`data/processed/...`) | Description |
| :--- | :--- | :--- |
| `MERGED_DATA_FILE` | `merged_gdf.feather` | Primary cleaned dataset |
| `YEARLY_DO_FILE` | `yearly_do_df.csv` | Aggregated yearly data |
| `DIST_MATRIX_FILE` | `dist_matrix_km.csv` | Distance matrix |
| `DECORRELATION_SCALE_FILE` | `stations_decorrelation_scale.csv` | Decorrelation results |
| `INTERPOLATED_DO_FILE` | `interpolated_do_df.csv` | Interpolated grid |
| `PCA_SCORES_FILE` | `pca_scores.csv` | PCA temporal results |
| `PCA_LOADINGS_FILE` | `pca_loadings.csv` | PCA spatial results |
