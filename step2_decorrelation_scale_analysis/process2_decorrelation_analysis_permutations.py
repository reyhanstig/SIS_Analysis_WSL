#!/usr/bin/env python
# coding: utf-8

import pandas as pd
import numpy as np
import geopandas as gpd
from scipy.spatial.distance import cdist
from scipy.optimize import curve_fit
from scipy import stats
import warnings
from pathlib import Path
import sys

# Ensure local scripts are importable
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.paths import ProjectPaths

warnings.filterwarnings('ignore')

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
    merged_gdf = gpd.read_feather(ProjectPaths.MERGED_DATA_FILE)
    
    base_dir = ProjectPaths.SEASONAL_DATA_DIR
    subsets = [
        "spring_surface", "spring_bottom", 
        "summer_surface", "summer_bottom", 
        "autumn_surface", "autumn_bottom", 
        "winter_surface", "winter_bottom"
    ]
    
    for subset in subsets:
        subset_path = base_dir / subset
        if not subset_path.exists():
            print(f"Skipping {subset}, path doesn't exist: {subset_path}")
            continue
            
        yearly_do_file = subset_path / 'yearly_do_df.csv'
        if not yearly_do_file.exists():
            print(f"Skipping {subset}, yearly_do_df.csv doesn't exist.")
            continue
            
        print(f"Processing {subset}...")
        
        # Load yearly DO data
        yearly_do_df = pd.read_csv(yearly_do_file, index_col=0)
        yearly_do_df.index = yearly_do_df.index.astype(str).str.zfill(8)
        
        # Extract unique station locations
        station_locs = merged_gdf.drop_duplicates('zettaicode').set_index('zettaicode')
        station_locs = station_locs.loc[yearly_do_df.index]
        
        # Project to UTM Zone 53N (EPSG:32653)
        station_locs_proj = station_locs.to_crs(epsg=32653)
        coords = list(zip(station_locs_proj.geometry.x, station_locs_proj.geometry.y))
        
        # Calculate distance matrix (km)
        dist_matrix_m = cdist(coords, coords, metric='euclidean')
        dist_matrix_km = pd.DataFrame(
            dist_matrix_m / 1000, 
            index=yearly_do_df.index,
            columns=yearly_do_df.index
        )
        
        # Save dist_matrix_km
        dist_matrix_km.to_csv(subset_path / "dist_matrix_km.csv")
        
        results_list = []
        for target_station in yearly_do_df.index:
            target_series = yearly_do_df.loc[target_station]
            correlations = yearly_do_df.corrwith(target_series, axis=1, drop=True)
            
            valid_stats = []
            for neighbor in yearly_do_df.index:
                neigh_series = yearly_do_df.loc[neighbor]
                # Calculate valid N (overlap)
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
                
                # Calculate r_crit
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
        results_df.to_csv(subset_path / "stations_decorrelation_scale.csv", index=False)
        print(f"Finished {subset}: computed {len(results_df)} stations.")

if __name__ == '__main__':
    main()
