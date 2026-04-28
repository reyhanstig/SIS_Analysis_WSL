# Streamlit Dashboard Documentation — 2026-04-27

This document outlines the architecture, features, and deployment of the two Streamlit dashboards developed for the Seto Inland Sea (SIS) water quality analysis project.

## 1. Overview
The project maintains two distinct Streamlit applications to serve different analytical needs:
1. **`streamlit_app.py` (V1)**: A dedicated time-series explorer for raw observation data.
2. **`streamlit_app_v2.py` (V2)**: A comprehensive analytical dashboard that integrates time-series exploration with pipeline results (PCA, Spatial Analysis, and Environmental Correlations).

---

## 2. Data Architecture
Both apps leverage a tiered data loading system to ensure performance while handling large datasets:

| Tier | Data Source | Usage | Loading Strategy |
| :--- | :--- | :--- | :--- |
| **Tier 1** | `merged_gdf.feather` | Raw observations & physical indices (Density, Stratification). | Loaded once at startup; cached globally. |
| **Tier 2** | `data/processed/seasonal/{season}_{layer}/*.csv` | PCA scores/loadings, decorrelation scales, interpolated maps, env correlations. | Lazily loaded on-demand based on sidebar filters. |

---

## 3. Dashboard V1: Time-Series Explorer
**File**: `scripts/streamlit_app.py`

### Key Features
*   **Station Lookup Map**: Interactive map using Plotly Mapbox. Highlighting stations selected in any comparison pane.
*   **Multi-Pane Comparison**: Allows users to create up to 5 side-by-side (stacked) time-series panes.
*   **Dynamic Filtering**: Sidebar controls for Watermass, Division, Year Range, Season, and Depth Layer.
*   **Y-Axis Synchronization**: Option to use a global Y-axis scale across all panes or a manual range for detailed inspection.

---

## 4. Dashboard V2: Analysis Dashboard
**File**: `scripts/streamlit_app_v2.py`

This version introduces a multi-tab interface to visualize the complete analytical pipeline.

### Tab 1: 📈 Time-Series Explorer
An enhanced version of V1 that includes additional derived physical metrics from the `01b` pipeline stage:
*   `density` (Potential Density)
*   `stratification` (Bottom - Surface Density)
*   `stratification_gradient` (Stratification / Depth Difference)

### Tab 2: 📊 PCA Results
Visualizes the output of the Principal Component Analysis:
*   **Scree Plot**: Interactive bar/line chart showing individual and cumulative explained variance.
*   **PC Scores**: Time-series of PC scores (PC1, PC2, etc.) to identify temporal trends.
*   **Eigenvector Map**: Spatial distribution of station loadings for the selected PC, helping identify geographical variance drivers.

### Tab 3: 🗺️ Spatial Analysis
Focuses on the spatial structure of the data:
*   **Decorrelation Scale Map**: Shows the spatial decorrelation scale (km) for each station.
    *   *Color*: Decorrelation scale value.
    *   *Size*: Number of neighbors within 100km.
*   **Interpolated DO Map**: A slider-controlled map allowing users to view interpolated Dissolved Oxygen fields across years. Includes a toggle to compare "Raw" vs "Interpolated" data points.

### Tab 4: 🔗 Environmental Correlations
Interactive mapping of environmental drivers:
*   **Correlation Map**: Displays Pearson correlation (r) between a selected PC and environmental parameters (e.g., SST, Wind, Air Temp).
*   **Significance Scaling**: Marker sizes are dynamically scaled based on p-values (***, **, *, ns).
*   **Distribution Boxplot**: Shows the overall distribution of r-values across all stations for a quick "net impact" assessment.

---

## 5. Execution Instructions

### Running a Single App
From the root of the project:
```bash
conda activate sis_analysis
streamlit run scripts/streamlit_app_v2.py
```

### Running Both Simultaneously
To run both apps, assign them to different ports:
```bash
# Terminal 1: Original App (Default Port 8501)
streamlit run scripts/streamlit_app.py --server.port 8501

# Terminal 2: Analysis App (Port 8502)
streamlit run scripts/streamlit_app_v2.py --server.port 8502
```

---

## 6. Maintenance & Troubleshooting
*   **Missing Analysis Data**: If a tab in V2 displays an info message ("Pipeline results not available"), ensure that the corresponding `dvc` stage has been executed for that specific season and layer combination.
*   **Import Errors**: Both apps use a robust import block for `ProjectPaths` to ensure they can be launched from either the project root or the `scripts/` directory.
*   **Port Conflicts**: Use `pkill -f streamlit` to clear any hung processes if ports appear stuck.
