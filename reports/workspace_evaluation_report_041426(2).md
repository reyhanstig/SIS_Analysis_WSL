# Workspace Evaluation Report: Adoption of V2 Columns

**Date:** 2026-04-14
**Context:** Analysis of new Tokyo & Ise Bay environmental dataset properties (`37_Tokyo_Ise_Bay_add_a.ipynb`)

## Finding Summary

During a review of the regional dataset features, a dual-column pattern was observed for major water quality parameters. For several original variables (e.g., `do_`, `ph`, `salt`, `cod`, `nh4n`, `tn`, `tp`), a secondary "V2" variant exists ending in a "2" (e.g., `do_2`, `ph2`, `salt2`, etc.).

### Quality Discrepancies
1. **Data Types**: The primary columns are often string/object arrays, whereas their V2 counterparts (suffixed with `2` or `_1`) have been preemptively cast to `float64` natively. This eliminates potential edge-case errors parsing complex invalid entries during python coercion.
2. **Completeness**: The high-quality columns boast higher `non-null` counts in almost all standard cases. 
    - **Dissolved Oxygen**: `do_` has 65,266 records vs `do_2` with 65,643 records (+377 points).
    - **Chlorophyll-a**: `chlorophyl` has 41,620 records vs `chloroph_1` with 42,326 records (+706 points).

## Pipeline Adjustments

To address this cleanly without causing cascading namespace breakage throughout the DVC workflow:

- `scripts/data_loader.py` was updated with a dynamic alias-resolution algorithm inside `clean_and_process_data()`.
- During raw data ingestion, if the pipeline detects an alternate "2" or "_1" pattern column that verifies as strictly numeric and possesses equal or greater complete observations, it **overrides the values in the primary column**.
- As a result, standard variables like `do_` and `chlorophyl` now inherit the superior quality dataset natively encoded in `do_2` and `chloroph_1` respectively. 

### Expected Impact
- All historical and downstream modeling relying on `yearly_do_df.csv` now implicitly processes `float64` `do_2` data.
- Pipeline metadata and documentation have been updated to acknowledge this silent feature upgrading mechanism natively handled within the codebase.
