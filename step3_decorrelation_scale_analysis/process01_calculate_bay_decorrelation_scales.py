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

from utils.data_loader import load_and_process_data
from utils.paths import ProjectPaths
from utils.mapping_config import MappingConfig

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

def compute_decorrelation_for_division(division, yearly_do_df, merged_gdf):
    print(f"\nProcessing decorrelation scales for division/bay: {division}...")
    
    # Map division to watermass_name / division in merged_gdf
    db_division = division
    if division in ['Ise Mikawa Bay', 'Ise-Mikawa Bay']:
        db_division = 'Ise Bay'
        
    # Filter stations belonging to this division/bay
    division_stations = merged_gdf[
        (merged_gdf['watermass_name'] == db_division) | 
        (merged_gdf['division'] == db_division)
    ]['zettaicode'].unique()
    
    division_stations_str = [str(st).zfill(8) for st in division_stations]
    
    yearly_do_df_div = yearly_do_df[yearly_do_df.index.isin(division_stations_str)].copy()
    
    if yearly_do_df_div.empty:
        print(f"No station data found in yearly_do_df for {division}.")
        return pd.DataFrame()
        
    min_periods = 15
    r_crit_alpha = 0.01
    distance_cutoff_km = 100
    
    # Get station coordinates
    station_coords = merged_gdf[['zettaicode', 'geometry']].drop_duplicates('zettaicode')
    station_coords['zettaicode_str'] = station_coords['zettaicode'].astype(str).str.zfill(8)
    station_coords = station_coords[station_coords['zettaicode_str'].isin(yearly_do_df_div.index)]
    station_coords = station_coords.set_index('zettaicode_str')
    
    if len(station_coords) < 5:
        print(f"Too few stations ({len(station_coords)}) in {division} for fitting. Skipping.")
        return pd.DataFrame()
        
    # Project to UTM Zone 53N (meter-based)
    stns_utm = gpd.GeoDataFrame(station_coords, geometry='geometry', crs=merged_gdf.crs)
    stns_utm = stns_utm.to_crs(epsg=32653)
    
    # Calculate pairwise distance matrix in km
    coords = np.array([(geom.x, geom.y) for geom in stns_utm['geometry']])
    dist_matrix = cdist(coords, coords) / 1000.0
    dist_matrix_km = pd.DataFrame(dist_matrix, index=stns_utm.index, columns=stns_utm.index)
    
    results_list = []
    for target_station in yearly_do_df_div.index:
        target_series = yearly_do_df_div.loc[target_station]
        correlations = yearly_do_df_div.corrwith(target_series, axis=1, drop=True)
        
        valid_stats = []
        for neighbor in yearly_do_df_div.index:
            neigh_series = yearly_do_df_div.loc[neighbor]
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
            pass
            
    results_df = pd.DataFrame(results_list)
    print(f"Successfully calculated decorrelation scales for {len(results_df)} stations in {division}.")
    return results_df

def plot_simple_decorrelation_scale(division, results_df, merged_gdf):
    if results_df.empty:
        print(f"No results to plot for {division}")
        return
        
    import matplotlib.pyplot as plt
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    from utils.mapping_config import MappingConfig
    
    plt.style.use(str(ProjectPaths.PROJECT_ROOT / 'project_style.mplstyle'))
    try:
        import cmocean
        import xarray as xr
        gebco_path = ProjectPaths.BOUNDARIES_DIR / "gebco_2024_n35.5_s34.0_w139.0_e140.5.nc"
        gebco = xr.open_dataset(gebco_path)
        has_gebco = True
    except:
        has_gebco = False
        cmocean = None

    station_coords_wgs84 = merged_gdf[['zettaicode', 'latitude', 'longitude']].drop_duplicates('zettaicode')
    station_coords_wgs84['zettaicode_str'] = station_coords_wgs84['zettaicode'].astype(str).str.zfill(8)
    plot_data = station_coords_wgs84.merge(results_df, left_on='zettaicode_str', right_on='Station_ID')
    
    if plot_data.empty:
        print(f"No coordinates found for simple plot of {division}")
        return
        
    map_extent = MappingConfig.get_dynamic_extent(division, plot_data=plot_data)
    
    fig_width, fig_height = MappingConfig.get_dynamic_figsize(map_extent, base_width=8)
    fig, ax = plt.subplots(figsize=(fig_width, fig_height), subplot_kw={'projection': ccrs.PlateCarree()})
    ax.set_facecolor(MappingConfig.COLOR_OCEAN)
    
    ax.add_feature(cfeature.LAND, facecolor=MappingConfig.COLOR_LAND, zorder=MappingConfig.ZORDER_CARTOPY_LAND)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5, edgecolor='black', zorder=MappingConfig.ZORDER_CARTOPY_COASTLINE)
    
    db_division = division
    if division in ['Ise Mikawa Bay', 'Ise-Mikawa Bay']:
        db_division = 'Ise Bay'
        
    if has_gebco and db_division == 'Tokyo Bay' and cmocean is not None:
        bath = gebco['elevation'].values
        lons = gebco['lon'].values
        lats = gebco['lat'].values
        bath_masked = np.where(bath < 0, bath, np.nan)
        ax.pcolormesh(lons, lats, bath_masked, cmap=cmocean.cm.deep, 
                      transform=ccrs.PlateCarree(), zorder=0.1)
    
    extent_width = map_extent[1] - map_extent[0]
    zoom_factor = max(4.5 / extent_width, 1.0)
    
    cmap_to_use = cmocean.cm.thermal if cmocean is not None else 'viridis'
    sc = ax.scatter(
        plot_data['longitude'], plot_data['latitude'],
        c=plot_data['Decorrelation_Scale_km'],
        cmap=cmap_to_use,
        s=60 * zoom_factor, edgecolors='k', linewidths=0.5,
        transform=ccrs.PlateCarree(),
        zorder=MappingConfig.ZORDER_PREDICTED
    )
    
    gl = MappingConfig.apply_gridlines(ax)
    
    ax.set_extent(map_extent, crs=ccrs.PlateCarree())
    plt.title(f'{division}: Decorrelation Scale (km) [Simple]')
    
    plt.subplots_adjust(bottom=0.15)
    cbar_ax = fig.add_axes([0.25, 0.05, 0.5, 0.03])
    cbar = fig.colorbar(sc, cax=cbar_ax, orientation='horizontal')
    cbar.set_label('Decorrelation Scale (km)')
    
    figures_dir = ProjectPaths.FIGURES_DIR / "step3_decorrelation_scale_analysis" / "10_calculate_bay_decorrelation_scales"
    figures_dir.mkdir(parents=True, exist_ok=True)
    out_img = figures_dir / f"{division.replace(' ', '_').lower()}_decorrelation_scale_simple.png"
    plt.savefig(out_img, bbox_inches='tight', dpi=300)
    plt.close()
    print(f"Saved simple decorrelation scale plot for {division} to: {out_img}")

def plot_decorrelation_scale(division, results_df, merged_gdf):
    if results_df.empty:
        print(f"No results to plot for {division}")
        return
        
    import matplotlib.pyplot as plt
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    from utils.mapping_config import MappingConfig
    
    plt.style.use(str(ProjectPaths.PROJECT_ROOT / 'project_style.mplstyle'))
    
    # Merge results with station coordinates
    station_coords_wgs84 = merged_gdf[['zettaicode', 'latitude', 'longitude']].drop_duplicates('zettaicode')
    station_coords_wgs84['zettaicode_str'] = station_coords_wgs84['zettaicode'].astype(str).str.zfill(8)
    plot_data = station_coords_wgs84.merge(results_df, left_on='zettaicode_str', right_on='Station_ID')
    
    if plot_data.empty:
        print(f"No coordinates found for plotting {division}")
        return
        
    map_extent = MappingConfig.get_dynamic_extent(division, plot_data=plot_data)
    fig_width, fig_height = MappingConfig.get_dynamic_figsize(map_extent, base_width=10)
    fig, ax = plt.subplots(figsize=(fig_width, fig_height), subplot_kw={'projection': ccrs.PlateCarree()})
    ax.set_facecolor(MappingConfig.COLOR_OCEAN)
    
    # Cartopy land and coastline
    ax.add_feature(cfeature.LAND, facecolor=MappingConfig.COLOR_LAND, zorder=MappingConfig.ZORDER_CARTOPY_LAND)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5, edgecolor='black', zorder=MappingConfig.ZORDER_CARTOPY_COASTLINE)
    
    # Optional boundary plotting
    try:
        db_division = division
        if division in ['Ise Mikawa Bay', 'Ise-Mikawa Bay']:
            db_division = 'Ise Bay'
            
        if db_division == 'Tokyo Bay':
            land_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS_prefecture_boundaries" / "Tokyobay_boundary.shp"
        elif db_division == 'Ise Bay':
            land_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS_prefecture_boundaries" / "Isebay_boundary.shp"
        else:
            land_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS_prefecture_boundaries" / "Setonaikai_boundary.shp"
            
        if land_boundary_path.exists():
            land_boundary = gpd.read_file(land_boundary_path)
            if land_boundary.crs != "EPSG:4326":
                land_boundary = land_boundary.to_crs("EPSG:4326")
            land_boundary.plot(ax=ax, facecolor=MappingConfig.COLOR_LAND, edgecolor=MappingConfig.COLOR_LAND_EDGE, 
                               linewidth=MappingConfig.LINEWIDTH_LAND, transform=ccrs.PlateCarree(), 
                               zorder=MappingConfig.ZORDER_LAND)
    except Exception as e:
        print(f"Could not load custom boundary for {division}: {e}")
        
    # Map extent
    # map_extent was already calculated above
    
    extent_width = map_extent[1] - map_extent[0]
    zoom_factor = max(4.5 / extent_width, 1.0)
    
    # Scatter plot of decorrelation scale
    sc = ax.scatter(
        plot_data['longitude'], plot_data['latitude'],
        c=plot_data['Decorrelation_Scale_km'],
        cmap='viridis',
        s=60 * zoom_factor, edgecolors='k', linewidths=0.5,
        transform=ccrs.PlateCarree(),
        zorder=MappingConfig.ZORDER_PREDICTED
    )
    
    gl = MappingConfig.apply_gridlines(ax)
    
    ax.set_extent(map_extent, crs=ccrs.PlateCarree())
    plt.title(f'{division}: Decorrelation Scale (km)')
    
    # Add colorbar
    plt.subplots_adjust(bottom=0.15)
    cbar_ax = fig.add_axes([0.25, 0.05, 0.5, 0.03])
    cbar = fig.colorbar(sc, cax=cbar_ax, orientation='horizontal')
    cbar.set_label('Decorrelation Scale (km)')
    
    figures_dir = ProjectPaths.FIGURES_DIR / "step3_decorrelation_scale_analysis" / "10_calculate_bay_decorrelation_scales"
    figures_dir.mkdir(parents=True, exist_ok=True)
    out_img = figures_dir / f"{division.replace(' ', '_').lower()}_decorrelation_scale.png"
    plt.savefig(out_img, bbox_inches='tight', dpi=300)
    plt.close()
    print(f"Saved decorrelation scale plot for {division} to: {out_img}")

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
    
    # Locate yearly_do_df.csv
    yearly_do_file = ProjectPaths.get_subset_dir(season, layer) / "yearly_do_df.csv"
    if not yearly_do_file.exists():
        print(f"Error: Pre-filtered data file {yearly_do_file} does not exist. Please run Step 1 first.")
        return
        
    yearly_do_df = pd.read_csv(yearly_do_file, index_col=0)
    yearly_do_df.index = yearly_do_df.index.astype(str).str.zfill(8)
    
    divisions_param = PARAMS.get('divisions', 'Seto Inland Sea, Tokyo Bay, Ise Bay, Osaka Bay')
    divisions = [d.strip() for d in divisions_param.split(',')]
    
    merged_gdf = load_and_process_data(force_reload=False)
    
    for division in divisions:
        df = compute_decorrelation_for_division(division, yearly_do_df, merged_gdf)
        if not df.empty:
            out_name = division.replace(' ', '_').lower()
            out_path = PROCESSED_DATA_DIR / f"{out_name}_decorrelation_scale.csv"
            df.to_csv(out_path, index=False)
            print(f"Saved {division} decorrelation scales to: {out_path}")
            
            # Plot the decorrelation scale map
            plot_simple_decorrelation_scale(division, df, merged_gdf)
            plot_decorrelation_scale(division, df, merged_gdf)

if __name__ == "__main__":
    main()
