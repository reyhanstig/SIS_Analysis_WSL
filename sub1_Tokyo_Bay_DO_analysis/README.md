# Tokyo Bay Scientific Reproducibility Package

This package contains the raw observation data, analysis scripts, and final processed figures for the Tokyo Bay environmental analysis.

## Execution Order & Script Details
To reproduce the analysis, execute the scripts in the following numerical order. Below is a detailed explanation of what each step folder contains and what its associated scripts do.

### 1. `step1_hypoxia_frequency_calculation`
Contains scripts to calculate and map the frequency and tendency of hypoxia (low dissolved oxygen) across the bay.
- `process11_mean_climatological_do_map.py`: Generates maps of the climatological mean dissolved oxygen levels.
- `process12_hypoxia_frequency_map.py`: Calculates and plots the spatial frequency of occurrence for hypoxic events.
- `process13_do_trend_spatial_mapping.py`: Maps the long-term linear trends of dissolved oxygen geographically.
- `process14_hypoxia_tendency_per_station.py`: Computes time-series tendencies of hypoxia per individual monitoring station.

### 2. `step2_decorrelation_scale_analysis`
Contains scripts to calculate the spatial decorrelation scales of environmental variables, determining the geographic extent over which variables co-vary.
- `process11_calculate_decorrelation_scale_per_bay.py`: Calculates the core decorrelation scales for various parameters.
- `process12_plot_decorrelation_scale_complete.py`: Generates histograms and spatial distribution figures of the decorrelation scales.

### 3. `step3_PCA_analysis`
Contains scripts to perform Principal Component Analysis (PCA) to extract the dominant modes of spatio-temporal variability in the data.
- `process11_calculate_pca_explained_variance_per_bay_raw.py`: Calculates the PCA scores and explained variance for the primary modes.
- `process12_plot_pca_timeseries_per_bay_raw.py`: Generates time series plots of the principal component scores over the survey years.
- `process13_plot_pca_eof_map_per_bay_raw.py`: Creates Empirical Orthogonal Function (EOF) spatial maps showing the geographic loading of the principal components.

### 4. `step4_environmental_factor_correlation_analysis`
Contains scripts to correlate the dominant PCA modes with secondary environmental factors (nutrients, temperature, etc.) to identify drivers of change.
- `process11_trend_grouping_and_maps.py`: Groups variables by trend similarity and maps them geographically.
- `process31_correlation_distribution.py`: Calculates correlation distributions between PCA modes and environmental factors.
- `process41_spatial_correlation_maps.py`: Maps spatial correlations across the bay.
- `process42_time_series_significant_stations_PC_correlation.py`: Plots time series correlations of significant environmental factors against the primary PCs.

## Dependencies & Environment Setup
To ensure total reproducibility, this package requires the specific conda environment used during the original analysis.
1. Install [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or Anaconda.
2. Run the following command in your terminal at the root of this package:
   `conda env create -f environment.yml`
3. Activate the environment before running any scripts:
   `conda activate sis_analysis`

## Data Dictionary: `data/raw_observation_data_tokyo_bay.csv`
This file contains the foundational multi-layer data used across all pipeline steps.

**Temporal Context**
- `surveyyear`, `surveymont`, `surveyday`, `surveyhour`: The exact timestamp of the sampling event (JST).

**Spatial & Sampling Context**
- `zettaicode`: Unique numerical identifier for fixed monitoring stations.
- `latitude`, `longitude`: Coordinate location of the station.
- `saisuipoin`: Refers to the depth of the sampling. `1` indicates surface sampling (depth = 0m). `2` indicates samples taken at the bottom depth indicated by the `depth` column.
- `depth`: The actual recorded sampling depth in meters.

**Environmental Variables**
- `do_`: Dissolved Oxygen (mg/L).
- `wtemp`: Water Temperature (°C).
- `salt`: Salinity (PSU).
- `chla`: Chlorophyll-a.
- `tn`, `tp`: Total Nitrogen, Total Phosphorus.
- `din`, `dip`: Dissolved Inorganic Nitrogen, Dissolved Inorganic Phosphorus.
- `nh4n`, `no2n`, `no3n`, `po4p`: Ammonium, Nitrite, Nitrate, Phosphate.
- `cod`, `toc`, `doc`: Chemical/Total/Dissolved Organic Carbon.
