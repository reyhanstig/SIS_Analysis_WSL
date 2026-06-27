#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# --- BOILERPLATE INJECTED BY AGENT ---
import os
import sys
import pandas as pd
import logging
import matplotlib.pyplot as plt
from pathlib import Path

CURRENT_SCRIPT = Path(__file__).resolve()
# Fix namespace shadowing by inserting project root at index 0
sys.path.insert(0, str(CURRENT_SCRIPT.parent.parent))
STEP_DIR = CURRENT_SCRIPT.parent.name
SCRIPT_NAME = CURRENT_SCRIPT.stem
import shutil
PROCESSED_DATA_DIR = Path('/home/reyha/SIS_Analysis_WSL/data/processed') / STEP_DIR / SCRIPT_NAME
if PROCESSED_DATA_DIR.exists():
    shutil.rmtree(PROCESSED_DATA_DIR, ignore_errors=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

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
from scipy.spatial.distance import cdist
from scipy.optimize import curve_fit
from scipy import stats

warnings.filterwarnings('ignore')

from utils.paths import ProjectPaths

# Parameters
r_crit_alpha = 0.01
distance_cutoff_km = 100
min_periods = 15

def gaussian_model_with_offset(x, A, dx):
    B = 1 - A
    return A * np.exp(-(x / dx)**2) + B

def calculate_r_crit(n, alpha=0.01):
    df = n - 2
    if df <= 0: return 1.0  # Safety
    t_val = stats.t.ppf(1 - alpha/2, df)
    r_crit = np.sqrt(t_val**2 / (df + t_val**2))
    return r_crit

def count_neighbors_within_distance(target_station, dist_matrix_km, max_distance_km=100):
    distances = dist_matrix_km.loc[target_station]
    neighbors = distances[(distances > 0) & (distances <= max_distance_km)]
    return len(neighbors)

def main():
    ProjectPaths.ensure_directories()
    
    # Retrieve season and layer from Step 1 parameters
    step1_param_file = ProjectPaths.PROJECT_ROOT / "step1_data_processing_cleaning" / "step1_parameter.csv"
    step1_params = {}
    if step1_param_file.exists():
        df_p = pd.read_csv(step1_param_file)
        for _, row in df_p.iterrows():
            step1_params[row['parameter_name']] = row['value']
    season = step1_params.get('season', 'Summer')
    layer = step1_params.get('layer', 'bottom')
    
    subset_dir = ProjectPaths.get_subset_dir(season, layer)
    yearly_do_file = subset_dir / 'yearly_do_df.csv'
    
    if not yearly_do_file.exists():
        print(f"Error: Pre-filtered data file {yearly_do_file} does not exist. Please run Step 1 first.")
        return
        
    print(f"Processing single filtered subset: {season}_{layer}...")
    
    # Load the merged data coordinates
    merged_gdf = gpd.read_feather(ProjectPaths.MERGED_DATA_FILE)
    
    # Load yearly DO data
    yearly_do_df = pd.read_csv(yearly_do_file, index_col=0)
    yearly_do_df.index = yearly_do_df.index.astype(str).str.zfill(8)
    
    # Extract unique station locations
    station_locs = merged_gdf.drop_duplicates('zettaicode').set_index('zettaicode')
    station_locs.index = station_locs.index.astype(str).str.zfill(8)
    station_locs = station_locs.loc[station_locs.index.intersection(yearly_do_df.index)]
    
    if station_locs.empty:
        print("No matching stations found with coordinates. Exiting.")
        return
        
    # Project to UTM Zone 53N (EPSG:32653)
    station_locs_proj = station_locs.to_crs(epsg=32653)
    coords = list(zip(station_locs_proj.geometry.x, station_locs_proj.geometry.y))
    
    # Calculate distance matrix (km)
    dist_matrix_m = cdist(coords, coords, metric='euclidean')
    dist_matrix_km = pd.DataFrame(
        dist_matrix_m / 1000, 
        index=station_locs.index,
        columns=station_locs.index
    )
    
    # Save dist_matrix_km to pipeline & legacy directory
    dist_matrix_km.to_csv(PROCESSED_DATA_DIR / "dist_matrix_km.csv")
    dist_matrix_km.to_csv(subset_dir / "dist_matrix_km.csv")
    
    results_list = []
    for target_station in yearly_do_df.index:
        if target_station not in dist_matrix_km.index:
            continue
            
        target_series = yearly_do_df.loc[target_station]
        correlations = yearly_do_df.corrwith(target_series, axis=1, drop=True)
        
        valid_stats = []
        for neighbor in yearly_do_df.index:
            if neighbor not in dist_matrix_km.index:
                continue
            neigh_series = yearly_do_df.loc[neighbor]
            valid_count = pd.concat([target_series, neigh_series], axis=1).dropna().shape[0]
            
            if valid_count >= min_periods:
                if neighbor == target_station:
                    corr_val = 1.0
                    dist_val = 0.0
                else:
                    corr_val = correlations[neighbor]
                    dist_val = dist_matrix_km.loc[target_station, neighbor]
                
                if not np.isnan(corr_val) and not np.isnan(dist_val):
                    if dist_val <= distance_cutoff_km:
                        valid_stats.append({'dist': dist_val, 'corr': corr_val, 'n': valid_count})
                        
        df_fit = pd.DataFrame(valid_stats)
        if len(df_fit) < 5: continue
            
        x_data = df_fit['dist'].values
        y_data = df_fit['corr'].values
        
        try:
            popt, pcov = curve_fit(
                gaussian_model_with_offset, x_data, y_data, 
                p0=[1.0, 50.0], bounds=([0, 0.001], [2.0, np.inf])
            )
            A_fit, dx_fit_param = popt
            B_fit = 1 - A_fit
            
            n_neighbors_100km = count_neighbors_within_distance(target_station, dist_matrix_km, max_distance_km=distance_cutoff_km)
            
            if n_neighbors_100km >= 2:
                r_crit = calculate_r_crit(n_neighbors_100km, alpha=r_crit_alpha)
            else:
                avg_n = df_fit['n'].mean()
                r_crit = calculate_r_crit(avg_n, alpha=r_crit_alpha)
            
            if A_fit > 0 and (r_crit - B_fit) / A_fit > 0:
                inner_val = (r_crit - B_fit) / A_fit
                if inner_val < 1:
                    decorrelation_scale = dx_fit_param * np.sqrt(-np.log(inner_val))
                else:
                    decorrelation_scale = 0.0
            else:
                decorrelation_scale = 0.0
            
            # R-squared
            residuals = y_data - gaussian_model_with_offset(x_data, *popt)
            ss_res = np.sum(residuals**2)
            ss_tot = np.sum((y_data - np.mean(y_data))**2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
            
            results_list.append({
                'Station_ID': target_station,
                'Decorrelation_Scale_km': decorrelation_scale,
                'Amplitude_A': A_fit,
                'Offset_B': B_fit,
                'dx_param': dx_fit_param,
                'R_squared': r_squared,
                'r_crit': r_crit,
                'n_neighbors_100km': n_neighbors_100km
            })
        except Exception as e:
            pass
            
    results_df = pd.DataFrame(results_list)
    results_df.to_csv(PROCESSED_DATA_DIR / "stations_decorrelation_scale.csv", index=False)
    results_df.to_csv(subset_dir / "stations_decorrelation_scale.csv", index=False)
    print(f"Finished: computed decorrelation scales for {len(results_df)} stations in {season}_{layer}.")

if __name__ == '__main__':
    main()
