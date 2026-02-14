# Seto Inland Sea Water Quality Data Analysis

Welcome to my new code.

## Goal
The purpose of this project is To compile the available environmental data from the Seto Inland Sea area, and make a workable water quality dataset. Then the dataset will be analyzed to reveal any yearly trend as a basis for further analysis.

## Source
The data is mainly sourced from the public water environment information site from the ministry of the environment: 
https://water-pub.env.go.jp/water-pub/mizu-site/mizu/download/download.asp

## Setup & Installation

### 1. Environment Setup
The project uses a Conda environment named **`sis_analysis`**.

1. **Clone this repository**.
2. **Create the environment**:
   ```bash
   conda env create -f environment.yml
   ```
   *Alternatively, create manually:*
   `conda create -n sis_analysis python=3.10 geopandas cartopy pandas matplotlib scipy dvc -y`
3. **Activate the environment**:
   ```bash
   conda activate sis_analysis
   ```

### 2. WSL Specific Setup
If running in **WSL** (Windows Subsystem for Linux), run the setup script to link data from Windows:
```bash
./scripts/fix_wsl_setup.sh
```
*This script installs DVC and creates symlinks to your Windows `data/` folder to avoid duplication.*

---

## Workflow (WSL)

**1. Start Session**
Always activate your environment when starting a new terminal session.
```bash
cd ~/SIS_Analysis_WSL
conda activate sis_analysis
```

**2. Manage Data (DVC)**
Data is stored in Windows but accessed via symlinks. Use DVC to track changes.
```bash
dvc status        # Check if data or pipelines have changed
```

**3. Run Analysis**
Launch Jupyter to run notebooks.
```bash
jupyter notebook
```
*   **Notebooks**: Located in `notebooks/`. Start with `01_Data_Processing.ipynb`.
*   **Scripts**: Utility scripts are in `scripts/`.

**4. Save Changes**
```bash
# 1. Add data changes (if any)
dvc add data reports/figures

# 2. Add code changes
git add .
git commit -m "Update analysis"
``` 