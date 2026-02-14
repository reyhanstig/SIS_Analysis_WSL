Here is the summarized instruction for the **Distance-Decay Gaussian Fitting** method. You can copy and paste this directly to another AI (like ChatGPT or Claude) to generate the Python code.

---

# Instruction: Perform Spatial Decorrelation Analysis (Gaussian Fitting Method)

I need you to perform a spatial analysis on Dissolved Oxygen (DO) time series data to determine the "Decorrelation Scale" for individual sampling stations.

### 1. Input Data

Assume the existence of two pandas DataFrames:

1. **`yearly_do.csv`**: A time-series matrix where rows represent Years and columns represent Station IDs.
2. **`station_coordinates.csv`**: Contains geographic locations with columns `Station_ID`, `Lat`, and `Lon`.

### 2. Methodology

Instead of spatial binning, you must perform a **Distance-Decay Curve Fitting** for each station individually.

**For each Target Station ():**

1. **Calculate Pairwise Correlations:**
* Calculate the Pearson correlation coefficient () between the Target Station's time series and **every other station's** time series.
* Calculate the Haversine distance () between the Target Station and each comparison station.
* *Result:* A scatter cloud of data points  representing how correlation decays with distance from this specific station.


2. **Fit a Gaussian Model:**
* Fit a Gaussian decay curve to this scatter cloud using the equation:


* **Constraint:** Fix the amplitude to 1.0 (since correlation at distance 0 is always 1). Optimize only for the parameter  (Length Scale).


3. **Determine Significance Threshold:**
* Calculate the critical correlation value () that corresponds to a p-value of **0.01** (), based on the number of overlapping years () in the time series.


4. **Calculate Decorrelation Scale:**
* Solve the fitted Gaussian equation to find the exact distance  where the curve drops below .
* Formula to solve:





### 3. Implementation Details (Python)

* **Libraries:** Use `pandas`, `numpy`, `scipy.optimize` (for `curve_fit`), and `scipy.stats`.
* **Missing Data:** Use pairwise deletion. When calculating correlation between two stations, only include years where both have valid data.
* **Constraint:** Require a minimum of **15 years of overlap** to accept a pairwise correlation. If overlap < 15, ignore that pair.
* **Optimization:** Use bounds for `curve_fit` to ensure  is positive.

### 4. Required Output

Generate a script that produces a DataFrame with the following columns:

* `Station_ID`
* `Lat`
* `Lon`
* `Decorrelation_Scale_km` (The calculated distance where )
* `Gaussian_L_Param` (The fitted parameter )

---

Here is the summarized instruction for the Distance-Decay Gaussian Fitting method. You can copy and paste this directly to another AI (like ChatGPT or Claude) to generate the Python code.Instruction: Perform Spatial Decorrelation Analysis (Gaussian Fitting Method)I need you to perform a spatial analysis on Dissolved Oxygen (DO) time series data to determine the "Decorrelation Scale" for individual sampling stations.1. Input DataAssume the existence of two pandas DataFrames:yearly_do.csv: A time-series matrix where rows represent Years and columns represent Station IDs.station_coordinates.csv: Contains geographic locations with columns Station_ID, Lat, and Lon.2. MethodologyInstead of spatial binning, you must perform a Distance-Decay Curve Fitting for each station individually.For each Target Station ($S_{target}$):Calculate Pairwise Correlations:Calculate the Pearson correlation coefficient ($r$) between the Target Station's time series and every other station's time series.Calculate the Haversine distance ($d$) between the Target Station and each comparison station.Result: A scatter cloud of data points $(d, r)$ representing how correlation decays with distance from this specific station.Fit a Gaussian Model:Fit a Gaussian decay curve to this scatter cloud using the equation:$$r(d) = \exp\left(-\left(\frac{d}{L}\right)^2\right)$$Constraint: Fix the amplitude to 1.0 (since correlation at distance 0 is always 1). Optimize only for the parameter $L$ (Length Scale).Determine Significance Threshold:Calculate the critical correlation value ($r_{crit}$) that corresponds to a p-value of 0.01 ($p < 0.01$), based on the number of overlapping years ($N$) in the time series.Calculate Decorrelation Scale:Solve the fitted Gaussian equation to find the exact distance $d$ where the curve drops below $r_{crit}$.Formula to solve:$$d_{scale} = L \cdot \sqrt{-\ln(r_{crit})}$$3. Implementation Details (Python)Libraries: Use pandas, numpy, scipy.optimize (for curve_fit), and scipy.stats.Missing Data: Use pairwise deletion. When calculating correlation between two stations, only include years where both have valid data.Constraint: Require a minimum of 15 years of overlap to accept a pairwise correlation. If overlap < 15, ignore that pair.Optimization: Use bounds for curve_fit to ensure $L$ is positive.4. Required OutputGenerate a script that produces a DataFrame with the following columns:Station_IDLatLonDecorrelation_Scale_km (The calculated distance where $r < r_{crit}$)Gaussian_L_Param (The fitted parameter $L$)