#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# --- BOILERPLATE INJECTED BY AGENT ---
import os
import pandas as pd
import logging
import matplotlib.pyplot as plt

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
import geopandas as gpd

warnings.filterwarnings('ignore')

from utils.data_loader import load_and_process_data
from utils.paths import ProjectPaths
from utils.mapping_config import MappingConfig

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
        
    fig, ax = plt.subplots(figsize=(10, 8), subplot_kw={'projection': ccrs.PlateCarree()})
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
    min_lon, max_lon = plot_data['longitude'].min(), plot_data['longitude'].max()
    min_lat, max_lat = plot_data['latitude'].min(), plot_data['latitude'].max()
    buffer = 0.2
    map_extent = [min_lon - buffer, max_lon + buffer, min_lat - buffer, max_lat + buffer]
    
    # Scatter plot of decorrelation scale
    sc = ax.scatter(
        plot_data['longitude'], plot_data['latitude'],
        c=plot_data['Decorrelation_Scale_km'],
        cmap='viridis',
        s=60, edgecolors='k', linewidths=0.5,
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
    
    figures_dir = ProjectPaths.FIGURES_DIR / STEP_DIR / SCRIPT_NAME / division.replace(' ', '_').lower()
    if figures_dir.exists():
        shutil.rmtree(figures_dir, ignore_errors=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    out_img = figures_dir / f"{division.replace(' ', '_').lower()}_decorrelation_scale.png"
    plt.savefig(out_img, bbox_inches='tight', dpi=300)
    plt.close()
    print(f"Saved complete decorrelation scale plot for {division} to: {out_img}")

def main():
    ProjectPaths.ensure_directories()
    merged_gdf = load_and_process_data(force_reload=False)
    
    # Load data from script 40
    parser = argparse.ArgumentParser()
    parser.add_argument('--division', type=str, required=True)
    args, unknown = parser.parse_known_args()
    
    division = args.division
    div_folder = division.replace(' ', '_').lower()
    
    data_dir_40 = ProjectPaths.PROCESSED_DATA_DIR / STEP_DIR / "40_calculate_decorrelation_scale_per_bay" / div_folder
    csv_file = data_dir_40 / f"{div_folder}_decorrelation_scale.csv"
    
    if not csv_file.exists():
        print(f"Error: Required data file not found: {csv_file}")
        return
        
    df = pd.read_csv(csv_file)
    if 'Station_ID' in df.columns:
        df['Station_ID'] = df['Station_ID'].astype(str).str.zfill(8)
        
    print(f"Plotting complete map for {division}...")
    plot_decorrelation_scale(division, df, merged_gdf)

if __name__ == "__main__":
    main()
