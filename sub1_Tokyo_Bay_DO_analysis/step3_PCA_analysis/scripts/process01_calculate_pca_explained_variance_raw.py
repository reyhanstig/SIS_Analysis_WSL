#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# --- BOILERPLATE INJECTED BY AGENT ---
import os
import pandas as pd
import logging
import matplotlib.pyplot as plt

CURRENT_SCRIPT = Path(__file__).resolve()
sys.path.insert(0, str(CURRENT_SCRIPT.parent.parent))
STEP_DIR = CURRENT_SCRIPT.parent.name
SCRIPT_NAME = CURRENT_SCRIPT.stem
import shutil

PROCESSED_DATA_DIR = Path('/home/reyha/SIS_Analysis_WSL/data/processed') / STEP_DIR / SCRIPT_NAME
if PROCESSED_DATA_DIR.exists():
    shutil.rmtree(PROCESSED_DATA_DIR, ignore_errors=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_DIR = Path('/home/reyha/SIS_Analysis_WSL/figures') / STEP_DIR / SCRIPT_NAME
if OUTPUT_DIR.exists():
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

step_num = STEP_DIR.split('_')[0].replace('step', '')
log_file = CURRENT_SCRIPT.parent / f"log_process{step_num}.txt"
logging.basicConfig(level=logging.INFO, filename=log_file, format='%(levelname)s: %(message)s')

param_file = CURRENT_SCRIPT.parent / f"step{step_num}_parameter.csv"
PARAMS = {}
if param_file.exists():
    df_params = pd.read_csv(param_file)
    if 'parameter_name' in df_params.columns and 'value' in df_params.columns:
        for _, row in df_params.iterrows():
            PARAMS[row['parameter_name']] = row['value']
# -------------------------------------

import warnings
import numpy as np
import geopandas as gpd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import seaborn as sns
import cartopy.crs as ccrs
import cartopy.feature as cfeature

warnings.filterwarnings('ignore')

from utils.paths import ProjectPaths
from utils.mapping_config import MappingConfig
from utils.data_loader import load_and_process_data

def plot_explained_variance(pca_model):
    plt.style.use(str(ProjectPaths.PROJECT_ROOT / 'project_style.mplstyle'))
    fig, ax = plt.subplots(figsize=(8, 5))
    
    components = np.arange(1, len(pca_model.explained_variance_ratio_) + 1)
    variance_ratio = pca_model.explained_variance_ratio_ * 100
    cumulative_variance = np.cumsum(variance_ratio)
    
    ax.bar(components, variance_ratio, alpha=0.7, label='Individual Variance')
    ax.plot(components, cumulative_variance, marker='o', color='r', label='Cumulative Variance')
    
    ax.set_xlabel('Principal Component')
    ax.set_ylabel('Explained Variance (%)')
    ax.set_title('PCA Explained Variance')
    ax.set_xticks(components)
    ax.legend()
    
    out_path = OUTPUT_DIR / 'pca_explained_variance_raw.png'
    plt.savefig(out_path, bbox_inches='tight', dpi=300)
    plt.close()
    print(f"Saved explained variance plot to: {out_path}")

def main():
    ProjectPaths.ensure_directories()
    
    step1_param_file = ProjectPaths.PROJECT_ROOT / "step1_data_processing_cleaning" / "step1_parameter.csv"
    step1_params = {}
    if step1_param_file.exists():
        df_p = pd.read_csv(step1_param_file)
        for _, row in df_p.iterrows():
            step1_params[row['parameter_name']] = row['value']
    season = step1_params.get('season', 'Summer')
    layer = step1_params.get('layer', 'bottom')
    
    subset_dir = ProjectPaths.get_subset_dir(season, layer)
    interpolated_do_file = subset_dir / "interpolated_do_df.csv"
    if not interpolated_do_file.exists():
        print(f"Error: Interpolated DO data does not exist.")
        return
        
    interpolated_do_df = pd.read_csv(interpolated_do_file, index_col=0)
    interpolated_do_df.index = interpolated_do_df.index.astype(str).str.zfill(8)
    
    # Fill remaining NaNs with the temporal mean
    interpolated_do_df = interpolated_do_df.fillna(interpolated_do_df.mean(axis=0))
    
    print("Performing PCA analysis (RAW)...")
    pca_input_data = interpolated_do_df.T
    
    pca_model = PCA(n_components=10)
    pca_result = pca_model.fit_transform(pca_input_data)
    
    years = interpolated_do_df.columns.astype(int)
    
    pc_scores = pd.DataFrame({'PC1': pca_result[:, 0], 'PC2': pca_result[:, 1]}, index=years)
    pc_scores.to_csv(PROCESSED_DATA_DIR / 'pc_scores.csv')
    
    eof1 = pca_model.components_[0, :]
    eof2 = pca_model.components_[1, :]
    eof_df = pd.DataFrame({
        'Station_ID': interpolated_do_df.index,
        'EOF1': eof1,
        'EOF2': eof2
    })
    eof_df.to_csv(PROCESSED_DATA_DIR / 'eof_patterns.csv', index=False)
    
    # Save variance info
    var_df = pd.DataFrame({
        'PC': ['PC1', 'PC2'],
        'Variance_Pct': [pca_model.explained_variance_ratio_[0]*100, pca_model.explained_variance_ratio_[1]*100]
    })
    var_df.to_csv(PROCESSED_DATA_DIR / 'pca_variance.csv', index=False)
    
    plot_explained_variance(pca_model)

if __name__ == "__main__":
    main()
