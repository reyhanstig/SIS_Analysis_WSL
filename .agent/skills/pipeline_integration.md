---
description: Transform a sandbox exploration notebook into a pipeline-ready component and integrate it into the formal step structure.
---

# Pipeline Integration Skill

This skill guides you through taking an exploratory notebook from `step0_sandbox/` and formally integrating it into the project's step-based DVC pipeline, adhering to the `global_rule.md` standards.

## Integration Steps

1.  **Analyze and Align**:
    -   Analyze the target notebook in `step0_sandbox/`.
    -   Determine which stage of the pipeline it belongs to based on the current structure:
        -   `step1_data_processing_cleaning/`
        -   `step2_hypoxia_frequency_calculation/`
        -   `step2_decorrelation_scale_analysis/`
        -   `step3_PCA_analysis/`
        -   `step5_environmental_factor_correlation_analysis/`

2.  **Format and Restructure**:
    -   Follow `global_rule.md`:
        -   Extract parameters into a CSV file and load them via Pandas, OR use `params.yaml` with DVC.
        -   Ensure the code produces exactly **one output** per script. If multiple outputs are needed, wrap the core logic in a loop based on the input parameters.
        -   Do not hardcode paths; use `utils.paths.ProjectPaths`.

3.  **Extraction & Module Creation**:
    -   **Option A (Preferred for Python scripts):** Extract the core logic from the notebook into a new Python script named `processX_descriptive_name.py` inside the chosen `stepX_.../` directory. Update the `main.py` and `__main__.py` in that directory to include this new process.
    -   **Option B (If keeping as a Notebook):** If it must remain a notebook, use `agent_notebook_utils.py` to enable modular execution and ensure it runs from start-to-finish without interaction. Keep it in the `stepX_.../` directory and number it logically (e.g., `10_...` for step 1, `20_...` for step 2).

4.  **Update `dvc.yaml`**:
    -   Add a new stage to `dvc.yaml`.
    -   If you used Option A, the `cmd` should be `python -m stepX_directory_name` (or invoking the specific script).
    -   If you used Option B, the `cmd` should use `papermill` or `admin_scripts/run_pipeline_step.py`.
    -   Define `deps` and `outs`.

5.  **Verify Pipeline**:
    -   Run `python validate_paths.py` (if it exists) to ensure no paths were broken during extraction.
    -   Run `dvc status` and `dvc repro`.
    -   Check that the new stage executes correctly and produces the expected outputs in `data/processed/` or `figures/`.

## Completion Criteria

-   The analytical logic has been moved out of `step0_sandbox/` and into the correct `stepX_` module.
-   Code adheres to `global_rule.md` (no hardcoded paths, 1 output per script, parameter management).
-   `dvc.yaml` includes the new stage and successfully resolves dependencies.
-   `dvc repro` executes cleanly.
