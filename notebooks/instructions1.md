**Decorrelation analysis : Part 2**

I need you to perform a **Spatial Autocorrelation Analysis** to determine the "Decorrelation Scale" of Dissolved Oxygen (DO) concentrations in the Seto Inland Sea.

**1. The Data**
I have the following variables already loaded in my Python environment (from `07_Decorrelation_Analysis_v2.ipynb`):

* `yearly_do_df`: A DataFrame where **rows are Station IDs** and **columns are Years**. It contains yearly average DO concentration values.
* `dist_matrix_km`: A square DataFrame (127x127) containing the pairwise Euclidean distances (in km) between all stations.

**2. The Analytical Method**
You must calculate the **Length Scale of Synchrony** for *each* station individually using a "Spatial Lag" approach.

* **Metric:** Use the pre-calculated **`dist_matrix_km`**.
* **Algorithm:**
For every Station $i$:
1. Iterate through distance lags $d$ in **12 km steps** (e.g., 0-12km, 12-24km, etc.).
2. Identify all neighbor stations $j$ that fall within the current distance bin using `dist_matrix_km`.
3. Calculate the **Spatial Lag Time Series**: The average time series of those neighbors.
4. Calculate the **Pearson Correlation ($r$)** between Station $i$'s time series and the Spatial Lag Time Series.
5. **Stop Rule:** The first distance bin where $r < 0.05$ is the **Decorrelation Scale** for that station.



**3. Analysis Constraints**

* **Lag Interval:** 12 km (based on median nearest neighbor distance).
* **Correlation Cutoff:** 0.05.
* **Missing Data:** Handle `NaN` values by using `np.nanmean` and ensuring pairs are only correlated if they have at least 5 years of overlapping data.

**4. Required Output**
Please write a Python script (using `pandas`, `numpy`, and `matplotlib`) that produces:

1. **A Results DataFrame:** Columns should be `[Station_ID, Lat, Lon, Decorrelation_Scale_km]`. (Note: use `station_locs` for Lat/Lon).
2. **A Dashboard Visualization** containing three subplots:
   * **Map:** A scatter plot of stations colored by their Decorrelation Scale.
   * **Histogram:** The distribution of scales across all stations.
   * **Correlogram:** A plot showing the average correlation decay curve (Mean $r$ vs Distance) with a standard deviation shadow.



---

### Next Steps for You

Please implement the logic above using the variables `yearly_do_df`, `dist_matrix_km`, and `station_locs` which are already available in the notebook context.
