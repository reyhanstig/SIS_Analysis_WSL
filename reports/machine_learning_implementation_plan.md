# Machine Learning Implementation Plan

## Executive Summary
This report outlines the strategy for integrating `pandas`-based machine learning (augmented with `scikit-learn`) into the Seto Inland Sea (SIS) Analysis pipeline. Based on a scan of the active notebooks (1-30), the current workflow is primarily analytical, relying on physics-based interpolation (Diffusion/Kriging) and linear statistical models (PCA, Decorrelation analysis). 

Machine Learning can be explicitly utilized to enhance **Data Processing**, **Spatial Interpolation (Analysis)**, and **Predictive Visualization**.

---

## 1. Review of Existing Notebook Pipeline (Focusing on NB 13-30)

The workspace scan revealed the following patterns in the current methodology:
- **Data Processing & Cleaning**: `01_Data_Processing`, `02_Create_Seasonal_Datasets`, `11_saisuipoin_cleaning`, and `26_check_temp_wtemp` handle data wrangling strictly via conditional filtering and standard aggregations.
- **Analysis (Interpolation)**: Notebooks 17-25 are heavily dedicated to physics-based interpolation (Diffusion Equation & Ordinary Kriging) to estimate historical Dissolved Oxygen (DO), Salinity, Air/Water Temperature. 
- **Analysis (Dimensionality Reduction)**: Notebooks `10_PCA_Analysis`, `12_PCA_analysis_continue`, and `28_EOF_anomaly` apply unsupervised learning via Principal Component Analysis (PCA) to find dominant environmental factors.
- **Visualization**: `13_nutrient_analysis`, `14_phase_trajectory_practice`, `15_water_mass_division_overview`, and `04_Hypoxia_Mapping` deal with mapping spatial statistics and correlations.

---

## 2. Applicable ML Integration Points

### A. Data Processing: Predictive Imputation
**Relevant Notebooks**: `01_Data_Processing.ipynb`, `02_Create_Seasonal_Datasets.ipynb`
**Implementation Detail**: 
Missing environmental values (`salt`, `temp`) limit downstream analysis. Instead of relying solely on dropping missing `NaN` values, we can implement **Iterative Imputation**. 
- **Methodology**: Treat each feature as a function of others. A `Random Forest` regressor or `BayesianRidge` can predict missing `salt` values using available `lat`, `lon`, `depth`, and `temp` using `sklearn.impute.IterativeImputer`.

### B. Analysis: ML-driven Spatial Interpolation Regression
**Relevant Notebooks**: `17_interpolation_comparison.ipynb`, `20_diffusion_eq_interp.ipynb`
**Implementation Detail**: 
The diffusion equation relies heavily on geometric constraints. ML can provide a data-driven baseline or hybrid alternative that learns non-linear relationships without needing explicit boundary polygons.
- **Methodology**: Formulate interpolation as a Regression task. 
  - **Features**: `['lat', 'lon', 'temp', 'wtemp', 'salt', 'saisuipoin']`
  - **Target**: `do_` (Dissolved Oxygen)
  - **Algorithm**: Train a `GradientBoostingRegressor` or `RandomForestRegressor`. This can handle the complex interactions between high temperatures and low DO efficiently using standard `pandas` DataFrames.

### C. Analysis: Automated Station Clustering (Unsupervised ML)
**Relevant Notebooks**: `10_PCA_Analysis.ipynb`, `28_EOF_anomaly.ipynb`
**Implementation Detail**: 
PCA identifies variance axes, but does not explicitly group stations.
- **Methodology**: Apply **K-Means Clustering** or **DBSCAN** onto the `pca_scores.csv` directly within pandas. This will physically map out "Environmental Regimes" (e.g., classifying stations into Cluster 1: High Variance Surface, Cluster 2: Stable Bottom, etc.).

### D. Visualization/Prediction: Hypoxia Vulnerability Classifier
**Relevant Notebooks**: `04_Hypoxia_Mapping.ipynb`, `13_nutrient_analysis.ipynb`
**Implementation Detail**: 
Currently, mapping highlights historical hypoxia frequency. ML can model *why* hypoxia occurs and *predict* its likelihood.
- **Methodology**: Supervised Classification.
  - **Target Generation**: Create a binary target `df['is_hypoxic'] = (df['do_'] < 2.0).astype(int)`
  - **Algorithm**: Train a `LogisticRegression` or `RandomForestClassifier` on nutrients (`TN`, `TP`, `DIN`) and temperatures.
  - **Visualization**: Extract and plot the **Feature Importances** (e.g., proving that bottom water temp is a stronger predictor than salinity).

---

## 3. Potential for Main Pipeline Replacement & Improvements

Machine Learning can fundamentally rethink core stages of the existing DVC pipeline, offering improvements in both speed and accuracy.

### Stage 3: Spatial Interpolation (Potential for Complete Replacement)
The current **Diffusion Equation** and **Kriging** methods (`09_Spatial_Interpolation_v2.ipynb`) are computationally intensive and require complex land-masking polygons to define boundaries.
- **ML Improvement**: A **Spatial Regression Model** (e.g., Random Forest or XGBoost) learns relationships directly from `Lat/Lon`, `Temp`, `Salinity`, and `Depth`. It inherently understands geographic barriers and eliminates the need for expensive SOR solvers.

### Stage 2: Decorrelation Analysis (Potential Obsolescence)
Current pipeline calculates distance-decay fits per station to determine interpolation weights.
- **ML Improvement**: If transitioning to ML-driven interpolation, **this entire stage potentially becomes obsolete**. ML regression models learn spatial correlation dynamically from the training data, removing the requirement for manual decorrelation measurements.

### Stage 1.5: Seasonal Data Preparation (Preserving Data Volume)
Currently, station-years missing collateral data (like Salinity) are often ignored.
- **ML Improvement**: Using **Iterative Imputation**, the pipeline can predict missing values based on the correlations between other features, effectively retaining historical data that would otherwise be rejected.

### Stage 4: PCA Analysis (From Variance to Actionable Zones)
PCA identifies variability but doesn't classify regions.
- **ML Improvement**: Appending **Unsupervised Clustering (K-Means)** to the PCA scores allows for the definition of distinct "Environmental Regimes". This transforms statistical outputs into a segmented geographic map (e.g., "Zone 1: Stable Surface", "Zone 2: Hypoxia Vulnerable Bottom").

---

## 4. Step-by-Step Implementation Roadmap

If approved, the agent will implement these features seamlessly into the DVC pipeline:

1. **Create `notebooks/pipeline/102_ML_Imputation.ipynb`**
   - Import dataset, apply `sklearn` Iterative Imputer, export cleaned data back to `data/processed/`.
2. **Create `notebooks/pipeline/103_ML_Interpolation.ipynb`**
   - Evaluate Random Forest Regressor vs current Diffusion Equation on a holdout test set (Cross-validation).
3. **Extend `notebooks/pipeline/10_PCA_Analysis.ipynb`**
   - Append a `KMeans` clustering section at the end of the notebook. Output cluster labels to `data/processed/station_clusters.csv`.
4. **Update `dvc.yaml`**
   - Link these new ML notebooks into the main data pipeline, ensuring `dvc repro` tracks the model artifacts correctly.

