# Workspace Evaluation Report: Adoption of V2 Columns

**Date:** 2026-04-14
**Context:** Analysis of new Tokyo & Ise Bay environmental dataset properties (`37_Tokyo_Ise_Bay_add_a.ipynb`)

## Finding Summary

During a review of the regional dataset features, a dual-column pattern was observed for major water quality parameters. For several original variables (e.g., `do_`, `ph`, `salt`, `cod`, `nh4n`, `tn`, `tp`), a secondary "V2" variant exists ending in a "2" (e.g., `do_2`, `ph2`, `salt2`, etc.).

### Quality Discrepancies
1. **Data Types**: The primary columns are often string/object arrays, whereas their V2 counterparts have been preemptively cast to `float64` natively. This eliminates potential edge-case errors parsing complex invalid entries during python coercion.
2. **Completeness**: The V2 columns boast higher `non-null` counts in almost all standard cases. 
    - E.g., `do_` has 65,266 records vs `do_2` with 65,643 records. 
    - This provides an additional ~377 high-quality observation points out-of-the-box for Dissolved Oxygen.

## Pipeline Adjustments

To address this cleanly without causing cascading namespace breakage throughout the DVC workflow:

- `scripts/data_loader.py` was updated with a dynamic alias-resolution algorithm inside `clean_and_process_data()`.
- During raw data ingestion, if the pipeline detects an alternate "2" pattern column that verifies as strictly numeric and possesses equal or greater complete observations, it **overrides the values in the primary column**.
- As a result, the standard variable `do_` now inherits the superior quality dataset natively encoded in `do_2`. 

### Expected Impact
- All historical and downstream modeling relying on `yearly_do_df.csv` now implicitly processes `float64` `do_2` data.
- Pipeline metadata and documentation have been updated to acknowledge this silent feature upgrading mechanism natively handled within the codebase.
