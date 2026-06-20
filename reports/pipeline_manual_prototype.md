# SIS Analysis Pipeline: Manual & Protocol

## 1. Philosophy: "Interactive Exploration, Automated Execution"

This protocol is designed to bridge your **existing notebook-centric workflow** with a **robust engineering pipeline**. 

**The Core Concept:** 
You continue to work exactly as you do—opening notebooks, exploring data, making plots, and adjusting logic interactively. However, once you are satisfied with a notebook's logic, you **"commit"** it to the pipeline. The "boring part" (re-running previous steps because you changed something upstream) is handled entirely by automation.

---

## 2. Directory Structure Standards

To enable automation, we strictly separate "Official Pipeline Steps" from "Experiments".

```text
SIS_Analysis_WSL/
├── notebooks/
│   ├── pipeline/               # <-- ONLY stable pipeline steps go here
│   │   ├── 01_Data_Processing.ipynb
│   │   ├── 08_Decorrelation_Analysis_v3.ipynb
│   │   ├── 09_Spatial_Interpolation_v2.ipynb
│   │   └── 10_PCA_Analysis.ipynb
│   ├── exploration/            # <-- Sandbox area. Use these for testing ideas.
│   │   ├── sandbox_interpolation_test.ipynb
│   │   └── quick_plot_check.ipynb
│   └── output/                 # <-- Automated run logs (generated files)
│       ├── 01_log.ipynb
│       └── ...
├── data/                       # Symlinked to Windows D: Drive
│   ├── raw/                    # Read-Only Source
│   └── processed/              # Machine-Generated (Never manually edit files here)
├── dvc.yaml                    # The "Master Plan" file linking the steps
└── params.yaml                 # Global settings (Year ranges, thresholds)
```

**Rule 1:** A notebook in `notebooks/pipeline/` MUST be runnable from top-to-bottom without errors.
**Rule 2:** Pipeline notebooks NEVER hardcode output filenames. They use `scripts.paths.ProjectPaths`.

---

## 3. The Analysis Cycle (How to work)

This section describes how to handle your specific requirement: **"Back and forth modification in the middle of the process."**

### Scenario A: The First Run (Building logic)

1.  **Open** `01_Data_Processing.ipynb` (or any other notebook).
2.  **Edit & Run:** Import data, visualize constraints, filter outliers. Use your judgment/expertise here.
3.  **Save:** When you see the output file (e.g., `data/processed/merged_gdf.feather`) is saved correctly by the last cell.
4.  **Register (Once):** You tell DVC about this step.

### Scenario B: The Cascading Fix

*Problem:* You are working on `10_PCA_Analysis.ipynb` and realize the results look weird. You trace it back to a cleaning error in `01_Data_Processing.ipynb`.

1.  **Pause** work on `10`.
2.  **Open** `01_Data_Processing.ipynb`.
3.  **Modify:** Fix the cleaning threshold. Run the cells in `01` interactively to confirm the chart looks right *in that notebook*.
4.  **Save** `01`.
5.  **THE MAGIC STEP:** instead of manually opening `08` and `09` and running them, you go to the terminal and type:
    ```bash
    dvc repro
    ```
6.  **What happens:**
    *   DVC sees `01` changed. It runs `01`.
    *   DVC knows `08` and `09` depend on `01`'s output. It automatically runs them.
    *   DVC knows `10` depends on `09`. It runs `10` up to the point you were working.
7.  **Resume:** You reload your `10_PCA_Analysis.ipynb` (or re-load the data variable), and your input data is now "fixed" and synchronized.

### Scenario C: Iterative Loops

*Problem:* You are aggressively tuning a parameter (e.g., "Interpolation Radius") in Step 09 and want to immediately see how it affects Step 10 PCA.

1.  **Move the Parameter:** Extract the "Radius" variable into `params.yaml`.
    ```yaml
    # params.yaml
    interpolation:
      search_radius_factor: 2.0
    ```
2.  **Update Notebooks:** Change Step 09 to read this param.
3.  **The Loop:**
    *   Edit `params.yaml` (Change `2.0` -> `2.5`)
    *   Run `dvc repro`
    *   Check specific PCA output figure in `10` output or `figures/`.
    *   Repeat.

---

## 4. Setting Up The Protocol (Implementation)

### Step 1: Install Requirements
You need `papermill` to execute notebooks as scripts.
```bash
conda install papermill pyyaml -c conda-forge
# OR
pip install papermill pyyaml
```

### Step 2: Define the Dependency Graph (`dvc.yaml`)
This is the file that explicitly solves your "Integration" problem. It guarantees that inputs for Step 2 come *exactly* from Step 1.

*Create a file named `dvc.yaml` in the root:*

```yaml
stages:
  process_data:
    cmd: papermill notebooks/pipeline/01_Data_Processing.ipynb notebooks/output/01_log.ipynb
    deps:
      - notebooks/pipeline/01_Data_Processing.ipynb
      - scripts/data_loader.py
    outs:
      - data/processed/merged_gdf.feather

  decorrelation:
    cmd: python scripts/run_pipeline_step.py notebooks/pipeline/08_Decorrelation_Analysis_v3.ipynb notebooks/output/08_log.ipynb decorrelation
    deps:
      - notebooks/pipeline/08_Decorrelation_Analysis_v3.ipynb
      - data/processed/merged_gdf.feather
    params:
      - decorrelation.min_periods
      - decorrelation.r_crit_alpha
      - decorrelation.distance_cutoff_km
    outs:
      - data/processed/yearly_do_df.csv
      - data/processed/dist_matrix_km.csv
      - data/processed/stations_decorrelation_scale.csv

  interpolation:
    cmd: python scripts/run_pipeline_step.py notebooks/pipeline/09_Spatial_Interpolation_v2.ipynb notebooks/output/09_log.ipynb interpolation
    deps:
      - notebooks/pipeline/09_Spatial_Interpolation_v2.ipynb
      - data/processed/yearly_do_df.csv
      - data/processed/dist_matrix_km.csv
      - data/processed/stations_decorrelation_scale.csv
    params:
      - interpolation.weighting_func
      - interpolation.min_weight
      - interpolation.search_radius_factor
    outs:
      - data/processed/interpolated_do_df.csv

  pca_analysis:
    cmd: papermill notebooks/pipeline/10_PCA_Analysis.ipynb notebooks/output/10_log.ipynb
    deps:
      - notebooks/pipeline/10_PCA_Analysis.ipynb
      - data/processed/interpolated_do_df.csv
      - data/processed/stations_decorrelation_scale.csv
    outs:
      - data/processed/pca_scores.csv
      - data/processed/pca_loadings.csv
      - data/processed/pca_variance.csv
```

---

## 5. Output Management & Versioning

You mentioned: *"I need to keep track of all the different outputs and compare them."*

With this pipeline, every time you run `dvc repro`, the outputs (`.feather`, `.csv`, `.png`) are updated. To track history:

1.  **Run Pipeline:** `dvc repro`
2.  **Commit Code & Data:**
    ```bash
    git add dvc.yaml dvc.lock notebooks/pipeline/*.ipynb params.yaml
    git commit -m "Analysis: Interpolation radius 15km"
    # Note: data/ is not committed to git here because it is a symlink to Windows/Drive
    ```
3.  **Compare:**
    To compare your current results with yesterday's results:
    *   `dvc metrics diff` (if you save numeric metrics)
    *   `dvc diff` (shows changes in file hashes)
    *   Or simply checkout the old git branch.

## 6. How to Start Today

1.  **Create folders:** `mkdir -p notebooks/pipeline notebooks/output notebooks/archive`
2.  **Move & Rename:** Move your "Good" notebooks to `notebooks/pipeline` and number them sequentially. Move the rest to `archive`.
3.  **Write `dvc.yaml`:** Copy the template above and adjust paths.
4.  **Run:** `dvc repro`.

This converts your "messy web of notebooks" into a **Click-Button-To-Update Factory** while letting you stay inside the notebooks for the actual creative work.
