# Dissolved Oxygen as the Primary Driver of Benthic Community Assembly Under Seasonal Hypoxia in the Semi-Enclosed Seto Inland Sea Japan

## Mega Prompt — Full Analysis Pipeline

---

## What This Study Is

This study reproduces and extends the analysis framework from:

> Lai, H. et al. (2024). Characteristics of demersal fish community structure during summer hypoxia in the Pearl River Estuary, China. Ecology and Evolution, 14(7), e11722. https://doi.org/10.1002/ece3.11722

The original paper examined how summer hypoxia (dissolved oxygen ≤ 2 mg/L) affects demersal fish communities in the Pearl River Estuary, China, using a single July 2021 survey across 24 stations. It used NMDS, PERMANOVA, GAMs, Mantel tests, and species/functional diversity indices to show that dissolved oxygen is the primary structuring force for fish communities under hypoxic conditions.

This study applies the same analytical logic to the Seto Inland Sea (Setonaikai), Japan — one of the world's most documented seasonal hypoxia systems — using real long-term monitoring data spanning over three decades (1991–2024). The key upgrades over the original paper are: (1) benthos instead of fish, which show stronger and more direct DO-community relationships because they cannot escape hypoxia, (2) multi-decadal temporal depth instead of a single snapshot, and (3) a hybrid unsupervised-supervised machine learning pipeline replacing pure ordination methods.

---

## Your Datasets

You have the following files. Read each one carefully before beginning any analysis step.

### fixed_line_survey_long_hiroshima.csv
Monthly shallow-sea fixed-line survey data from Hiroshima Prefecture covering Hiroshima Bay, Aki Nada, and Northern Bingo Nada for the year 2014. Shape is 1,199 rows and 6 columns: Month (1 to 12), Station (18 stations with IDs 1, 2, 4, 6, 7, 13, 15, 17, 18, 19, 20, 21, 24, 33, 34, 35, 36, 37, 38), Depth (0m, 2m, 5m, 10m, 20m, 30m, Bottom), DO in mg/L, Salinity in PSU, Temperature in degrees Celsius. This is your primary hypoxia dataset. The DO column is only available here, not in the Osaka data. Filter to Depth == Bottom for all bottom-layer analyses. Hypoxia threshold is DO ≤ 2 mg/L. Summer season is months 6 through 9.

### fixed_line_survey_long_osaka.csv
Monthly fixed-line survey from Osaka Bay for 2016 (Heisei 28). Shape is 1,143 rows and 5 columns: Month, Station (1 to 20), Depth (0m, 5m, 10m, 20m, 30m, Bottom), Salinity in PSU, Temperature in degrees Celsius. There is no DO column. Use the surface-to-bottom temperature difference as a stratification index — a difference greater than 3 degrees Celsius indicates a strong thermocline that suppresses vertical oxygen mixing and is a reliable proxy for hypoxia risk.

### fixed_station_observations_osaka.csv
Daily meteorological and oceanographic observations from the Osaka Fisheries Technology Center fixed station at Misaki town for 2016. Shape is 414 rows and 16 columns including air temperature, humidity, barometric pressure, rainfall, solar radiation, wind speed, wind direction, water temperature, and salinity. Use this as atmospheric forcing context. Rainfall drives freshwater stratification and wind speed drives stratification breakdown and hypoxia dissipation events.

### station_meta.csv
Spatial metadata for the 20 Osaka fixed-line stations. Columns are Station_ID, Latitude_N in degrees-minutes format, Longitude_E in degrees-minutes format, and Nominal_Depth_m ranging from 12 to 60 meters. Parse coordinates by splitting on the space and computing decimal degrees as degrees plus minutes divided by 60. Deeper stations are more prone to bottom hypoxia.

### bottom_2023.xlsx — sheet named 底質_累積2023
Long-term bottom sediment survey data from 1991 to 2024 across multiple sea areas of the Seto Inland Sea. Shape is 1,852 rows and 51 columns. The key columns you need are: 年 (Year), 月 (Month), 緯度_度 plus 緯度_分 plus 緯度_秒 for latitude, 経度_度 plus 経度_分 plus 経度_秒 for longitude, 水深 (water depth in meters), pH, ORP (redox potential in mV — negative values indicate reducing/anoxic conditions), 強熱減量 (loss on ignition as percentage, represents sediment organic content), COD (chemical oxygen demand in mg/g), TN (total nitrogen in mg/g), TP (total phosphorus in mg/g), TOC (total organic carbon in mg/g), 硫化物 (sulfides in mg/g — high values indicate anaerobic decomposition underway), 砂分/粘土分/礫分 (sand/clay/gravel percentages), 季節 where 2.夏 means Summer and 4.冬 means Winter, and 海域 for sea area code. Sea area codes relevant to this study are 301 through 304 for Osaka Bay and Harima Nada, and 400 for Hiroshima Bay area. This is your multi-decadal sediment oxygen demand dataset and the foundation for the Random Forest prediction model. Sampled twice yearly in summer (month 7 or 8) and winter (month 1 or 2). To convert coordinates from degrees-minutes-seconds to decimal degrees use: decimal = degrees + minutes/60 + seconds/3600.

### benthos data (from benthos_manual.xls and the broader national survey)
Benthic macrofauna species composition and abundance data from the Seto Inland Sea. This is your community matrix — the equivalent of the fish catch data in the original paper. Benthic organisms are sessile and cannot escape hypoxia the way fish can, so their community composition directly reflects accumulated oxygen stress and the DO-diversity relationships will be cleaner and stronger than those reported for fish in the original paper. The dominant stress-indicator taxa in hypoxic SIS sediments are opportunistic polychaetes such as Capitella and Mediomastus. Diverse communities with bivalves and echinoderms indicate normoxic recovery conditions.

### Environmental data folders (YYYY_SIS_wq-raw, YYYY_Osaka_wq-raw etc.)
Year-by-year raw water quality files from 1978 to 2023 covering the whole Seto Inland Sea. Each folder likely contains seasonal water quality profiles with DO at depth, temperature, salinity, and nutrients measured at fixed stations. These are the richest source for building the full multi-decadal DO time series used as the target variable in the Random Forest model. When reading these files, standardize column names to: Station, Year, Month, Depth, DO_mgL, Temp_C, Salinity_PSU. Filter to bottom-layer observations only.

---

## Why These ML Methods and Not LSTM

The original pipeline proposed using an LSTM (recurrent neural network) for temporal DO prediction. After reviewing the data structure this was rejected for three reasons. First, the sediment dataset does not sample the same fixed stations every year — sampling locations shift, so there is no consistent entity tracked through time and any sequence the LSTM would learn would be noise rather than signal. Second, with only two time points per year (summer and winter) across 33 years, the effective training set after splitting is around 40 sequences, which is far too small for LSTM to learn without severe overfitting. Third, the sediment data has no direct DO measurement, only proxy variables, adding an extra layer of assumed spatial correspondence that would compound errors in a deep learning model.

The replacement pipeline uses K-means clustering followed by Random Forest. This choice is well-supported by recent peer-reviewed literature. Millot et al. (2025) used K-means clustering combined with Random Forest modelling to group Mediterranean soft-bottom sites by biotic composition and predict their distribution from environmental variables, reporting strong predictive performance. Frontiers in Marine Science (2025) published a hybrid unsupervised-supervised pipeline using clustering for community state identification followed by supervised classification, finding that DO, depth, ORP, and sediment organic content were the most important structuring features. Random Forest has been shown to achieve 89 to 94 percent accuracy in hypoxia classification in coastal lagoons (ScienceDirect 2021, 2024) and outperforms LSTM on small ecological datasets because it requires no sequence structure, handles missing data natively, and provides interpretable feature importance through SHAP values. For the Seto Inland Sea specifically, Random Forest has already been validated for predicting water quality variables from commonly measured parameters in a 2025 Journal of Oceanography study on pCO2 estimation using SIS Comprehensive Water Quality Survey data — the same data infrastructure you are using.

---

## Analysis Pipeline

### Step 1 — Environmental Characterization and Hypoxia Zone Identification

This step reproduces Figure 3 and Figure 2 of the original paper.

Using fixed_line_survey_long_hiroshima.csv, filter to Depth == Bottom rows. For each station and month compute bottom DO, bottom temperature, and bottom salinity. Then compute the surface-to-bottom temperature difference per station-month by subtracting the bottom temperature from the 0m temperature row for the same station and month. This is your stratification index. A value greater than 3 degrees Celsius indicates a strong thermocline.

Classify each station-month as one of four oxygen regimes: normoxic (DO > 4 mg/L), moderate stress (2 < DO ≤ 4 mg/L), hypoxic (DO ≤ 2 mg/L), severely hypoxic (DO ≤ 1 mg/L). Flag any station-month with DO ≤ 2 in any summer month (6 to 9) as a hypoxic site for downstream analysis.

Compute Spearman correlations between bottom DO and each of: bottom temperature, bottom salinity, station nominal depth from station_meta.csv, and the stratification index. Report correlation coefficients and p-values in a matrix equivalent to Figure 2 of the original paper. Expected direction: bottom DO negatively correlated with depth (deeper = less mixing = lower DO) and negatively correlated with stratification index (stronger thermocline = worse hypoxia).

For Osaka, compute stratification index from fixed_line_survey_long_osaka.csv using surface-minus-bottom temperature difference. Correlate with station depth to confirm that deeper stations have stronger stratification, consistent with hypoxia risk.

*Data Limitations & Methodological Weaknesses:*
- **Hiroshima Station ID Mismatch & Missing Coordinates:** The file `station_meta.csv` contains coordinates and nominal depths *only* for the 20 Osaka Bay stations. Hiroshima Bay stations (which go up to ID 38 in `fixed_line_survey_long_hiroshima.csv`) have no metadata in `station_meta.csv`. Attempting to merge Hiroshima data with `station_meta.csv` by ID will assign incorrect Osaka coordinates and depths to Hiroshima stations. Hiroshima coordinates must instead be parsed directly from Row 1 of `587628.pdf` (which the current script ignores).
- **Proxy DO for Osaka:** The Osaka dataset lacks direct DO measurements, forcing the use of temperature-based stratification index as a proxy. This proxy limits direct biological validation.

---

### Step 2 — K-Means Clustering for Site Regime Classification

This step replaces the NMDS ordination and PERMANOVA from the original paper with a validated unsupervised machine learning approach that produces actionable cluster labels rather than just a visualization.

Build the feature matrix with one row per station-month observation. Features are: bottom DO, bottom temperature, bottom salinity, station nominal depth, stratification index (surface minus bottom temperature), month encoded cyclically as sine and cosine of month times 2π divided by 12 so that January and December are adjacent in feature space, and optionally sediment TOC and sulfides from bottom_2023.xlsx matched to the nearest station by decimal-degree coordinates and season.

Standardize all features to zero mean and unit variance before clustering. K-means is distance-based and sensitive to scale differences between variables.

Run K-means for K equal to 2 through 6. For each K compute the within-cluster sum of squares for the elbow plot and the silhouette score. Select the K with the highest average silhouette score. Expect K = 2 or K = 3 to be optimal, corresponding to hypoxic versus normoxic or hypoxic versus transitional versus normoxic regimes.

Validate by cross-tabulating cluster assignments against the hypoxia flag (DO ≤ 2 yes or no). A good clustering should recover the hypoxia threshold with high agreement. Report cluster centroids in the original unstandardized feature space so they are ecologically interpretable, for example Cluster A has mean DO of 1.4 mg/L, mean depth of 45 m, mean stratification index of 5.2 degrees Celsius.

This is the equivalent of the original paper's PERMANOVA result which found R² = 0.10, p = 0.003 showing significant community separation between hypoxic and normoxic zones.

*Data Limitations & Methodological Weaknesses:*
- **Missing Sediment Chemistry for Osaka & Hyogo:** The sediment survey (`bottom_2023.xlsx`) only covers prefectures `[34, 35, 38, 44]` (Hiroshima, Yamaguchi, Ehime, Oita). There is no sediment data (TOC, sulfides) for Osaka Bay (prefecture 27) or Harima Nada (prefecture 28) in this dataset, preventing their inclusion in the clustering feature set for these regions.
- **Coordinate-based Alignment Constraint:** Nearest-neighbor spatial matching of sediment data to water column observations is blocked for Hiroshima Bay until station coordinates are extracted from the Hiroshima survey PDF.

---

### Step 3 — Benthic Diversity Indices and GAM Analysis

This step reproduces Table S3 and Figures 6 and 7 of the original paper.

Build a species-by-station abundance matrix from the benthic macrofauna dataset. Compute the following diversity indices per station per season: Shannon index H prime equals negative sum of pi times log of pi where pi is the relative abundance of species i, Simpson index as 1 minus sum of pi squared, Margalef richness as S minus 1 divided by the natural log of N where S is species count and N is total individuals, and Pielou evenness as H prime divided by the natural log of S.

Join each station-season diversity value with the corresponding bottom DO value from the Hiroshima fixed-line data or the multi-year SIS environmental data, matching by station identifier, year, and season.

Run Generalized Additive Models with each diversity index as the response and bottom DO as the smooth predictor term using a cubic spline with 3 to 5 degrees of freedom. Run the GAMs twice: once for all stations and once for hypoxic stations only (bottom DO ≤ 2 mg/L in that season). This directly replicates Figure 6.

Also compute Spearman correlations between each diversity index and each environmental variable (DO, temperature, salinity, depth, stratification index, sediment TOC if available). Present as a heatmap with significance stars, equivalent to Figure 7. Run separately for all stations and for hypoxic stations only.

Expected results consistent with the original paper: within hypoxic stations, Shannon, Simpson, and Margalef all show significant positive correlation with DO (original paper found r = 0.77, 0.73, and 0.67 respectively). Functional divergence index FDiv is expected to decrease with increasing DO in the hypoxic zone, indicating that low-DO conditions select for functionally divergent stress specialists while higher DO allows generalist return and trait homogenization.

*Data Limitations & Methodological Weaknesses:*
- **Complex & Erroneous Benthos Formatting:** `benthos_2023.xlsx` is structured in a wide format with up to 62 species columns per sample (`学名1`, `和名1`, `個体数1`, `湿重量1` etc.). It contains row-shift errors (rows 569, 605), date typos (`2109` year at row 1252), and non-numeric abundance markers (e.g. `+`, `＋`, `G` indicating presence) that require custom preprocessing and melting to a long format before diversity metrics can be computed.
- **Incomplete Spatial Overlap:** Benthos and sediment datasets only overlap in Hiroshima, Yamaguchi, and Ehime (821 samples, 72.6% of benthos samples). Benthos stations in Osaka or Hyogo cannot be merged with sediment chemistry data, though they can be linked to water-column physical parameters in `merged_gdf.feather`.

---

### Step 4 — Mantel Test for Community-Environment Correlation

This step reproduces Figure 9 of the original paper.

Compute a Bray-Curtis dissimilarity matrix between all pairs of stations based on benthic species relative abundances. Compute Euclidean distance matrices for each environmental variable separately: DO, temperature, salinity, depth, and stratification index.

Run Spearman-based Mantel tests between the community dissimilarity matrix and each environmental distance matrix using 999 permutations. Run for all stations and for hypoxic stations only.

Report Mantel r and p-value for each variable in both subsets. Expected result mirroring the original paper: DO has a significantly stronger Mantel r inside the hypoxic zone than across all stations, confirming that DO is the primary structuring force under hypoxic conditions while depth, temperature, and salinity act as secondary filters. The original paper found Mantel r = 0.36, p = 0.011 for DO in the hypoxic zone.

*Data Limitations & Methodological Weaknesses:*
- **Overlapping Station Constraints:** The Mantel test requires concurrent community and environmental distance matrices. Only 59 of the 95 unique benthos stations (62.1%) overlap with the water quality observation stations in `merged_gdf.feather`, reducing the sample size and spatial coverage for the analysis.

---

### Step 5 — Random Forest for Hypoxia Prediction and Driver Identification

This step is the novel machine learning contribution that extends beyond the original paper's scope and is justified by the published literature on RF-based hypoxia prediction in coastal systems.

The scientific question is: given the sediment condition (organic load, redox state, sulfide accumulation) and basic environmental context (depth, season, year), can you predict whether a location will experience hypoxic conditions? This operationalizes the paper's causal narrative — that benthic oxygen demand from sediment decomposition drives bottom DO depletion — into a predictive model.

Build the feature matrix from bottom_2023.xlsx using summer observations. Features per observation are: TOC, sulfides, ORP, COD, loss on ignition (強熱減量), clay fraction (粘土分), water depth (水深), month, year, and sea area code. Target variable is binary: hypoxic (summer DO ≤ 2 mg/L at that location) or normoxic. Where direct DO measurements are available from the SIS environmental folders for matching station coordinates and year, use those as ground truth labels. Where DO is not directly available, use ORP less than negative 100 mV AND sulfides greater than 0.2 mg/g AND LOI greater than 5 percent as a composite hypoxia-risk label, which is ecologically validated for anoxic sediment conditions.

Split data into training (1991 to 2010), validation (2011 to 2017), and test (2018 to 2024) sets. This temporal split is important — do not use random splitting because it would allow future sediment conditions to inform past predictions, leaking information across time.

Train a Random Forest classifier with 200 to 500 trees, max depth of 10 to 15, and minimum samples per leaf of 5 to prevent overfitting on the small dataset. Tune hyperparameters using the validation set. Evaluate on the test set using accuracy, AUC-ROC, F1 score, and confusion matrix. Based on published results from similar coastal systems, expect accuracy of 85 to 94 percent.

Compute SHAP (SHapley Additive exPlanations) values for each feature to produce an interpretable feature importance ranking. Expected top predictors consistent with the literature and with the original paper's narrative: TOC and sulfides will be the strongest predictors because they represent accumulated organic oxygen demand, followed by ORP (redox state), water depth (stratification susceptibility), and year (long-term eutrophication trend).

Plot SHAP summary plot showing mean absolute SHAP value per feature. Plot SHAP dependence plots for TOC versus hypoxia probability and sulfides versus hypoxia probability to show the nonlinear threshold relationships.

Also run Random Forest as a regressor predicting continuous summer bottom DO rather than binary hypoxia class. Report RMSE and R² on the test set.

*Data Limitations & Methodological Weaknesses:*
- **Data Leakage & Circular Logic (Critical Risk):** Defining the hypoxia target using a sediment-based composite proxy (`ORP < -100 mV AND sulfides > 0.2 mg/g AND LOI > 5%`) while using these same variables as model features will cause severe data leakage. The model will achieve a deceptively high classification accuracy (99%+) by memorizing this logical rule rather than predicting actual water-column DO. To avoid this, direct bottom DO labels from the water quality database (`merged_gdf.feather`) must be matched spatially and temporally to the sediment samples.
- **Temporal Alignment Loss:** Due to differences in survey frequency (semi-annual sediment surveys vs. monthly water quality profiles) and shifting station locations, matching by exact coordinates and date will cause significant data loss.

---

### Step 6 — Long-Term Trend Analysis

This step uses your unique multi-decadal data advantage — something the original paper, based on a single survey, could not do.

Using the bottom_2023.xlsx sediment data from 1991 to 2024, run Mann-Kendall trend tests on the following annual summer means per sea area: TOC, sulfides, ORP, COD, and loss on ignition. Mann-Kendall is a non-parametric monotonic trend test that is standard in long-term fisheries and environmental monitoring studies in Japan and directly comparable to what SIS management agencies report.

The Seto Inland Sea has been subject to nutrient load regulations since the 1970s and strengthened again in the 2000s. Expect a long-term improvement signal (declining TOC, improving ORP, lower sulfides) in regulated sea areas like Osaka Bay, and potentially a stagnation or worsening trend in less regulated outer areas. Report Sen's slope (the rate of change per year) alongside the Mann-Kendall tau and p-value.

Cross-reference these sediment trends with the Random Forest feature importance output. If TOC is the top predictor of hypoxia and TOC shows a significant declining trend since 2000, this provides a mechanistic explanation for any observed recovery of benthic communities in the same period — directly connecting your ML model outputs to the ecological narrative.

*Data Limitations & Methodological Weaknesses:*
- **Geographic Bias of Trends:** Since the sediment monitoring dataset (`bottom_2023.xlsx`) only contains data for prefectures 34, 35, 38, and 44, the long-term trend analysis will be biased toward the western and central regions of the Seto Inland Sea. It cannot represent the eastern regions (Osaka Bay and Harima Nada), making it impossible to evaluate long-term sediment oxygen demand trends in the highly urbanized Osaka Bay using this dataset.

---

### Step 7 — Synthesis Table

After completing all steps produce the following comparison table between your study and the original paper:

| Analysis element | Original paper Pearl River Estuary | This study Seto Inland Sea |
|---|---|---|
| Study system | Subtropical Chinese estuary | Semi-enclosed Japanese inland sea |
| Survey type | Single July 2021 trawl survey | Multi-decadal fixed-line monitoring 1991 to 2024 |
| Community studied | Demersal fish 104 species | Benthic macrofauna report your species count |
| Hypoxia prevalence | 11 of 24 sites hypoxic | Report your result |
| Primary DO driver | Thermal stratification | Thermal stratification plus sediment oxygen demand |
| Shannon versus DO all sites | No significant correlation | Report your result |
| Shannon versus DO hypoxic only | r = 0.77 p = 0.006 | Report your result |
| FDiv versus DO direction | Negative decreases with DO | Report your result |
| Mantel DO hypoxic only | r = 0.36 p = 0.011 | Report your result |
| Temporal trend capability | None single snapshot | Mann-Kendall 33 years |
| ML method | None traditional statistics only | K-means clustering plus Random Forest with SHAP |
| Hypoxia prediction accuracy | Not applicable | Report AUC and F1 |

Discuss differences in terms of ecosystem type, taxonomic group, data resolution, and geographic scale. Emphasize that using benthos instead of fish strengthens the DO-community relationship because benthos cannot migrate away from hypoxic zones, making them more reliable indicators of chronic oxygen stress.

---

## Key Thresholds and Definitions

Use these consistently throughout the paper:

Normoxic: DO greater than 4 mg/L. Moderate stress: DO between 2 and 4 mg/L. Hypoxic: DO at or below 2 mg/L. Severely hypoxic: DO at or below 1 mg/L. Near-anoxic: DO at or below 0.5 mg/L.

Summer hypoxia season in the Seto Inland Sea: June through September (months 6 to 9). Peak hypoxia typically in August. Hypoxia begins in May and dissipates in autumn with cooling and storm-driven mixing.

Hypoxic sediment indicators: ORP below negative 100 mV, sulfides above 0.2 mg/g, loss on ignition above 5 percent, COD above 10 mg/g.

---

## Literature the AI Should Be Aware Of

Lai et al. 2024 Ecology and Evolution is the direct template paper. The full citation is in the header of this document.

Millot et al. 2025 used K-means clustering combined with Random Forest to partition Mediterranean soft-bottom sites into megabenthic community types from environmental variables — this is the closest methodological precedent for Steps 2 and 5.

Frontiers in Marine Science 2025 published a hybrid unsupervised-supervised ML pipeline for marine ecological communities finding DO, depth, ORP, and sediment organic content as top structuring features — validates the feature set used in Step 5.

ScienceDirect 2021 and 2024 published Random Forest hypoxia classification in coastal lagoons achieving 89 to 94 percent accuracy — sets the expected performance benchmark for Step 5.

Journal of Oceanography 2025 validated Random Forest for water quality estimation specifically in the Seto Inland Sea using the Comprehensive Water Quality Survey data — the same data infrastructure used in this study.

Breitburg et al. 2018 Science provides global context on coastal hypoxia expansion since 1950 — cite in the introduction.

Vaquer-Sunyer and Duarte 2008 established that fish are among the most sensitive marine organisms to hypoxia — explains why the original paper focused on fish and why benthos are an equally valid and arguably stronger signal.

---

## Expected Final Outputs

Map of bottom DO distribution across Hiroshima Bay stations by month with hypoxic zones highlighted.

Spearman correlation matrix of bottom environmental variables equivalent to Figure 2 of the original paper.

Elbow plot and silhouette score plot for K-means cluster selection, followed by a scatter plot of cluster assignments in DO-temperature-depth space.

Cross-tabulation table of K-means clusters versus hypoxia flag showing classification agreement.

GAM plots of Shannon, Simpson, Margalef, Pielou, and FDiv versus bottom DO for all stations and hypoxic stations separately equivalent to Figure 6.

Heatmap of Spearman correlations between diversity indices and environmental variables for all stations and hypoxic stations separately equivalent to Figure 7.

Mantel test results table equivalent to Figure 9.

Random Forest confusion matrix, AUC-ROC curve, and SHAP summary plot.

Mann-Kendall trend plots for TOC, sulfides, and ORP per sea area from 1991 to 2024.

Synthesis comparison table between this study and the original PRE paper.