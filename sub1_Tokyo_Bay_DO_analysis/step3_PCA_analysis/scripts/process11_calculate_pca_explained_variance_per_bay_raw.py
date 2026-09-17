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

def gaussian_weight(distance, scale):
    return np.exp(-(distance**2) / (2 * scale**2))

def interpolate_missing_do(yearly_do_df, decorrelation_df, dist_matrix, weighting_func='gaussian', min_weight=0.01):
    search_radius_factor = 2.0
    interpolated_df = yearly_do_df.copy()
    common_stations = list(set(yearly_do_df.index) & set(decorrelation_df.index) & set(dist_matrix.index))
    
    for year in yearly_do_df.columns:
        for station in common_stations:
            if not pd.isna(yearly_do_df.loc[station, year]):
                continue
            scale = decorrelation_df.loc[station, 'Decorrelation_Scale_km']
            if pd.isna(scale) or scale <= 0:
                continue
            
            search_radius = search_radius_factor * scale
            valid_stations = yearly_do_df.index[~pd.isna(yearly_do_df[year])].tolist()
            neighbors = [s for s in valid_stations if s in common_stations and s != station]
            if len(neighbors) == 0:
                continue
            
            distances = dist_matrix.loc[station, neighbors]
            within_radius = distances[distances <= search_radius]
            if len(within_radius) == 0:
                continue
            
            neighbors_in_radius = within_radius.index.tolist()
            dist_vals = dist_matrix.loc[station, neighbors_in_radius].values
            do_vals = yearly_do_df.loc[neighbors_in_radius, year].values
            weight_vals = gaussian_weight(dist_vals, scale)
            valid_mask = weight_vals > min_weight
            if valid_mask.sum() == 0:
                continue
            
            interpolated_df.loc[station, year] = (do_vals[valid_mask] * weight_vals[valid_mask]).sum() / weight_vals[valid_mask].sum()
            
    mean_fallback = interpolated_df.mean(axis=1)
    for col in interpolated_df.columns:
        interpolated_df[col] = interpolated_df[col].fillna(mean_fallback)

    return interpolated_df

def plot_explained_variance(pca_model, division):
    plt.style.use(str(ProjectPaths.PROJECT_ROOT / 'project_style.mplstyle'))
    fig, ax = plt.subplots(figsize=(8, 5))
    
    components = np.arange(1, len(pca_model.explained_variance_ratio_) + 1)
    variance_ratio = pca_model.explained_variance_ratio_ * 100
    cumulative_variance = np.cumsum(variance_ratio)
    
    ax.bar(components, variance_ratio, alpha=0.7, label='Individual Variance')
    ax.plot(components, cumulative_variance, marker='o', color='r', label='Cumulative Variance')
    
    ax.set_xlabel('Principal Component')
    ax.set_ylabel('Explained Variance (%)')
    ax.set_title(f'{division}: PCA Explained Variance')
    ax.set_xticks(components)
    ax.legend()
    
    out_path = OUTPUT_DIR / f"{division.replace(' ', '_').lower()}_pca_explained_variance_raw.png"
    plt.savefig(out_path, bbox_inches='tight', dpi=300)
    plt.close()

def main():
    ProjectPaths.ensure_directories()
    division = args.division
    
    step1_param_file = ProjectPaths.PROJECT_ROOT / "step1_data_processing_cleaning" / "step1_parameter.csv"
    step1_params = {}
    if step1_param_file.exists():
        df_p = pd.read_csv(step1_param_file)
        for _, row in df_p.iterrows():
            step1_params[row['parameter_name']] = row['value']
    season = step1_params.get('season', 'Summer')
    layer = step1_params.get('layer', 'bottom')
    
    yearly_do_file = ProjectPaths.get_subset_dir(season, layer) / "yearly_do_df.csv"
    if not yearly_do_file.exists():
        print(f"Error: Pre-filtered data file {yearly_do_file} does not exist.")
        return
        
    yearly_do_df = pd.read_csv(yearly_do_file, index_col=0)
    yearly_do_df.index = yearly_do_df.index.astype(str).str.zfill(8)
    
    merged_gdf = load_and_process_data(force_reload=False)
    
    dist_matrix_file = ProjectPaths.PROCESSED_DATA_DIR / "dist_matrix_km.csv"
    if not dist_matrix_file.exists():
        print("Error: dist_matrix_km.csv not found.")
        return
    dist_matrix_km = pd.read_csv(dist_matrix_file, index_col=0)
    dist_matrix_km.index = dist_matrix_km.index.astype(str).str.zfill(8)
    dist_matrix_km.columns = dist_matrix_km.columns.astype(str).str.zfill(8)

    db_division = division
    if division in ['Ise Mikawa Bay', 'Ise-Mikawa Bay']:
        db_division = 'Ise Bay'
        
    division_stations = merged_gdf[
        (merged_gdf['watermass_name'] == db_division) | 
        (merged_gdf['division'] == db_division)
    ]['zettaicode'].unique()
    
    division_stations_str = [str(st).zfill(8) for st in division_stations]
    yearly_do_df_div = yearly_do_df[yearly_do_df.index.isin(division_stations_str)].copy()
    
    if yearly_do_df_div.empty:
        print(f"No station data found in yearly_do_df for {division}.")
        return
        
    decorrelation_file = ProjectPaths.PROCESSED_DATA_DIR / "step3_decorrelation_scale_analysis" / "process11_calculate_decorrelation_scale_per_bay" / division.replace(' ', '_').lower() / f"{division.replace(' ', '_').lower()}_decorrelation_scale.csv"
    if not decorrelation_file.exists():
        print(f"Decorrelation scale file not found for {division}. Skipping.")
        return
        
    decorrelation_df = pd.read_csv(decorrelation_file, index_col='Station_ID')
    decorrelation_df.index = decorrelation_df.index.astype(str).str.zfill(8)
    
    interpolated_do_df = interpolate_missing_do(yearly_do_df_div, decorrelation_df, dist_matrix_km)
    interpolated_do_df = interpolated_do_df.fillna(interpolated_do_df.mean(axis=0))
    
    if interpolated_do_df.empty or len(interpolated_do_df) < 2:
        print(f"Insufficient interpolated data for {division}.")
        return
        
    pca_input_data = interpolated_do_df.T
    
    n_components = min(10, len(interpolated_do_df), len(interpolated_do_df.columns))
    if n_components < 2:
        print(f"Not enough components for {division}.")
        return
        
    pca_model = PCA(n_components=n_components)
    pca_result = pca_model.fit_transform(pca_input_data)
    
    years = interpolated_do_df.columns.astype(int)
    
    pc_scores = pd.DataFrame({'PC1': pca_result[:, 0], 'PC2': pca_result[:, 1]}, index=years)
    out_name = division.replace(' ', '_').lower()
    pc_scores.to_csv(PROCESSED_DATA_DIR / f"{out_name}_pc_scores.csv")
    
    eof1 = pca_model.components_[0, :]
    eof2 = pca_model.components_[1, :]
    eof_df = pd.DataFrame({
        'Station_ID': interpolated_do_df.index,
        'EOF1': eof1,
        'EOF2': eof2
    })
    eof_df.to_csv(PROCESSED_DATA_DIR / f"{out_name}_eof_patterns.csv", index=False)
    
    var_df = pd.DataFrame({
        'PC': ['PC1', 'PC2'],
        'Variance_Pct': [pca_model.explained_variance_ratio_[0]*100, pca_model.explained_variance_ratio_[1]*100]
    })
    var_df.to_csv(PROCESSED_DATA_DIR / f"{out_name}_pca_variance.csv", index=False)
    
    plot_explained_variance(pca_model, division)

if __name__ == "__main__":
    main()
