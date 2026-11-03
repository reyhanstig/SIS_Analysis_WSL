# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Analysis of Japanese Ministry of the Environment water-quality data for the Seto Inland Sea and nearby bays (Tokyo, Ise, Osaka, ...), focused on dissolved-oxygen (DO) trends and hypoxia. Code runs in WSL; the heavy data lives on Windows. `.agent/global_rule.md` is the master rule set for agent work here and is summarized below; read it before adding pipeline code.

## Environment and commands

- Python: `/home/reyha/miniconda3/envs/sis_analysis/bin/python` (also in `.agent/python_env_path`). Or `conda run -n sis_analysis python ...`. Create the env with `conda env create -f environment.yml`.
- Run the full pipeline: `dvc repro`. Run one step: `python -m step2_hypoxia_frequency_calculation` (from repo root). Steps and their dependencies are declared in `dvc.yaml`.
- Run one script of a step directly: `cd stepN_*/ && PYTHONPATH=<repo root> python processNN_*.py [--division "Tokyo Bay"]`. Scripts import `utils.*`, so the repo root must be on `PYTHONPATH`. `main.py` sets this for you.
- Helpers in `admin_scripts/`: `run_pipeline_step.py`, `rename_pipeline_step.py`, `delete_pipeline_step.py`, `clean_orphaned_outputs.py`.
- There is no test suite or linter configured. Verify changes by running the affected script and inspecting its output under `figures/` or `data/processed/`.
- Notebooks can be run as scripts or have functions imported through `scripts/agent_notebook_utils.py` (`load_nb_as_module`).

## Architecture

**Pipeline.** `step1_…` to `step6_…` are Python packages (`__main__.py` calls `main.main()`), chained in `dvc.yaml`: step1 cleaning feeds step2 (hypoxia frequency), step3 (decorrelation scales), then step4 (PCA/EOF), step5 (environmental-factor correlations) and step6 (focus-area analysis). `step0_sandbox/` is the user's personal notebook history and is not part of the pipeline.

**Orchestration pattern.** Each step's `main.py` runs its `processNN_*.py` scripts with `subprocess.run` and does the looping itself. It reads a `stepN_parameter(s).csv` and iterates over regions, seasons or parameters. It passes values to the scripts as CLI args such as `--division`. The scripts do the logic for one region and one output. They are not meant to loop.

**Regions.** A "division" is either a whole water mass (`watermass_name`, such as "Seto Inland Sea", "Tokyo Bay" or "Ise Bay") or a Seto sub-basin (`division` column, such as "Osaka Bay" or "Harima Nada"). The step parameter CSVs list them as semicolon-separated values.

**Paths and data.** `data/`, `figures/`, `sources/`, `notes/` and `00_Heavy_Assets/` are symlinks into `/mnt/c/Users/reyha/Documents/SIS_Analysis_Windows/` and are gitignored. DVC tracks them through `data_*.dvc` and `reports/figures.dvc`, and DVC is run from Windows for the data. Always use `from utils.paths import ProjectPaths` for paths and never hardcode them. `.agent/global_rule.md` mentions `scripts/paths.py`, but the real file is `utils/paths.py`. `utils/data_loader.py` and `utils/mapping_config.py` hold the shared loading and mapping standards (see `reports/SIS_mapping_standard.md`).

**Config.** Global settings are in `params.yaml` (seasonal subsets, interpolation, decorrelation, mapping bbox). Per-step settings are in the `step*_parameter*.csv` files. Key domain facts: `temp` is air temperature and `wtemp` is water temperature. `saisuipoin` 1 is the surface layer and 2 is the bottom layer. `do_` is DO in mg/L. Hypoxia is DO below `hypoxia_threshold` (2.0 by default).

## Conventions (from .agent/global_rule.md)

- Script parameters live in a CSV loaded with pandas, not in the code. Output file and folder names include the parameter values.
- One script produces one output. Looping belongs in `main.py`.
- Name scripts `processNN_<long_descriptive_name>.py`. The tens digit groups related sub-processes (01–09, then 11–19, then 21–29). Sub-steps must run independently. Keep each script to about 500 lines or fewer.
- Figures are saved under `figures/<step>/<script_name>/...`, mirroring the script's path, with one sub-folder per parameter value (for example `.../tokyo_bay/`). Processed data goes in `data/processed/` with the same naming and is tracked with DVC.
- An output-producing script must `shutil.rmtree` its own target directory before writing. When `main.py` loops over divisions, the inner script wipes only its own division sub-folder, never the parent. Alternatively, `main.py` clears the parent before the loop.
- Input CSVs must be existence-checked. Log a warning and exit cleanly instead of raising `FileNotFoundError`.
- Never rename or delete a step by hand. Use the `admin_scripts` rename and delete tools so `dvc.yaml`, figures and data stay in sync.
- To re-run only part of a step, do not comment scripts out of `main.py`, because it clears the output folders first. Create a temporary orchestration script without the `rmtree` calls, run it, then delete it.
- Never auto-clean `step0_sandbox/`. New sandbox notebooks start from `step0_sandbox/archive/101_example_notebook.ipynb`, and their outputs go to `figures/step0_sandbox/<notebook_name>/`.
- Temporary test scripts go in `scratch/` (gitignored).

## Sub-project

`sub1_Tokyo_Bay_DO_analysis/` is a self-contained Tokyo Bay version of the same four-stage analysis, with its own README, data and `environment.yml`. It is independent of the main pipeline.

## Known inconsistencies

The README directory tree omits step6 and sub1. `.agent/workflows/*.md` contain stale Windows paths (`c:\Users\reyha\Documents\SIS_Analysis`) and a Python 3.11 note, while `README.md` says 3.10. Trust the current WSL layout over these.
