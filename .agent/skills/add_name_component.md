---
description: Add a descriptive name component to directory, script, and output names based on user-defined characteristics or parameters.
---

# Add Name Component Skill

## Description
This skill defines the protocol for appending or inserting a descriptive name component (e.g., a specific parameter, characteristic, or region) into the names of corresponding directories, scripts, and output files. This ensures consistency and reproducibility, strictly adhering to the naming conventions in `global_rule.md`.

## Triggers
- The user requests to add a characteristic, parameter, or distinguishing feature (e.g., "raw", "filtered", "tokyo_bay") to a script or pipeline step.
- You are splitting a generic script into parameterized scripts.
- You are generating outputs that vary based on parameters in a CSV file or iterative loop.

## Instructions
When adding a name component based on a user-defined characteristic or parameter, follow these rules:

1. **Script Names**:
   - Append the component to the descriptive part of the script name, but preserve the numbered execution prefix (`process01_`, `process11_`, etc.).
   - Example: If adding the component "raw" to `process01_calculate_pca_explained_variance.py`, the new name should be `process01_calculate_pca_explained_variance_raw.py`.

2. **Output Directories (Figures and Processed Data)**:
   - The output base directory for a script must mirror the new script name exactly.
   - Example: The script `process01_calculate_pca_explained_variance_raw.py` must output its files to `figures/step4_PCA_analysis/process01_calculate_pca_explained_variance_raw/` and `data/processed/step4_PCA_analysis/process01_calculate_pca_explained_variance_raw/`.

3. **Sub-Folders for Iterative Parameters**:
   - If the script is orchestrated by `main.py` and iterates over inputs, save results in sub-folders corresponding to the parameter value.
   - Example: `figures/step4_PCA_analysis/process11_calculate_pca_explained_variance_per_bay_raw/tokyo_bay/`.
   - **Important**: When running in a loop, the script must ONLY wipe its specific parameter sub-folder (e.g., using `shutil.rmtree(..., ignore_errors=True)`) and NEVER the parent script folder.

4. **Output File Names**:
   - Include the specified parameters from the CSV file (or the iterated value) directly in the name of the output processed data and figures.
   - Example: `pca_timeseries_raw_tokyo_bay.png` or `yearly_do_df_raw.csv`.
   - This makes it explicitly clear what parameters were used to generate the output.

5. **Maintain Pipeline Integrity**:
   - If a script is renamed to add a component, verify that you update the `pipeline_details.md`, `dvc.yaml`, and the step's `main.py` orchestrator.
   - If changing a step directory name entirely, do NOT rename manually; use `python admin_scripts/rename_pipeline_step.py`.
