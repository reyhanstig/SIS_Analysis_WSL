# Analysis Pipeline Details

This document provides an in-depth breakdown of the DVC analysis pipeline, describing the inputs, data processing logic, and outputs of each script within the numbered step directories.

## 1. `step1_data_processing_cleaning`
This step parses, cleans, and standardizes heterogeneous data formats (including PDFs) into analysis-ready CSVs or spatial DataFrames.
- **`process01_extract_spatial_data.py`**: Iterates through zipped shapefile archives containing water quality monitoring data. It reads spatial attributes using `geopandas`, determines the survey year, maps internal `watercode` values (e.g., 201/202) to specific regional names (like "Ise Bay" or "Tokyo Bay"), and extracts the raw shapefile contents into designated raw data folders grouped by year and region, handling duplicate checks via MD5 hashing.
- **`process02_create_seasonal_subset.py`**: Filters the cleaned, merged dataset by season and layer, extracting a yearly averaged station matrix for key parameters (DO, temp, wtemp, salt) taking into account region-aware representative months.
- **`process03_extract_fixed_station.py`**: Uses `pdfplumber` and precise coordinate-based parsing to extract daily fixed-station weather and water parameter observations (e.g., Temperature, Salinity, Wind, Rainfall) from complex Japanese government PDF reports (e.g., Osaka surveys). Output is saved as a structured daily CSV.
- **`process04_extract_hiroshima_survey.py`**: Parses Hiroshima line survey PDF tables using `pdfplumber`. It aligns numeric text to depth labels (0m, 5m, 10m, 20m, 30m, Bottom) and extracts temperature, salinity, and dissolved oxygen (DO) measurements per station.
- **`process05_extract_line_survey.py`**: Similar to the Hiroshima script, but generalized for standard line survey PDF formats. Extracts depth-stratified temperature and salinity data and pivots it into a structured long-format CSV.
- **`process06_retrieve_sis_river_stations.py`**: A web-scraping script using Selenium and headless Chrome to retrieve river water level and flow rate station coordinates from the MLIT database. It automatically filters nationwide stations by Seto Inland Sea prefectures and performs a spatial intersection (`geopandas`) to save only those falling strictly within the Seto Inland Sea boundaries.
- **`util_convert_to_geojson.py`**: A utility tool to batch convert shapefiles to standardized GeoJSON formats for easier web mapping and integration.

## 2. `step2_hypoxia_frequency_calculation`
This step evaluates how often different regions experience severe oxygen depletion and models long-term trends.
- **`process01_hypoxia_frequency_trend_all.py`**: Segments the Seto Inland Sea into sub-basins (Tokyo Bay, Ise Bay, etc.). Uses an iterative diffusion interpolation algorithm with spatial barriers (KDTree and coastal boundaries) to create continuous spatial maps of climatological Mean DO. It then calculates the frequency of Hypoxic (0-2 mg/L) and Low DO (2-5 mg/L) events and maps linear regression slopes (mg/L/year) to highlight worsening or improving regions.
- **`process02_hypoxia_frequency_trend_mapping_all_division.py`**: Generates high-resolution spatial mapping specifically tailored to the designated legal divisions of the Seto Inland Sea, ensuring maps align with regulatory boundaries.
- **`process03_hypoxia_frequency_trend_v2.py`**: An updated methodology for calculating DO trends that applies stricter data completeness thresholds and different interpolation weighting.
- **`process04_hypoxia_tendecy_per_station.py`**: Outputs time-series plots and trend statistics for individual monitoring stations, identifying specific local hotspots of oxygen depletion.

## 3. `step3_decorrelation_scale_analysis`
This step calculates spatial and temporal decorrelation scales—metrics that define how far from a monitoring station the data remains statistically representative.
- **`process01_calculate_bay_decorrelation_scales.py`**: Focuses on Summer Bottom Dissolved Oxygen (DO). It calculates a pairwise distance matrix between all stations, correlates multi-year DO time-series, and fits a Gaussian decay model constrained by a significance threshold (`r_crit`) to compute the exact spatial decorrelation radius (in km) for Ise Bay and Tokyo Bay.
- **`process02_decorrelation_analysis_permutations.py`**: Runs permutation analyses and bootstrap sampling to robustly estimate confidence intervals for the calculated decorrelation scales.
- **`process03_decorrelation_seasonal.py`**: Extends the decorrelation scale logic to calculate representative radii across different seasons (Spring, Summer, Autumn, Winter) rather than just summer bottom hypoxia.
- **`process11_calculate_decorrelation_scale_per_bay.py`**: Separates all selected water masses (e.g., Seto Inland Sea) into their individual sub-basins first, then calculates the decorrelation scale for each basin dynamically. Outputs simple spatial visualizations for each region.
- **`process12_plot_decorrelation_scale_complete.py`**: Generates the formal, high-resolution map figures for the decorrelation scales calculated in script 40, applying accurate land boundaries and shapefiles.

## 4. `step4_PCA_analysis`
This step uses Principal Component Analysis to distill complex environmental parameters into primary drivers.
- **`process01_calculate_pca_explained_variance_raw.py`**: Loads the spatially interpolated dissolved oxygen (DO) data for the target region and performs PCA to extract the dominant spatial and temporal patterns (PC1 and PC2) and calculate explained variance.
- **`process02_plot_pca_timeseries_raw.py`**: Generates PC time series plots from the PCA results.
- **`process03_plot_pca_eof_map_raw.py`**: Generates spatial EOF maps from the PCA results.
- **`process11_calculate_pca_explained_variance_per_bay_raw.py`**: Conducts the identical PCA dynamically for each individual sub-basin. It iterates through the divisions, dynamically interpolates missing DO data using a Gaussian weight function bounded by that basin's specific decorrelation scale, and calculates explained variance.
- **`process12_plot_pca_timeseries_per_bay_raw.py`**: Generates per-basin PC time series plots.
- **`process13_plot_pca_eof_map_per_bay_raw.py`**: Generates per-basin spatial EOF maps.

## 5. `step5_environmental_factor_correlation_analysis`
This step uses statistical modeling to directly link dissolved oxygen (DO) depletion to specific environmental predictors.
- **`process01_driver_comparison_by_trend.py`**: Evaluates the long-term trends of potential drivers (e.g., rising surface temperatures vs. changing nutrient loads) and cross-correlates them with the localized DO trends computed in Step 2.
- **`process02_what_affects_do.py`**: Uses a Random Forest Regressor and Pearson Correlation to determine which climatological parameters (Summer Stratification, Winter Air Temp, Spring Chl-a, etc.) best predict spatial variations in DO. Employs permutation importance to robustly rank the top predictors.
- **`process03_what_affects_do_v3.py`**: An advanced iteration of the correlation analysis that incorporates time-lagged variables and specific stratification metrics.
- **`process04_what_nutrients_affect_do_a.py`**: Specifically isolates chemical and biological predictors (Nitrogen, Phosphorus, Chlorophyll) to evaluate how nutrient loading drives bottom-water hypoxia.
