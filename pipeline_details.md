# Analysis Pipeline Details

This document provides an in-depth breakdown of the DVC analysis pipeline, describing the inputs, data processing logic, and outputs of each script within the numbered step directories.

## 1. `step1_data_extraction`
This step handles the extraction of raw environmental monitoring data from zipped shapefiles.
- **`10_extract_spatial.py`**: Iterates through zipped shapefile archives containing water quality monitoring data. It reads spatial attributes using `geopandas`, determines the survey year, maps internal `watercode` values (e.g., 201/202) to specific regional names (like "Ise Bay" or "Tokyo Bay"), and extracts the raw shapefile contents into designated raw data folders grouped by year and region.

## 2. `step1_data_processing_cleaning`
This step parses, cleans, and standardizes heterogeneous data formats (including PDFs) into analysis-ready CSVs or spatial DataFrames.
- **`20_extract_fixed_station.py`**: Uses `pdfplumber` and precise coordinate-based parsing to extract daily fixed-station weather and water parameter observations (e.g., Temperature, Salinity, Wind, Rainfall) from complex Japanese government PDF reports (e.g., Osaka surveys). Output is saved as a structured daily CSV.
- **`30_extract_hiroshima_survey.py`**: Parses Hiroshima line survey PDF tables using `pdfplumber`. It aligns numeric text to depth labels (0m, 5m, 10m, 20m, 30m, Bottom) and extracts temperature, salinity, and dissolved oxygen (DO) measurements per station.
- **`40_extract_line_survey.py`**: Similar to the Hiroshima script, but generalized for standard line survey PDF formats. Extracts depth-stratified temperature and salinity data and pivots it into a structured long-format CSV.
- **`50_extract_spatial_data.py`**: Works in tandem with `10_extract_spatial.py` to further refine and route the unzipped spatial dataset folders to the primary processing pipeline directories, handling duplicate checks via MD5 hashing.
- **`60_retrieve_sis_river_stations.py`**: A web-scraping script using Selenium and headless Chrome to retrieve river water level and flow rate station coordinates from the MLIT database. It automatically filters nationwide stations by Seto Inland Sea prefectures and performs a spatial intersection (`geopandas`) to save only those falling strictly within the Seto Inland Sea boundaries.
- **`util_convert_to_geojson.py`**: A utility tool to batch convert shapefiles to standardized GeoJSON formats for easier web mapping and integration.

## 3. `step2_decorrelation_scale_analysis`
This step calculates spatial and temporal decorrelation scales—metrics that define how far from a monitoring station the data remains statistically representative.
- **`10_calculate_bay_decorrelation_scales.py`**: Focuses on Summer Bottom Dissolved Oxygen (DO). It calculates a pairwise distance matrix between all stations, correlates multi-year DO time-series, and fits a Gaussian decay model constrained by a significance threshold (`r_crit`) to compute the exact spatial decorrelation radius (in km) for Ise Bay and Tokyo Bay.
- **`20_decorrelation_analysis_permutations.py`**: Runs permutation analyses and bootstrap sampling to robustly estimate confidence intervals for the calculated decorrelation scales.
- **`30_decorrelation_seasonal.py`**: Extends the decorrelation scale logic to calculate representative radii across different seasons (Spring, Summer, Autumn, Winter) rather than just summer bottom hypoxia.

## 4. `step2_hypoxia_frequency_calculation`
This step evaluates how often different regions experience severe oxygen depletion and models long-term trends.
- **`10_hypoxia_frequency_trend_all.py`**: Segments the Seto Inland Sea into sub-basins (Tokyo Bay, Ise Bay, etc.). Uses an iterative diffusion interpolation algorithm with spatial barriers (KDTree and coastal boundaries) to create continuous spatial maps of climatological Mean DO. It then calculates the frequency of Hypoxic (0-2 mg/L) and Low DO (2-5 mg/L) events and maps linear regression slopes (mg/L/year) to highlight worsening or improving regions.
- **`20_hypoxia_frequency_trend_mapping_all_division.py`**: Generates high-resolution spatial mapping specifically tailored to the designated legal divisions of the Seto Inland Sea, ensuring maps align with regulatory boundaries.
- **`30_hypoxia_frequency_trend_v2.py`**: An updated methodology for calculating DO trends that applies stricter data completeness thresholds and different interpolation weighting.
- **`40_hypoxia_tendecy_per_station.py`**: Outputs time-series plots and trend statistics for individual monitoring stations, identifying specific local hotspots of oxygen depletion.

## 5. `step3_PCA_analysis`
This step uses Principal Component Analysis to distill complex environmental parameters into primary drivers.
- **`10_PCA_env_corr_Ise_bay.py`**: Calculates seawater density (using `gsw-python`) and seasonal climatologies (Temperature, Salinity, Wind, Chlorophyll-a). Fills spatial data gaps using the decorrelation scale derived in Step 2. Runs PCA on the environmental matrix to extract PC1 and PC2. Finally, maps the per-station Pearson correlation between the PC scores and physical factors, highlighting the primary physical drivers of water quality in Ise Bay.
- **`20_PCA_env_corr_Tokyo_bay.py`**: Executes the identical PCA and spatial gap-filling methodology on the Tokyo Bay subset, isolating the dominant environmental forcings unique to that basin.

## 6. `step5_environmental_factor_correlation_analysis`
This step uses statistical modeling to directly link dissolved oxygen (DO) depletion to specific environmental predictors.
- **`10_driver_comparison_by_trend.py`**: Evaluates the long-term trends of potential drivers (e.g., rising surface temperatures vs. changing nutrient loads) and cross-correlates them with the localized DO trends computed in Step 2b.
- **`20_what_affects_do.py`**: Uses a Random Forest Regressor and Pearson Correlation to determine which climatological parameters (Summer Stratification, Winter Air Temp, Spring Chl-a, etc.) best predict spatial variations in DO. Employs permutation importance to robustly rank the top predictors.
- **`30_what_affects_do_v3.py`**: An advanced iteration of the correlation analysis that incorporates time-lagged variables and specific stratification metrics.
- **`40_what_nutrients_affect_do_a.py`**: Specifically isolates chemical and biological predictors (Nitrogen, Phosphorus, Chlorophyll) to evaluate how nutrient loading drives bottom-water hypoxia.
