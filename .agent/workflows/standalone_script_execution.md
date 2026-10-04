---
description: Workflow for running or testing standalone process scripts or steps without running a full DVC repro.
---

When developing, testing, or debugging scripts within the data pipeline (such as individual `process*.py` scripts in step 5), running `dvc repro` on the entire pipeline is often too slow and rigid. `dvc repro` treats each step (like `step5_environmental_factor_correlation_analysis`) as a monolithic stage, running all scripts defined in its `main.py` in sequence.

Here are the four most optimal ways to execute parts of the pipeline, depending on your goal:

### 1. Test one script with one parameter combination (Direct Execution)
By far the fastest feedback loop for iterating on a single process script. Each script uses `argparse` and can be run entirely standalone.
- **Agent Instruction:** Before executing this script for the user, you MUST first reply to the user and ask them to select which parameters they want to use from the available options. Do not run the script until the user has selected their parameters.
- Ensure you set `PYTHONPATH` so internal imports (like `utils`) resolve correctly.
- Provide the necessary command-line arguments directly based on the user's selection.
- **Command:**
  ```bash
  cd /home/reyha/SIS_Analysis_WSL/step5_environmental_factor_correlation_analysis

  conda run -n sis_analysis \
    env PYTHONPATH=/home/reyha/SIS_Analysis_WSL \
    python process42_time_series_significant_stations_PC_correlation.py \
      --pc_name PC1 \
      --param Summer_1_WTEMP \
      --target_region "Seto Inland Sea" \
      --season Summer \
      --layer bottom \
      --data_type env
  ```

### 2. Test one script with all its parameter combinations
If you need to test a specific script across all its dynamic arguments (e.g., all regions, layers, or parameters read from `step5_parameter.csv`), running them one by one is tedious. 
- Do **not** run the main orchestration script, as it deletes output directories and runs other scripts as well.
- Instead, create a small, temporary shell script (or Python script) that iterates over the parameter combinations and runs the conda command for you.

### 3. Force DVC to re-run only one step (Skipping upstream)
If you made changes to a step (like `step5`) and want DVC to reproduce it, but DVC is trying to rebuild upstream steps (like `step4_PCA_analysis`), you can force it to only execute the target step.
- This will still run the full `main.py` for that step.
- **Command:**
  ```bash
  dvc repro --single-item step5_environmental_factor_correlation_analysis
  ```

### 4. Run a step's main orchestration script without DVC overhead
If you just want to run the entire step (e.g., all `process*.py` scripts) and bypass DVC's caching, dependency checking, and lockfile updates entirely, you can run the step's module directly using Python.
- This is useful for quickly regenerating outputs for a step without checking DVC status.
- **Command:**
  ```bash
  cd /home/reyha/SIS_Analysis_WSL
  
  conda run -n sis_analysis \
    env PYTHONPATH=/home/reyha/SIS_Analysis_WSL \
    python -m step5_environmental_factor_correlation_analysis
  ```
