---
description: Transform an exploration notebook into a pipeline-ready component and integrate it.
---

# Pipeline Integration Skill

This skill guides you through the process of taking an exploration notebook and integrating it into the project's DVC pipeline.

## Integration Steps

1.  **Format and Structure**:
    -   Ensure `101_example_notebook.ipynb` structure is followed.
    -   Replace manual paths with `ProjectPaths`.
    -   Add `parameters` tag to the parameters cell (if applicable).
    -   Ensure notebook runs start-to-finish without interaction.

2.  **Move to Pipeline Directory**:
    -   Move the notebook from `notebooks/exploration/` (or root) to `notebooks/pipeline/`.
    -   Rename it with a sequential number (e.g., `09_Spatial_Interpolation_v2.ipynb`).
    -   Use `git mv` if the file was tracked by git.

3.  **Update `scripts/paths.py`**:
    -   If the notebook creates new output files (CSV, Feather, Figures), define constants for them in `ProjectPaths`.
    -   Example: `NEW_ANALYSIS_FILE = PROCESSED_DATA_DIR / "new_analysis.csv"`

4.  **Update `dvc.yaml`**:
    -   Add a new stage (e.g., `new_analysis`).
    -   Define `cmd` (using `papermill` or `run_pipeline_step.py`), `deps` (input files/scripts), and `outs` (output files).
    -   Reference the newly added path constants if possible (though `dvc.yaml` uses relative paths directly).

5.  **Update `params.yaml` (Optional)**:
    -   If the notebook uses configurable parameters, add a section in `params.yaml`.
    -   Ensure the parameter names in `dvc.yaml` match the keys in `params.yaml`.

6.  **Verify Pipeline**:
    -   Run `dvc repro`.
    -   Check that the new stage executes correctly and produces the expected outputs.

7.  **Update Pipeline Summary**:
    -   Open `notebooks/pipeline/pipeline_summary.md`.
    -   Add a new section for the added stage under "3. Pipeline Stages".
    -   List the notebook path, inputs, and outputs.
    -   Add any new path constants to "4. Key Artifacts".

## Parameters for `run_pipeline_step.py`

When adding a stage to `dvc.yaml`, prefer using `python scripts/run_pipeline_step.py` over raw `papermill` if you need parameter injection from `params.yaml`.

Example `dvc.yaml` entry:

```yaml
  my_new_stage:
    cmd: python scripts/run_pipeline_step.py notebooks/pipeline/XX_My_Notebook.ipynb notebooks/output/XX_log.ipynb my_stage_params
    deps:
      - notebooks/pipeline/XX_My_Notebook.ipynb
      - data/processed/input_data.csv
    params:
      - my_stage_params.threshold
    outs:
      - data/processed/output_data.csv
```

## Completion Criteria

-   Notebook is in `notebooks/pipeline/`.
-   `dvc.yaml` includes the new stage.
-   `dvc repro` runs successfully.
-   `notebooks/pipeline/pipeline_summary.md` is updated.
-   Git tracks the changes (`dvc.yaml`, `scripts/paths.py`, notebook file).
