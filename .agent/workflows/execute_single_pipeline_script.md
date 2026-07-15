---
description: Execute a single script within a pipeline step folder without triggering global output folder deletion.
---

When testing or running a single data processing script in the pipeline (e.g., within `step5_environmental_factor_correlation_analysis`), avoid running the step's primary `main.py` directly if you do not want all existing output folders wiped. The `main.py` orchestration script aggressively cleans output directories by deleting all `process*.py` folders at the very beginning to prevent stale data.

Follow this workflow to isolate the execution:

1. **Option A: Direct Execution via Terminal (For a single run/test)**
   - Bypass `main.py` entirely by running the script directly using the `conda` environment.
   - You must manually pass the required command-line arguments (e.g., `--pc_name`, `--param`, `--target_region`).
   - Example:
     ```bash
     conda run -n sis_analysis python process43_confirm_env_parameter_relationship.py --pc_name PC1 --param Summer_1_WTEMP --target_region "Seto Inland Sea" --layer bottom --data_type env
     ```
   - This will regenerate outputs for this specific run without touching the directories of other scripts.

2. **Option B: Temporary Orchestration Script (For bulk runs without deletion)**
   - If you need to run the script across all combinations of parameters and regions (e.g., dynamically reading from `step5_parameter.csv` or `step5_ts_parameters.csv`), do **not** simply comment out the other scripts in `main.py`. If you run a modified `main.py`, it will still delete all folders first, leaving you with missing data.
   - Instead, create a temporary orchestration script (e.g., `run_temp.py`) inside the step directory.
   - The temporary script should:
     1. Import `subprocess`, `Path`, and project configurations.
     2. Read the dynamic parameters and regions from the relevant CSV files.
     3. Iterate through the target regions, seasons, layers, and parameters.
     4. Use `subprocess.run()` to execute the target Python scripts with the derived arguments.
     5. **Omit any `shutil.rmtree` or directory deletion logic.**
   - Run the temporary script from the terminal using the `sis_analysis` environment:
     ```bash
     conda run -n sis_analysis python run_temp.py
     ```

3. **Cleanup**
   - After the execution is finished and the outputs are verified, ensure you delete the `run_temp.py` script or add it to `.gitignore` so it does not clutter the repository.
