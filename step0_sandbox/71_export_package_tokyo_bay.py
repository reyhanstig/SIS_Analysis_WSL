import os
import shutil
import zipfile
import subprocess
from pathlib import Path
import pandas as pd

# Define paths
ROOT_DIR = Path('/home/reyha/SIS_Analysis_WSL')
STAGING_DIR = ROOT_DIR / 'sub1_Tokyo_Bay_DO_analysis'
ZIP_OUTPUT = Path('/mnt/c/Users/reyha/Documents/SIS_Analysis_Windows/data/tokyo_bay_DO_analysis_package.zip')

# Step mapping for reproducible package
STEP_MAPPING = {
    'step2_hypoxia_frequency_calculation': 'step1_hypoxia_frequency_calculation',
    'step3_decorrelation_scale_analysis': 'step2_decorrelation_scale_analysis',
    'step4_PCA_analysis': 'step3_PCA_analysis',
    'step5_environmental_factor_correlation_analysis': 'step4_environmental_factor_correlation_analysis'
}

def clear_staging():
    if STAGING_DIR.exists():
        shutil.rmtree(STAGING_DIR)
    STAGING_DIR.mkdir(parents=True)

def copy_file(src, dst_relative):
    dst = STAGING_DIR / dst_relative
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

def filter_do_data():
    print("Extracting Granular Observation Data for Tokyo Bay...")
    do_path = ROOT_DIR / 'data/processed/tokyo_bay_gdf.feather'
    if do_path.exists():
        try:
            tokyo_df = pd.read_feather(do_path)
            
            # Filter for both surface (1) and bottom (2) layers
            tokyo_df = tokyo_df[tokyo_df['saisuipoin'].isin([1, 2])]
            
            if len(tokyo_df) > 0:
                # Select the comprehensive list of columns for reproducibility
                cols_to_keep = [
                    'surveyyear', 'surveymont', 'surveyday', 'surveyhour', 
                    'latitude', 'longitude', 'zettaicode', 'saisuipoin', 'depth',
                    'do_', 'wtemp', 'salt', 'chla', 'cod', 'tn', 'tp', 'din', 'dip', 
                    'nh4n', 'no2n', 'no3n', 'po4p', 'toc', 'doc'
                ]
                # Only keep columns that actually exist in the dataframe
                existing_cols = [c for c in cols_to_keep if c in tokyo_df.columns]
                tokyo_df = tokyo_df[existing_cols]
                
                out_path = STAGING_DIR / 'data' / 'raw_observation_data_tokyo_bay.csv'
                out_path.parent.mkdir(parents=True, exist_ok=True)
                tokyo_df.to_csv(out_path, index=False)
                print(f"Filtered granular data saved to {out_path.relative_to(STAGING_DIR)} with shape {tokyo_df.shape}")
            else:
                print("No Tokyo Bay data found in merged_gdf!")
        except Exception as e:
            print(f"Error filtering DO data: {e}")
    else:
        print("Could not find merged_gdf_saisuipoin_cleaned.feather!")

def collect_scripts_and_assets():
    print("Collecting scripts and figures and remapping step numbers...")
    
    # 1. Copy environment.yml
    if (ROOT_DIR / 'environment.yml').exists():
        copy_file(ROOT_DIR / 'environment.yml', 'environment.yml')
    
    for old_step, new_step in STEP_MAPPING.items():
        # Copy Scripts (.py)
        src_scripts = ROOT_DIR / old_step
        if src_scripts.exists():
            for p in src_scripts.rglob('*.py'):
                if p.is_file() and not p.name.startswith('.'):
                    rel_path = p.relative_to(src_scripts)
                    dst_path = Path(new_step) / 'scripts' / rel_path
                    copy_file(p, dst_path)
                    
        # Copy Figures (filtered for Tokyo Bay)
        src_figures = ROOT_DIR / 'figures' / old_step
        if src_figures.exists():
            for p in src_figures.rglob('*'):
                if p.is_file() and ('tokyo' in p.name.lower() or 'tokyo' in [part.lower() for part in p.parts]):
                    # Flatten the path to avoid Windows 260-character MAX_PATH limit
                    dst_path = Path(new_step) / 'figures' / p.name
                    copy_file(p, dst_path)
                    
        # Copy Processed Data (filtered for Tokyo Bay)
        src_data = ROOT_DIR / 'data' / 'processed' / old_step
        if src_data.exists():
            for p in src_data.rglob('*'):
                if p.is_file() and ('tokyo' in p.name.lower() or 'tokyo' in [part.lower() for part in p.parts]):
                    # Flatten the path to avoid Windows 260-character MAX_PATH limit
                    dst_path = Path('data') / 'processed' / new_step / p.name
                    copy_file(p, dst_path)

def create_readme():
    print("Generating README.md Data Dictionary...")
    readme_content = """# Tokyo Bay Scientific Reproducibility Package

This package contains the raw observation data, analysis scripts, and final processed figures for the Tokyo Bay environmental analysis.

## Execution Order & Script Details
To reproduce the analysis, execute the scripts in the following numerical order. Below is a detailed explanation of what each step folder contains and what its associated scripts do.

### 1. `step1_hypoxia_frequency_calculation`
Contains scripts to calculate and map the frequency and tendency of hypoxia (low dissolved oxygen) across the bay.
- `process11_mean_climatological_do_map.py`: Generates maps of the climatological mean dissolved oxygen levels.
- `process12_hypoxia_frequency_map.py`: Calculates and plots the spatial frequency of occurrence for hypoxic events.
- `process13_do_trend_spatial_mapping.py`: Maps the long-term linear trends of dissolved oxygen geographically.
- `process14_hypoxia_tendency_per_station.py`: Computes time-series tendencies of hypoxia per individual monitoring station.

### 2. `step2_decorrelation_scale_analysis`
Contains scripts to calculate the spatial decorrelation scales of environmental variables, determining the geographic extent over which variables co-vary.
- `process11_calculate_decorrelation_scale_per_bay.py`: Calculates the core decorrelation scales for various parameters.
- `process12_plot_decorrelation_scale_complete.py`: Generates histograms and spatial distribution figures of the decorrelation scales.

### 3. `step3_PCA_analysis`
Contains scripts to perform Principal Component Analysis (PCA) to extract the dominant modes of spatio-temporal variability in the data.
- `process11_calculate_pca_explained_variance_per_bay_raw.py`: Calculates the PCA scores and explained variance for the primary modes.
- `process12_plot_pca_timeseries_per_bay_raw.py`: Generates time series plots of the principal component scores over the survey years.
- `process13_plot_pca_eof_map_per_bay_raw.py`: Creates Empirical Orthogonal Function (EOF) spatial maps showing the geographic loading of the principal components.

### 4. `step4_environmental_factor_correlation_analysis`
Contains scripts to correlate the dominant PCA modes with secondary environmental factors (nutrients, temperature, etc.) to identify drivers of change.
- `process11_trend_grouping_and_maps.py`: Groups variables by trend similarity and maps them geographically.
- `process31_correlation_distribution.py`: Calculates correlation distributions between PCA modes and environmental factors.
- `process41_spatial_correlation_maps.py`: Maps spatial correlations across the bay.
- `process42_time_series_significant_stations_PC_correlation.py`: Plots time series correlations of significant environmental factors against the primary PCs.

## Dependencies & Environment Setup
To ensure total reproducibility, this package requires the specific conda environment used during the original analysis.
1. Install [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or Anaconda.
2. Run the following command in your terminal at the root of this package:
   `conda env create -f environment.yml`
3. Activate the environment before running any scripts:
   `conda activate sis_analysis`

## Data Dictionary: `data/raw_observation_data_tokyo_bay.csv`
This file contains the foundational multi-layer data used across all pipeline steps.

**Temporal Context**
- `surveyyear`, `surveymont`, `surveyday`, `surveyhour`: The exact timestamp of the sampling event (JST).

**Spatial & Sampling Context**
- `zettaicode`: Unique numerical identifier for fixed monitoring stations.
- `latitude`, `longitude`: Coordinate location of the station.
- `saisuipoin`: Refers to the depth of the sampling. `1` indicates surface sampling (depth = 0m). `2` indicates samples taken at the bottom depth indicated by the `depth` column.
- `depth`: The actual recorded sampling depth in meters.

**Environmental Variables**
- `do_`: Dissolved Oxygen (mg/L).
- `wtemp`: Water Temperature (°C).
- `salt`: Salinity (PSU).
- `chla`: Chlorophyll-a.
- `tn`, `tp`: Total Nitrogen, Total Phosphorus.
- `din`, `dip`: Dissolved Inorganic Nitrogen, Dissolved Inorganic Phosphorus.
- `nh4n`, `no2n`, `no3n`, `po4p`: Ammonium, Nitrite, Nitrate, Phosphate.
- `cod`, `toc`, `doc`: Chemical/Total/Dissolved Organic Carbon.
"""
    readme_path = STAGING_DIR / 'README.md'
    with open(readme_path, 'w') as f:
        f.write(readme_content)
    print("README.md created.")

def create_zip():
    print("Creating ZIP archive...")
    with zipfile.ZipFile(ZIP_OUTPUT, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(STAGING_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, STAGING_DIR)
                zipf.write(file_path, arcname)
    print(f"ZIP archive created at: {ZIP_OUTPUT}")

if __name__ == '__main__':
    clear_staging()
    filter_do_data()
    collect_scripts_and_assets()
    create_readme()
    create_zip()
    print("Export complete!")
