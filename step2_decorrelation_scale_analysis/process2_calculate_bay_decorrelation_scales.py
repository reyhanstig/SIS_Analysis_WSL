#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Calculate decorrelation scales for Tokyo Bay and Ise Bay
and save the results to processed data directory as CSVs.
"""

import sys
from pathlib import Path
import warnings
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.spatial.distance import cdist
from scipy.optimize import curve_fit
from scipy import stats

warnings.filterwarnings('ignore')

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from scripts.data_loader import load_and_process_data
from utils.paths import ProjectPaths

def gaussian_model_with_offset(x, A, dx):
    """Gaussian decay with offset, constrained: A + B = 1"""
    B = 1 - A
    return A * np.exp(-(x / dx)**2) + B

def calculate_r_crit(n, alpha=0.01):
    """Calculate critical correlation value for significance test."""
    if n < 3:
        return 1.0
    df = n - 2
    t_crit = stats.t.ppf(1 - alpha/2, df)
    r_crit = np.sqrt(t_crit**2 / (t_crit**2 + df))
    return r_crit

def count_neighbors_within_distance(target_station, dist_matrix, max_distance_km=100):
    """Count number of stations within max_distance_km of target_station"""
    distances = dist_matrix.loc[target_station]
    neighbors = distances[(distances > 0) & (distances <= max_distance_km)]
    return len(neighbors)

def compute_bay_decorrelation(bay_name, representative_month):
    print(f"\nProcessing decorrelation scales for {bay_name} (Month: {representative_month})...")
    
    # Load and filter data
    merged_gdf = load_and_process_data(force_reload=False)
    bay_gdf = merged_gdf[merged_gdf['watermass_name'] == bay_name].copy()
    
    min_periods = 15
    r_crit_alpha = 0.01
    distance_cutoff_km = 100
    
    # Filter for Summer Bottom
    summer_bottom = bay_gdf[
        (bay_gdf['season'] == 'Summer') & 
        (bay_gdf['saisuipoin'] == 2) &
        (bay_gdf['surveymont'] == representative_month)
    ].copy()
    summer_bottom['do_'] = pd.to_numeric(summer_bottom['do_'], errors='coerce')
    summer_bottom = summer_bottom.dropna(subset=['do_']).copy()
    
    if len(summer_bottom) == 0:
        print(f"No summer bottom DO data found for {bay_name}.")
        return pd.DataFrame()
        
    # Build yearly DO matrix (stations x years)
    yearly_do_df = summer_bottom.groupby(['zettaicode', 'year'])['do_'].mean().unstack('year')
    
    # Filter stations with insufficient temporal data
    yearly_do_df = yearly_do_df[yearly_do_df.notna().sum(axis=1) >= min_periods]
    print(f"Yearly DO DataFrame shape: {yearly_do_df.shape}")
    print(f"  - {yearly_do_df.shape[0]} stations with >= {min_periods} valid years")
    
    if yearly_do_df.empty:
        print(f"No stations with >= {min_periods} valid years found for {bay_name}.")
        return pd.DataFrame()
        
    # Get station coordinates
    station_coords = bay_gdf[['zettaicode', 'geometry']].drop_duplicates('zettaicode')
    station_coords = station_coords[station_coords['zettaicode'].isin(yearly_do_df.index)]
    station_coords = station_coords.set_index('zettaicode')
    
    # Project to UTM Zone 53N (meter-based)
    stns_utm = gpd.GeoDataFrame(station_coords, geometry='geometry', crs=bay_gdf.crs)
    stns_utm = stns_utm.to_crs(epsg=32653)
    
    # Calculate pairwise distance matrix in km
    coords = np.array([(geom.x, geom.y) for geom in stns_utm['geometry']])
    dist_matrix = cdist(coords, coords) / 1000.0
    dist_matrix_km = pd.DataFrame(dist_matrix, index=stns_utm.index, columns=stns_utm.index)
    
    results_list = []
    for target_station in yearly_do_df.index:
        target_series = yearly_do_df.loc[target_station]
        correlations = yearly_do_df.corrwith(target_series, axis=1, drop=True)
        
        valid_stats = []
        for neighbor in yearly_do_df.index:
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
        if len(df_fit) < 5:
            continue
            
        x_data = df_fit['dist'].values
        y_data = df_fit['corr'].values
        
        try:
            # Fit Gaussian Model with offset (A + B = 1 constraint)
            popt, pcov = curve_fit(
                gaussian_model_with_offset, x_data, y_data,
                p0=[1.0, 50.0], bounds=([0, 0.001], [2.0, np.inf])
            )
            A_fit, dx_fit_param = popt
            B_fit = 1 - A_fit
            
            n_neighbors_100km = count_neighbors_within_distance(
                target_station, dist_matrix_km, max_distance_km=distance_cutoff_km
            )
            
            if n_neighbors_100km >= 2:
                r_crit = calculate_r_crit(n_neighbors_100km, alpha=r_crit_alpha)
            else:
                avg_n = df_fit['n'].mean()
                r_crit = calculate_r_crit(avg_n, alpha=r_crit_alpha)
            
            # Solve for decorrelation scale
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
            print(f"Fitting failed for station {target_station}: {e}")
            
    results_df = pd.DataFrame(results_list)
    print(f"Successfully calculated decorrelation scales for {len(results_df)} stations.")
    return results_df

def main():
    ProjectPaths.ensure_directories()
    
    # 1. Tokyo Bay (Month 8 = August)
    tokyo_df = compute_bay_decorrelation("Tokyo Bay", 8)
    if not tokyo_df.empty:
        out_path = ProjectPaths.PROCESSED_DATA_DIR / "tokyo_bay_decorrelation_scale.csv"
        tokyo_df.to_csv(out_path, index=False)
        print(f"Saved Tokyo Bay decorrelation scales to: {out_path}")
        
    # 2. Ise Bay (Month 7 = July)
    ise_df = compute_bay_decorrelation("Ise Bay", 7)
    if not ise_df.empty:
        out_path = ProjectPaths.PROCESSED_DATA_DIR / "ise_bay_decorrelation_scale.csv"
        ise_df.to_csv(out_path, index=False)
        print(f"Saved Ise Bay decorrelation scales to: {out_path}")

if __name__ == "__main__":
    main()
