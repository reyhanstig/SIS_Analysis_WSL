# Step 5 Region-Specific PC Correlation Fix Report

## Overview

`process41_spatial_correlation_maps.py` maps, for each station, the correlation between a PC score series (PC1 or PC2 of summer bottom DO) and an environmental or nutrient series. Step 5 mapped three watermasses (Seto Inland Sea, Tokyo Bay, Ise Bay), but the correlations for all three were computed against **one** PC: the Seto Inland Sea PCA. The Tokyo Bay and Ise Bay maps therefore did not describe those bays.

This report covers the audit of the original maps, the root cause, the fix, and the results after re-running step 5 for the Summer/bottom DO subset. The earlier audit was shared as an HTML page; this document supersedes it for the Tokyo Bay and Ise Bay findings.

## Findings (before the fix)

All numbers are for the Summer/bottom DO subset, 1982-2023.

**1. Wrong PC for the bays.**
- `process01_data_integrity_and_correlation.py` read one `pca_scores.csv` from `data/processed/seasonal/summer_bottom/`. That file is the Seto PCA (124 Seto stations; no Tokyo or Ise stations).
- For all 28 Tokyo Bay and 33 Ise Bay stations, the stored correlation equalled the correlation with the Seto PC1 (difference 0.0). Against each bay's own PC1 the values differed by up to 0.57 (Tokyo) and 0.65 (Ise).
- The bay PC1s are different modes from the Seto PC1 (r = -0.09 with Tokyo Bay, -0.40 with Ise Bay).
- `process42` already plotted each bay's own PC but coloured stations by the Seto-based correlations, so its plots and the `process41` maps disagreed.

**2. The Seto PC1 is mostly a long-term trend.**
- Seto PC1 correlates with year at r = 0.81 (lag-1 autocorrelation 0.72) and tracks Seto mean bottom DO (r = 0.77).
- A station's correlation with PC1 was almost fully predicted by how strongly that variable trends over time (Spearman 0.93-0.96 in all three regions).
- After linear detrending, the strongest maps (TN, winter water temperature) fell to roughly chance level. Water temperature correlated positively with DO only because both rise over the period.
- One signal survived detrending in Seto: year-to-year changes in summer surface salinity correlated positively with PC1 at 52 % of Seto stations (same sign everywhere). The matching Ise Bay result (55 %) in the earlier audit was computed against the Seto PC1 and is **not** carried over.

**3. PC2 is not a stable mode.** In Seto, PC2 explains 8.9 % (about ±2.0 % by North's rule) and cannot be separated from PC3 (8.0 %). Seto PC2 maps average 10-11 % significant stations against 5 % expected by chance.

**4. Other problems around process41 (not changed by this fix).**
- `process43` regresses the PC on the mean of stations already selected for p ≤ 0.05, so its significance is partly circular.
- Stratification is defined two ways: `process01` uses Δσ₀/Δdepth (kg/m⁴), `process42/43` use Δσ₀ only (kg/m³).
- DIP and PO4-P are identical variables and produce duplicate maps.
- `process41` hard-codes absolute output paths.
- Significance counts treat stations and years as independent. Neither is true (autocorrelated years, spatially correlated stations).

## Root cause

1. `process01` had no notion of region: it correlated every station in the data with the single Seto `pca_scores.csv`, and wrote one correlation file per season/layer.
2. All consumers (`process12`, `31`, `32`, `33`, `41`, `42`, `43`) only filtered stations by region afterwards.
3. Separately, the per-bay PCs from step 4 `process11` mean-fill years without DO observations, so those years carry a placeholder score of about 0 (for example 1e-15 in Tokyo Bay 1981 and 1982). Correlating against them would have mixed meaningless points into the results.

## Fix details

**`utils/paths.py`** (new `ProjectPaths` helpers, reusing `get_subset_dir`):
- `region_slug(region)`
- `get_corr_file(season, layer, region, data_type, pc_name)` -> `data/processed/seasonal/<season>_<layer>/<region_slug>/pca_<env|nutr>_corr_<pc>.csv`
- `get_region_pc_scores_path` / `get_region_pc_scores`: Seto uses the Seto-wide `pca_scores.csv`; other regions use the step 4 per-bay file `process11_..._per_bay_raw/<slug>/pca_scores_<slug>.csv`
- `get_region_pc_used_file`: the exact (masked) PC series that `process01` correlated
- `get_region_loadings`: Seto `pca_loadings.csv`, or the per-bay `eof_patterns`
- `mask_unobserved_years`: sets PC rows to NaN for years where fewer than `min_stations` of the region's stations have a DO value

**`step5_parameter.csv`**: new `pc_min_do_stations` (default 3).

**`process01_data_integrity_and_correlation.py`**: new required `--target_region`. It loads that region's PC, masks unobserved years, restricts the data to the region's stations, writes the four correlation CSVs plus `pc_scores_used.csv` into `<region_slug>/` (wiping only that folder first), and exits with a warning if the PC file is missing. The integrity report filename now includes the region slug. `calculate_station_correlations` and `min_periods` (15) are unchanged.

**`main.py`**: `process01` now runs inside the region loop. If it produced no output for a region, that region is skipped with a warning.

**Consumers switched to the region's files**: `process12`, `process31`, `process33` (exits with code 42 when files are missing, which `main.py` treats as end of chunks), `process32` (also uses the region's loadings), `process41` (title now reads "<region> (own PCn)"), `process42` and `process43` (both read `pc_scores_used.csv`, so plots use the same PC as the correlations).

Seto Inland Sea keeps the Seto-wide PC. Seto sub-basins also keep it (sub-basin PCs were out of scope).

**Cleanup and related fixes made while re-running the full step 5 pipeline:**
- `apps/streamlit_app_v2.py` loaded the old shared correlation files. It now stacks the three per-region files (same 188 stations and columns as before), with a caption saying each station is correlated with its own region's PC. The four old shared files (`pca_{env,nutr}_corr_pc{1,2}.csv` in `data/processed/seasonal/summer_bottom/`) were then deleted.
- `main.py` still decided whether to run `process32`, `41`, `42` and `43` by checking for the deleted shared file, so those scripts were silently skipped and no maps were produced in the first full run. Both checks now use the region's file and log a warning when it is missing.
- `merged_gdf.feather` has no `din` or `dip` column. Only `process01`'s `main()` and `process15` derived them, so `process21` and `process13` failed with `KeyError: ['din']` when the full pipeline was run. The derivation is now a shared `add_din_dip()` in `process01`, applied inside `MatrixBuilder`, so every script that builds the permutation matrices gets the columns.

## Results (after the fix)

Verification:

| Check | Result |
|---|---|
| Seto files vs the pre-fix files | Identical for all 127 Seto stations (4 files, 132 env and 240 nutr columns), max difference 0 |
| Bay correlations vs hand recomputation (summer bottom WTEMP) | Match the bay's own PC1 to about 1e-16 (28 Tokyo, 33 Ise stations); differ from the Seto PC1 by up to 0.59 (Tokyo) and 0.65 (Ise) |
| Masked years (Tokyo Bay) | 1981, 1982, 2007 masked; largest `n` in the Tokyo file is 40 (Ise Bay: none masked, largest `n` 43) |
| Re-run (Summer/bottom, 3 regions, env and nutr, PC1 and PC2) | 82 steps; 76 returned 0, 6 returned 42 (normal end-of-chunks signal from `process33`); no failures |
| Visual check (Tokyo Bay summer bottom WTEMP, PC1) | Map and `process42` plot agree: all significant stations positive; masked years absent from the PC series |

Bay PCs behave very differently from the Seto PC1: Tokyo PC1 has no trend (r with year -0.06, lag-1 0.05) and explains 37.9 % of variance; Ise PC1 has a weak trend (r -0.31, lag-1 0.10) and explains 18.9 %. Seto PC1 has r = 0.81 and lag-1 0.72.

Effect on the bay maps (124 maps per region and PC, env and nutr combined; the table gives the mean over those maps of the share of the bay's stations with p ≤ 0.05):

| Region / PC | % stations p ≤ 0.05 before | after | Old vs new station r (median across maps) | Share of station signs that flipped |
|---|---|---|---|---|
| Tokyo Bay PC1 | 30.9 % | 4.9 % | -0.11 | 52 % |
| Tokyo Bay PC2 | 7.7 % | 11.7 % | -0.26 | 55 % |
| Ise Bay PC1 | 21.5 % | 5.6 % | -0.49 | 59 % |
| Ise Bay PC2 | 5.7 % | 8.6 % | 0.20 | 40 % |

For summer bottom water temperature vs PC1, the median r in Tokyo Bay moved from 0.16 to 0.36 (significant stations 14 % to 57 %), and in Ise Bay from 0.25 to 0.17 (36 % to 18 %).

With each bay's own PC, PC1 significance sits at about chance (Tokyo 5.1 %, Ise 6.0 % when all station tests in all maps are pooled). A small number of maps stand out clearly:
- **Tokyo Bay PC1**: summer bottom density (negative, 17 of 28 stations; 15 survive per-map FDR), summer bottom water temperature (positive, 16 of 28; 15 FDR).
- **Tokyo Bay PC2**: summer surface water temperature (positive, 27 of 28 stations), summer air temperature (positive, 23), summer surface PO4-P/DIP (negative, 20).
- **Ise Bay PC2**: summer surface density (negative, 22 of 33), spring surface COD (positive, 21), summer air temperature (positive, 18).
- **Ise Bay PC1**: no map stands out (the best is 11 of 32 stations).
- Number of maps with a field-significant share of stations (binomial test, p < 0.05): Tokyo PC1 13, Tokyo PC2 36, Ise PC1 16, Ise PC2 23 (of 124 each).

Seto Inland Sea results are unchanged (PC1: 25 % of stations significant, PC2: 10 %).

All 736 `process41` maps for the three regions were regenerated.

**Full pipeline run.** `python -m step5_environmental_factor_correlation_analysis` was run end to end: exit code 0, 351 scripts started, no tracebacks, no missing-file warnings. The first three attempts did not complete cleanly, for the reasons listed under "Cleanup and related fixes" above (two failed on `KeyError: ['din']`, one finished but skipped the map scripts). The only warnings in the final run are the expected "PCA output missing" for the seven DO subsets other than Summer/bottom, which step 4 does not compute.

For the Summer/bottom DO PCs, every environmental season and layer was correlated for each region: 44 env and 80 nutr permutations (4 seasons × both layers), for 127 Seto, 28 Tokyo Bay and 33 Ise Bay stations. `process32`, `41`, `42` and `43` each ran 12 times (3 regions × env/nutr × PC1/PC2). Output counts: 736 maps (`process41`), 736 loading scatters (`process32`), 1,929 time-series plots (`process42`), 1,929 scatters (`process43`), 726 parameter time series (`process15`), 48 distribution and 16 heatmap figures. No file in the step 5 figure folders is older than the run, so the previous naming-scheme leftovers (October files) were removed. The `process41` maps per region and environmental season are Seto 60/62/60/62, Tokyo Bay 62 each, Ise Bay 60/62/60/62 (Spring/Summer/Autumn/Winter); a few maps are not drawn where too few stations have data.

## Out of scope / remaining issues

- **Stale helper scripts.** `check_p31*.py` (repo root) and `step5.../run_process31_all.py`, `temp_process31_summary.py` still point at the deleted shared correlation files. They are old one-off diagnostics and were left untouched; they will fail if run.
- **PC sign.** PC signs were left as computed (an arbitrary sklearn convention). A positive correlation for Tokyo Bay or Ise Bay is relative to that bay's PC sign. Orienting PCs so that positive means higher DO is still open.
- **Seto sub-basin PCs** (Osaka Bay, Harima Nada, ...), the standardized PCA mode, the empty `hibiki_nada` step 4 output and the legacy `ise_mikawa_bay` folder (still read by step 6) were not touched.
- **Only Summer/bottom DO has PC files** (step 4 is parameterised for one season/layer by design), so the other seven season/layer DO subsets are skipped by step 5 with a warning, as before. The environmental time series of all four seasons and both layers are all correlated against the Summer/bottom DO PCs.
- **Not yet addressed from the audit:** use detrended or first-differenced series as the main result and show trends separately; test whole-map significance with a Monte Carlo that keeps autocorrelation; treat Seto PC2 as exploratory or rotate the leading PCs; select variables from hypotheses instead of testing all 124; remove the duplicate DIP/PO4-P maps; fix the circular `process43` regression; unify the stratification definition; remove hard-coded paths from `process41`.
- The summer surface salinity result for Seto (52 %) is the one detrended result worth following up with river discharge or precipitation data. The equivalent check for Tokyo Bay and Ise Bay against their own PCs has not been done.

## Status

**Resolved for the scope of this fix.** The correlation logic uses each region's own PC for Tokyo Bay and Ise Bay (Seto unchanged), the old shared files are removed, the Streamlit app reads the per-region files, and the full step 5 pipeline has been re-run successfully for all environmental seasons and layers. The wider analysis recommendations listed above remain open.
