# SIS Analysis - WSL Migration Guide

This guide will help you migrate your `SIS_Analysis` project from Windows (PowerShell) to WSL (Ubuntu).

## 1. Prerequisites
- **WSL Installed**: Ensure you have WSL and Ubuntu installed (`wsl --install` in PowerShell).
- **VS Code Extensions**: Install the **WSL** extension for VS Code.

## 2. Moving Files
For best performance with Python and Git, it is highly recommended to move your files into the WSL filesystem (e.g., your home directory `~`), rather than keeping them on the Windows drive (`/mnt/c/...`).

### Steps:
1. Open your WSL Ubuntu terminal.
2. Navigate to your home directory:
   ```bash
   cd ~
   ```
3. Copy the project folder from Windows:
   > **Note:** We use `sudo` here because Git files are often "Read-Only" on Windows, which causes permission errors with a normal copy.
   ```bash
   # Remove any failed partial copies first
   rm -rf SIS_Analysis

   # Copy with sudo
   sudo cp -r /mnt/c/Users/reyha/Documents/SIS_Analysis .

   # Fix ownership (change 'root' ownership back to your user)
   sudo chown -R $USER:$USER SIS_Analysis
   ```
4. Enter the directory:
   ```bash
   cd SIS_Analysis
   ```

## 3. Environment Setup
We have created an `environment.yml` file to make installation easy using Conda (recommended for geospatial libraries like `cartopy` and `geopandas`).

### Option A: Using Conda (Recommended)
1. If you don't have Conda, install Miniconda in WSL:
   ```bash
   mkdir -p ~/miniconda3
   wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda3/miniconda.sh
   bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
   rm -rf ~/miniconda3/miniconda.sh
   ~/miniconda3/bin/conda init bash
   source ~/.bashrc
   ```
2. Create the environment:
   ```bash
   conda env create -f environment.yml
   ```
3. Activate it:
   ```bash
   conda activate sis_analysis
   ```

### Option B: Using Pip
If you prefer standard Python venv:
```bash
sudo apt-get update && sudo apt-get install python3-venv libgeos-dev libproj-dev
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
*Note: Installing `cartopy` via pip on Linux often requires manual system dependency installation (GEOS, Proj).*

## 4. VS Code Setup
1. From inside the `SIS_Analysis` directory in your WSL terminal, run:
   ```bash
   code .
   ```
   This will open VS Code connected to WSL.

## 5. Validate DVC (Data Version Control)
Since this project uses DVC with Google Drive:
1. Run `dvc status` or `dvc doctor`.
2. If you need to pull data, run:
   ```bash
   dvc pull
   ```
   *You may need to authenticate with Google Drive again via the browser link provided in the terminal.*

## 6. Code Compatibility
- **Paths**: Hardcoded Windows paths (e.g., `C:\Users\...`) have been updated to use relative paths in `scripts/generate_ito_notebook.py`.
- **Scripts**: Execute scripts using python command, e.g., `python scripts/convert_to_geojson.py`.

## 7. Troubleshooting
- **Git Line Endings**: Windows uses CRLF, Linux uses LF. If you see many modified files, it might be line endings.
  - Run `git config --global core.autocrlf input` in WSL.
- **Permission Denied**: If you have issues running scripts, ensure they are executable (`chmod +x scripts/*.py`) or run with `python script.py`.
