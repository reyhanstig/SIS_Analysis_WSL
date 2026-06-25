# Seto Inland Sea Water Quality Data Analysis

Welcome to my new code.

## Goal
The purpose of this project is To compile the available environmental data from the Seto Inland Sea area, and make a workable water quality dataset. Then the dataset will be analyzed to reveal any yearly trend as a basis for further analysis.

## Source
The data is mainly sourced from the public water environment information site from the ministry of the environment: 
https://water-pub.env.go.jp/water-pub/mizu-site/mizu/download/download.asp

## Setup & Installation

### 1. Repository Setup
This project uses a **single Git repository** (`SIS_Analysis_WSL`) cloned in both Windows and WSL environments.
*   **Windows**: Used for managing high-volume data (`data/`, `figures/`) with DVC.
*   **WSL**: Used for running analysis code (`notebooks/`, `scripts/`).

## Directory Structure

```text
SIS_Analysis_WSL/
├── admin_scripts/                              <- Shell scripts and DVC utilities
├── apps/                                       <- Streamlit dashboards
├── data/                                       <- Data storage (Symlink recommended)
├── figures/                                    <- Output visualisations (Symlink recommended)
├── reports/                                    <- Markdown reports and documentation
├── step0_sandbox/                              <- Jupyter Notebooks for exploration and scratchpad
├── step1_data_processing_cleaning/             <- Spatial data and river station extraction
├── step2_hypoxia_frequency_calculation/        <- Hypoxia frequency analysis
├── step2_decorrelation_scale_analysis/         <- Decorrelation scales
├── step3_PCA_analysis/                         <- PCA environments
├── step5_environmental_factor_correlation_analysis/ <- Env factor correlations
└── utils/                                      <- Shared python utilities (paths, config)
```

### 2. Environment Setup
The project uses a Conda environment named **`sis_analysis`**.

1. **Clone this repository**.
2. **Create the environment**:
   ```bash
   conda env create -f environment.yml
   ```
   *Alternatively, create manually:*
   `conda create -n sis_analysis python=3.10 geopandas cartopy pandas matplotlib scipy dvc papermill pyyaml xarray netcdf4 gsw selenium beautifulsoup4 -y`
3. **Activate the environment**:
   ```bash
   conda activate sis_analysis
   ```

### 3. Windows Setup (Required for Data Management)
The data management workflow relies on DVC being installed on Windows.
*   **Install DVC on Windows**: Download the installer from [dvc.org](https://dvc.org/) or run `pip install dvc` in your Windows terminal.

### 4. WSL Setup
Run the setup script to link data from Windows:
```bash
./scripts/fix_wsl_setup.sh
```
*This script creates symlinks to your Windows `data/` folder so you can access files directly.*

## Data Field Definitions

Key parameters in the dataset have been clarified through statistical analysis (see `notebooks/26_check_temp_wtemp.ipynb`):

- **`temp`**: **Air Temperature (°C)**. Ambient air temperature recorded at the time of sampling. Shows higher variance and is independent of water depth.
- **`wtemp`**: **Water Temperature (°C)**. Recorded at the specific sampling depth. Shows lower variance (high heat capacity) and decreases with depth.
- **`saisuipoin`**: **Sampling Depth Layer**. 
    - `1`: Surface Layer.
    - `2`: Bottom Layer.
- **`do_`**: Dissolved Oxygen concentration (mg/L).
- **`salt`**: Salinity.

---

## Analysis Pipeline (New!)

We use a **DVC Pipeline** to automate the execution of our modular Python scripts. The pipeline is strictly organized into numbered step directories (e.g., `step1_data_extraction`, `step2_hypoxia_frequency_calculation`), ensuring downstream dependencies automatically rebuild when early data or parameters change.

### Core Command
```bash
dvc repro
```
Running this command in the terminal executes the pipeline. DVC tracks each step directory, automatically checking for modified scripts or parameters and only re-running what is necessary.

### Directory Structure & Conventions
*   **`stepX_.../`**: Each pipeline step has its own directory acting as a python module.
*   **`stepX_.../10_script.py`**: Scripts are numbered in 10s places (10, 20, 30) for logical execution order. 
*   **`stepX_.../stepX_parameter.csv`**: Every step folder contains its own parameter CSV. Scripts read from this file rather than hardcoding variables.
*   **`figures/stepX_.../YY_script/`**: Outputs and generated figures are automatically saved to dynamically mirrored directories in the `figures/` symlink folder.
*   **`dvc.yaml`**: Defines the dependency graph hooking these modular step folders together.

### How to Work
1.  **Modify**: Update parameters in the `stepX_parameter.csv` file or edit the `.py` scripts inside a step directory.
2.  **Run**: Execute `dvc repro` in the terminal. DVC detects changes in the specific folder and re-runs the affected stages automatically.

---

## Workflow (Hybrid)

**1. Manage Data (Windows)**
Modify data or figures in your Windows folder. Commit changes here first.
```powershell
# In Windows PowerShell
cd C:\Users\reyha\Documents\SIS_Analysis_Windows

# We've set up custom tracker names in the repository root to avoid symlink overlap.
# Simply run the add command -- DVC will automatically detect and update `data_raw.dvc`, `data_sushitsu.dvc`, etc.!
dvc add data/raw data/sushitsu data/boundaries
git add data_raw.dvc data_sushitsu.dvc data_boundaries.dvc
git commit -m "Update external raw data"
git push
```

**2. Sync & Analyze (WSL)**
Pull the latest data version into WSL before running analysis.
```bash
# In WSL
cd ~/SIS_Analysis_WSL
git pull          # Gets the new 'data.dvc' file
conda activate sis_analysis
dvc repro         # Updates the analysis
jupyter notebook  # Open notebooks for interactive work
```
> **Note**: If `git pull` fails with "divergent branches", run:
> `./scripts/reconcile_branches.sh` to fix it automatically.

**3. Save Code Changes (WSL)**
Commit analysis work in WSL.
```bash
# In WSL
git add .
git commit -m "Update analysis code"
git push
dvc push  # Pushes newly generated figures and cache to DVC remote
```

**4. Sync Back (Windows)**
Occasionally pull code changes to Windows to keep it up to date.
```powershell
# In Windows
git pull
dvc pull  # Pull the latest figures and data changes from the remote
``` 

---

## Pipeline Steps Details

The DVC pipeline consists of the following modular steps:

1. **`step1_data_extraction`**: Initial extraction of raw spatial data.
2. **`step1_data_processing_cleaning`**: Cleans and extracts specific survey data, including fixed stations, Hiroshima survey data, line surveys, spatial data, and river stations.
3. **`step2_decorrelation_scale_analysis`**: Analyzes the spatial and temporal decorrelation scales of environmental variables, including seasonal variations and permutations.
4. **`step2_hypoxia_frequency_calculation`**: Calculates the frequency and trends of hypoxia across different stations and divisions, mapping the trends over time.
5. **`step3_PCA_analysis`**: Performs Principal Component Analysis (PCA) to find correlations between environmental factors, specifically targeting Ise Bay and Tokyo Bay.
6. **`step5_environmental_factor_correlation_analysis`**: Investigates the drivers of hypoxia, analyzing what environmental factors (e.g., nutrients, temperature) affect dissolved oxygen (DO) levels and comparing these drivers by their trends.

For a comprehensive breakdown of every script in each step and its specific function, please refer to the [Pipeline Details Documentation](pipeline_details.md).