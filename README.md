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

**Required Directory Structure:**
```
C:\Users\reyha\Documents\SIS_Analysis_Windows  (Windows Clone)
/home/reyha/SIS_Analysis_WSL                   (WSL Clone)
```
*Note: The WSL `data/` folder is a symlink to the Windows `data/` folder.*

### 2. Environment Setup
The project uses a Conda environment named **`sis_analysis`**.

1. **Clone this repository**.
2. **Create the environment**:
   ```bash
   conda env create -f environment.yml
   ```
   *Alternatively, create manually:*
   `conda create -n sis_analysis python=3.10 geopandas cartopy pandas matplotlib scipy dvc papermill pyyaml -y`
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

---

## Analysis Pipeline (New!)

We use a **DVC Pipeline** to automate the execution of notebooks. This ensures that when you update an early step (like data cleaning), all downstream analysis (like PCA) is automatically updated.

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

# Add new external raw data folders individually (this places the .dvc files in the data/ folder)
# We must immediately move them to the root directory and rename them to avoid placing Git-tracked items inside the WSL data/ symlink.
dvc add data/raw data/sushitsu data/boundaries
mv data/raw.dvc data_raw.dvc
mv data/sushitsu.dvc data_sushitsu.dvc
mv data/boundaries.dvc data_boundaries.dvc
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