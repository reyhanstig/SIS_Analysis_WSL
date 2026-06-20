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

We use a **DVC Pipeline** to automate the execution of notebooks. This ensures that when you update an early step (like data cleaning), all downstream analysis (like PCA) is automatically updated. 

**Regional Support**: The pipeline now supports localized analysis. By adjusting `mapping` parameters in `params.yaml`, you can automatically restrict the entire analysis (from subsets to PCA) to specific bays such as **Tokyo Bay** or **Ise Bay**.

### Core Command
```bash
dvc repro
```
Running this command in the terminal will execute the entire pipeline from start to finish, running only the steps that need to be updated.

### Directory Structure
*   **`notebooks/pipeline/`**: Contains the "Official" analysis notebooks. These are run by DVC.
*   **`notebooks/exploration/`**: Place for testing ideas.
*   **`params.yaml`**: Configuration file for parameters (e.g., thresholds, radii).
*   **`dvc.yaml`**: Defines the dependency graph.

### How to Work
1.  **Edit**: Open a notebook in `notebooks/pipeline/` and modify it interactively.
2.  **Save**: Save the notebook.
3.  **Run**: Terminate the kernel and run `dvc repro` in the terminal to propagate your changes to all other notebooks.

For detailed instructions, see `pipeline_manual_prototype.md`.

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