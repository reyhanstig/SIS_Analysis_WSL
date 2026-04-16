# Workspace Evaluation & Pipeline Optimization Report

**Date:** 2026-04-14
**Objective:** Evaluate the codebase environment as defined in `workspace_evaluation.md` and provide concrete strategies to refine the analysis pipeline, handle new datasets efficiently, and reduce reliance on AI agents by shifting automation to the code itself.

---

## Section 1: Current State of the Workspace

An automated Python scan was conducted over the project directory to extract metadata.

### Summary Statistics
* **Python Scripts (`.py`)**: 35
* **Jupyter Notebooks (`.ipynb`)**: 64
* **Markdown Reports (`.md`)**: 14

### Organizational Anti-Patterns
* **Leftover Artifacts**: Several Python `.py` scripts are improperly stored within the `notebooks/` directory rather than in the unified `scripts/` directory. These are likely leftover exports from notebooks:
  * `notebooks/33_DO_PCA_corr.py`
  * `notebooks/36_plot_env_correlation_test_sig.py`
  * `notebooks/35_DO_PCA_nutr_corr.py`
  * `notebooks/08_Decorrelation_Analysis_v3.py`
  * `notebooks/12_PCA_analysis_continue.py`
  * `notebooks/09_Spatial_Interpolation_diagram.py`
  * `notebooks/08_Decorrelation_Analysis_preview.py`
  * `notebooks/36_plot_env_correlations.py`
* **Workflow Duplication**: Adding new datasets (e.g., `37_Tokyo_Ise_Bay_add_a.ipynb`) is currently handled by creating entirely separate duplicate notebooks of the main pipeline steps.

### Documentation & Health Gaps
Multiple notebooks are lacking proper Markdown preambles/headers in their first cells, reducing structural readability for developers:
* `31_bathymetry_check.ipynb`
* `test_murakami.ipynb`
* `sandbox.ipynb`
* `cartropy sample.ipynb`
* `98_Gaussian_Practice.ipynb`
* `analysis1.ipynb`, `analysis4.ipynb`, `old_02.ipynb`
* `Web_scraping_river_water_level.ipynb`

---

## Section 2: Recommended Improvements and Optimizations

Based on the goal to refine the pipeline, accommodate new data dynamically, and minimize manual/AI agent execution steps, the following steps are heavily recommended:

### 1. Reproducibility & Handling New Datasets efficiently
Currently, expanding to a new region relies on manually copying an established notebook (`01_Data_Processing.ipynb`) to a new one (`37_Tokyo_Ise_Bay_add_a.ipynb`) and manually replacing variable filters. This process degrades pipeline integrity.
* **Parameterize the Data Loader**: Update `scripts/data_loader.py` to pull target regions directly from `params.yaml`. For example, `regions: ['Seto Inland Sea', 'Tokyo Bay', 'Ise Bay']`. The pipeline should dynamically loop over this list to generate a generalized `merged_gdf.feather` with distinct identifiers.
* **DVC `foreach` Integration**: Since DVC is already orchestrated via `dvc.yaml`, take advantage of [DVC's matrix/foreach feature](https://dvc.org/doc/user-guide/project-structure/dvcyaml-files#foreach-stages). Define `regions` in `params.yaml`, and DVC will dynamically generate execution stages for Tokyo Bay, Ise Bay, etc. automatically without duplicating notebook files.

### 2. Including Automation in the Actual Code (Reducing AI Agent Reliance)
Delegating file manipulation and notebook running to AI agents costs API tokens and risks unpredictable errors. You should "code the automation."
* **Extract Logic to Core Python Packages**: Over 60+ notebooks exist, but most critical pipeline logic remains trapped in notebook cells. Extract core logic (e.g., spatial interpolation, PCA matrix building) into discrete `.py` modules inside `scripts/` (e.g., `scripts/pca_core.py`).
* **Implement a Command-Line Interface (CLI)**: Wrap pipeline scripts using Python's native `argparse` or `click` libraries. This allows you to run an entire sub-analysis instantly from the terminal without opening a notebook or asking an AI to do it:
  `python scripts/run_pipeline_step.py --target-region "Tokyo Bay" --step pca`
* **Single Master Script over Notebook Chaining**: Instead of asking the agent or manually executing a chain of 4 parameter notebooks, create a native Python orchestrator script (`scripts/run_all.py`) that strictly invokes standard functions in a deterministic order. Keep the Jupyter Notebooks purely for visualizations and sanity checks.

### 3. File System Cleanup & Automation
* **Use a `Makefile`**: Create a `Makefile` in the project root with automated commands like `make clean` to scrub out auto-generated `.py` files inside the `notebooks` directory, remove `__pycache__`, and clear out any cached `.ipynb_checkpoints`.
* **Automate Formatting**: Set up `pre-commit` hooks. Configure a tool like `nbstripout` and `black` to ensure that standard code quality is maintained automatically upon every local `git commit` you execute, removing the step of asking an AI to "format this notebook".
