# Report: Handling of Missing Data (0.0 vs NaN) in the Data Loader

**Date:** 2026-10-04
**Context:** Investigation into the artificial `0.0` values populating downstream analysis and their origin in the `data_loader.py` script.

## 1. The True Nature of the Raw Data
A previous workspace evaluation (`workspace_evaluation_report_041426(2).md`) identified a dual-column pattern in the raw environmental shapefiles (e.g., `doc` vs `doc2`, `salt` vs `salt2`). The report concluded that the "V2" columns were of higher quality because they were natively cast as `float64` and boasted significantly higher completeness (`non-null` counts).

However, an in-depth investigation into the raw shapefiles reveals that this completeness is a **mathematical illusion**:
* **Primary Columns (e.g., `doc`, `salt`)**: Stored as strings/objects. Missing data is correctly recorded as `None` or empty strings.
* **V2 Columns (e.g., `doc2`, `salt2`)**: Stored natively as floats, but **missing data is universally encoded as exactly `0.0`**. Additionally, for censored nutrient data, these columns use hardcoded numbers (e.g., `0.01`) as **Limit of Detection (LOD)** placeholders instead of standard blank/NaN records.

Because `0.0` and `0.01` are valid floating-point numbers, pandas does not register them as null values.
## 2. The Flaw in the Data Loader Script
In `utils/data_loader.py`, the `clean_and_process_data()` function executes the following algorithm to "upgrade" variables to their V2 counterparts:
```python
base_valid = gdf[base_col].notna().sum()
v2_valid = gdf[col].notna().sum()
if v2_valid >= base_valid:
    gdf[base_col] = gdf[col]
```
By relying solely on `.notna().sum()`, the script falls into a trap. For example, Dissolved Organic Carbon (DOC) has roughly 24,000 true measurements. The remaining ~38,000 records are missing. 
- The `doc` column correctly yields ~24,000 `notna()` counts.
- The `doc2` column registers ~62,000 `notna()` counts (because the 38,000 missing values are saved as `0.0`).

The script determines `doc2` is the superior dataset and completely overwrites `doc` with it, thereby injecting 38,000 artificial zero values into the central pipeline database (`merged_gdf.feather`).

## 3. Impact on Downstream Pipeline Operations
Because missing values are explicitly encoded as `0.0`, they successfully bypass all data-cleaning safeguards in the pipeline:

* **Step 1 (Seasonal Subsets):** In `process02_create_seasonal_subset.py`, the command `subset.dropna(subset=[param])` is used to filter out invalid records before aggregating yearly means. This fails because `0.0` is not dropped.
* **Steps 5 & 6 (Correlation Analysis):** Scripts like `process42` and `process01` rely on `.dropna()` to align the valid years of environmental parameters against the Principal Component (PC) scores. The artificial zeroes are retained. When calculating the Pearson correlation, these `0.0`s pull the statistical mean down exponentially and introduce massive false variance, resulting in highly skewed (and incorrect) correlations.
* **Time Series Visualization:** The plotting functions faithfully render the data they are given, resulting in flatlines at `0.0` for decades where data was never measured, or violent zigzagging when missing data is interpolated with real measurements.

## 4. Suggestions for Pipeline Optimization
The previous implementation plan proposed a "patch" to sweep through the dataset and convert `0.0` back to `NaN`, followed by a complex spatial interpolation. This is highly inefficient because we are writing code to reverse a bug caused by our own data loader. 

To optimize the pipeline, we should fix the root cause. 

### Optimization 1: Rethink V2 Column Adoption
The primary reason the V2 columns were adopted was to avoid "edge-case errors parsing complex invalid entries during python coercion" from the primary string columns. 

However, `pandas` has a built-in, highly optimized function for this exact scenario: `pd.to_numeric(..., errors='coerce')`. This function safely forces strings into floats and natively converts unparseable strings, empty strings, and `None` directly into `NaN`. 
* **Suggestion:** We should consider abandoning the V2 column swap entirely for parameters where `0.0` is used as a placeholder. We can simply apply `pd.to_numeric(errors='coerce')` to the primary columns. This elegantly preserves the true missing data gaps as `NaN` without any custom zero-hunting logic.

### Optimization 2: Sequence of NaN Conversion
If the V2 columns *must* be retained (e.g., if the primary columns are deeply corrupted), the `0.0 -> np.nan` conversion must be injected **before** the `.notna()` validity test in `data_loader.py`. 
* **Suggestion:** Before comparing `base_valid` and `v2_valid`, the script must explicitly scrub `0.0` from the V2 column. This will reveal its true completeness count, and only then should the algorithm decide if it is truly a superior dataset to inherit.

### Optimization 3: Streamlining Downstream Steps
By handling the `NaN` generation correctly at the absolute beginning of the pipeline (`utils/data_loader.py`), we completely optimize the downstream workflow. 
* We no longer need to write custom interpolation scripts to fill in artificial gaps.
* The existing `.dropna()` commands scattered across Step 1, Step 5, and Step 6 will immediately begin functioning exactly as they were originally designed, filtering out invalid years naturally. 
* This drastically reduces the computational overhead and cognitive complexity of the pipeline.
