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

def plot_eof_map(eof_values, station_coords, pc_name, variance_pct, division):
    plt.style.use(str(ProjectPaths.PROJECT_ROOT / 'project_style.mplstyle'))

    plot_data = station_coords.copy()
    plot_data['EOF'] = eof_values
    
    min_lon, max_lon = plot_data['longitude'].min(), plot_data['longitude'].max()
    min_lat, max_lat = plot_data['latitude'].min(), plot_data['latitude'].max()
    buffer = 0.2
    map_extent = [min_lon - buffer, max_lon + buffer, min_lat - buffer, max_lat + buffer]
    
    fig, ax = plt.subplots(figsize=(10, 8), subplot_kw={'projection': ccrs.PlateCarree()})
    ax.set_facecolor(MappingConfig.COLOR_OCEAN)
    
    ax.add_feature(cfeature.LAND, facecolor=MappingConfig.COLOR_LAND, zorder=MappingConfig.ZORDER_CARTOPY_LAND)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5, edgecolor='black', zorder=MappingConfig.ZORDER_CARTOPY_COASTLINE)
    
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
        pass
    
    vmax = max(abs(plot_data['EOF'].min()), abs(plot_data['EOF'].max()))
    
    sc = ax.scatter(
        plot_data['longitude'], plot_data['latitude'],
        c=plot_data['EOF'],
        cmap='coolwarm',
        vmin=-vmax, vmax=vmax,
        s=np.maximum(abs(plot_data['EOF']) * 800, 20), edgecolors='k', linewidths=0.5,
        transform=ccrs.PlateCarree(),
        zorder=MappingConfig.ZORDER_PREDICTED
    )
    
    gl = MappingConfig.apply_gridlines(ax)
    
    ax.set_extent(map_extent, crs=ccrs.PlateCarree())
    plt.title(f'{division}: {pc_name} Spatial Pattern ({variance_pct:.1f}%)')
    
    plt.subplots_adjust(bottom=0.15)
    cbar_ax = fig.add_axes([0.25, 0.05, 0.5, 0.03])
    cbar = fig.colorbar(sc, cax=cbar_ax, orientation='horizontal')
    cbar.set_label('EOF Weight')
    
    out_path = OUTPUT_DIR / f"{division.replace(' ', '_').lower()}_eof_map_{pc_name.lower()}_raw.png"
    plt.savefig(out_path, bbox_inches='tight', dpi=300)
    plt.close()

def main():
    ProjectPaths.ensure_directories()
    division = args.division
    out_name = division.replace(' ', '_').lower()
    
    data_dir = ProjectPaths.PROCESSED_DATA_DIR / STEP_DIR / "21_calculate_pca_explained_variance_per_bay_raw" / out_name
    eof_file = data_dir / f"{out_name}_eof_patterns.csv"
    var_file = data_dir / f"{out_name}_pca_variance.csv"
    
    if not eof_file.exists() or not var_file.exists():
        print("Error: EOF patterns or variance file not found.")
        return
        
    eof_df = pd.read_csv(eof_file)
    eof_df['Station_ID'] = eof_df['Station_ID'].astype(str).str.zfill(8)
    var_df = pd.read_csv(var_file)
    
    pc1_var = var_df[var_df['PC'] == 'PC1']['Variance_Pct'].values[0]
    pc2_var = var_df[var_df['PC'] == 'PC2']['Variance_Pct'].values[0]
    
    merged_gdf = load_and_process_data(force_reload=False)
    station_coords = merged_gdf[['zettaicode', 'latitude', 'longitude']].drop_duplicates('zettaicode')
    station_coords['zettaicode_str'] = station_coords['zettaicode'].astype(str).str.zfill(8)
    
    station_coords = station_coords[station_coords['zettaicode_str'].isin(eof_df['Station_ID'])]
    station_coords = station_coords.set_index('zettaicode_str')
    
    eof_df = eof_df.set_index('Station_ID')
    station_coords = station_coords.loc[eof_df.index]
    
    plot_eof_map(eof_df['EOF1'].values, station_coords, 'PC1', pc1_var, division)
    plot_eof_map(eof_df['EOF2'].values, station_coords, 'PC2', pc2_var, division)

if __name__ == "__main__":
    main()
