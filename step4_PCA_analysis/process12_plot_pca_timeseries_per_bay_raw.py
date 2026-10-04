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
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--division', type=str, required=True)
args, unknown = parser.parse_known_args()

PROCESSED_DATA_DIR = Path('/home/reyha/SIS_Analysis_WSL/data/processed') / STEP_DIR / SCRIPT_NAME / args.division.replace(' ', '_').lower()
if PROCESSED_DATA_DIR.exists():
    import shutil
    shutil.rmtree(PROCESSED_DATA_DIR, ignore_errors=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_DIR = Path('/home/reyha/SIS_Analysis_WSL/figures') / STEP_DIR / SCRIPT_NAME / args.division.replace(' ', '_').lower()
if OUTPUT_DIR.exists():
    import shutil
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def plot_pc_timeseries(pc_scores, division, var_df):
    plt.style.use(str(ProjectPaths.PROJECT_ROOT / 'project_style.mplstyle'))
    
    # Extract variance percentages
    pc1_var = var_df[var_df['PC'] == 'PC1']['Variance_Pct'].values[0] if var_df is not None and not var_df.empty else 0.0
    pc2_var = var_df[var_df['PC'] == 'PC2']['Variance_Pct'].values[0] if var_df is not None and not var_df.empty else 0.0

    # 1. Determine dynamic tick years
    first_year = pc_scores.index[0]
    last_year = pc_scores.index[-1]
    target_type = type(first_year)
    mid_ticks = [target_type(y) for y in range(1985, 2021, 5) if target_type(y) in pc_scores.index]
    tick_years = sorted(list(set([first_year] + mid_ticks + [last_year])), key=lambda x: int(x))

    # --- Plot Combined ---
    fig, ax = plt.subplots(figsize=(10, 5))
    
    ax.plot(pc_scores.index, pc_scores['PC1'], marker='o', label=f'PC1 ({pc1_var:.1f}%)', color='tab:blue')
    ax.plot(pc_scores.index, pc_scores['PC2'], marker='s', label=f'PC2 ({pc2_var:.1f}%)', color='darkgoldenrod')
    
    ax.axhline(y=0, color='red', linestyle='--', alpha=0.7)
    ax.set_xlabel('Year')
    ax.set_ylabel('PC Score')
    ax.set_title(f'{division}: Principal Component Time Series', fontsize=20, fontweight='bold')
    
    # grid lines at the same positions
    ax.set_xticks(tick_years)
    ax.tick_params(axis='x', rotation=45)
    ax.grid(True, linestyle='--', alpha=0.6)
    
    ax.legend(fontsize=16)
    
    out_path = OUTPUT_DIR / f"{division.replace(' ', '_').lower()}_pc_timeseries_raw.png"
    plt.tight_layout()
    plt.savefig(out_path, bbox_inches='tight', dpi=300)
    plt.close()

    # --- Plot PC1 only ---
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(pc_scores.index, pc_scores['PC1'], marker='o', label=f'PC1 ({pc1_var:.1f}%)', color='tab:blue')
    
    ax.axhline(y=0, color='red', linestyle='--', alpha=0.7)
    ax.set_xlabel('Year')
    ax.set_ylabel('PC1 Score')
    ax.set_title(f'{division}: PC1 Time Series', fontsize=20, fontweight='bold')
    
    ax.set_xticks(tick_years)
    ax.tick_params(axis='x', rotation=45)
    ax.grid(True, linestyle='--', alpha=0.6)
    
    ax.legend(fontsize=16)
    
    out_path1 = OUTPUT_DIR / f"{division.replace(' ', '_').lower()}_pc1_timeseries_raw.png"
    plt.tight_layout()
    plt.savefig(out_path1, bbox_inches='tight', dpi=300)
    plt.close()

    # --- Plot PC2 only ---
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(pc_scores.index, pc_scores['PC2'], marker='s', label=f'PC2 ({pc2_var:.1f}%)', color='darkgoldenrod')
    
    ax.axhline(y=0, color='red', linestyle='--', alpha=0.7)
    ax.set_xlabel('Year')
    ax.set_ylabel('PC2 Score')
    ax.set_title(f'{division}: PC2 Time Series', fontsize=20, fontweight='bold')
    
    ax.set_xticks(tick_years)
    ax.tick_params(axis='x', rotation=45)
    ax.grid(True, linestyle='--', alpha=0.6)
    
    ax.legend(fontsize=16)
    
    out_path2 = OUTPUT_DIR / f"{division.replace(' ', '_').lower()}_pc2_timeseries_raw.png"
    plt.tight_layout()
    plt.savefig(out_path2, bbox_inches='tight', dpi=300)
    plt.close()

def main():
    ProjectPaths.ensure_directories()
    division = args.division
    out_name = division.replace(' ', '_').lower()
    
    data_dir = ProjectPaths.PROCESSED_DATA_DIR / STEP_DIR / "process11_calculate_pca_explained_variance_per_bay_raw" / out_name
    pc_scores_file = data_dir / f"pca_scores_{out_name}.csv"
    var_file = data_dir / f"{out_name}_pca_variance.csv"
    
    if not pc_scores_file.exists():
        print(f"Error: {pc_scores_file} not found.")
        return
        
    pc_scores = pd.read_csv(pc_scores_file, index_col=0)
    var_df = pd.read_csv(var_file) if var_file.exists() else None
    plot_pc_timeseries(pc_scores, division, var_df)

if __name__ == "__main__":
    main()
