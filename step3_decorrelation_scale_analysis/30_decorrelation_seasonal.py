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
OUTPUT_DIR = Path('/home/reyha/SIS_Analysis_WSL/figures') / STEP_DIR / SCRIPT_NAME
if OUTPUT_DIR.exists():
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
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

import numpy as np
import geopandas as gpd
import cartopy.crs as ccrs
from utils.paths import ProjectPaths
from utils.mapping_config import MappingConfig

def main():
    # Retrieve season and layer from Step 1 parameters
    step1_param_file = ProjectPaths.PROJECT_ROOT / "step1_data_processing_cleaning" / "step1_parameter.csv"
    step1_params = {}
    if step1_param_file.exists():
        df_p = pd.read_csv(step1_param_file)
        for _, row in df_p.iterrows():
            step1_params[row['parameter_name']] = row['value']
    season = step1_params.get('season', 'Summer').capitalize()
    layer = step1_params.get('layer', 'bottom').capitalize()
    
    print(f"Loading results for {season} - {layer}...")
    
    results = []
    
    # Load seasonal scale results
    subset_name = f"{season.lower()}_{layer.lower()}"
    file_path = ProjectPaths.SEASONAL_DATA_DIR / subset_name / 'stations_decorrelation_scale.csv'
    if file_path.exists():
        df = pd.read_csv(file_path)
        df['Season'] = season
        df['Layer'] = layer
        results.append(df)
        
    # Load bay specific results from script 10
    bays_dir = PROCESSED_DATA_DIR.parent / '10_calculate_bay_decorrelation_scales'
    if bays_dir.exists():
        for csv_file in bays_dir.glob("*_decorrelation_scale.csv"):
            df = pd.read_csv(csv_file)
            if not df.empty:
                df['Season'] = season
                df['Layer'] = layer
                results.append(df)
                
    if not results:
        print("No decorrelation results found. Please run scripts 10 and 20 first.")
        return
        
    all_results = pd.concat(results, ignore_index=True)
    all_results['Decorrelation_Scale_km'] = all_results['Decorrelation_Scale_km'].replace(0.0, np.nan)
    
    # Merge geometry info into results
    merged_gdf = gpd.read_feather(ProjectPaths.MERGED_DATA_FILE)
    station_locs = merged_gdf.drop_duplicates('zettaicode').set_index('zettaicode')
    station_locs.index = station_locs.index.astype(str).str.zfill(8)
    
    all_results['longitude'] = all_results['Station_ID'].astype(str).str.zfill(8).map(lambda x: station_locs.loc[x, 'longitude'] if x in station_locs.index else np.nan)
    all_results['latitude'] = all_results['Station_ID'].astype(str).str.zfill(8).map(lambda x: station_locs.loc[x, 'latitude'] if x in station_locs.index else np.nan)
    
    divisions_param = PARAMS.get('divisions', 'Seto Inland Sea, Tokyo Bay, Ise Bay, Osaka Bay')
    divisions = [d.strip() for d in divisions_param.split(',')]
    
    for division in divisions:
        print(f"\nGenerating single plot for {division} ({season} - {layer})...")
        
        # Filter stations for this division
        db_division = division
        if division in ['Ise Mikawa Bay', 'Ise-Mikawa Bay']:
            db_division = 'Ise Bay'
            
        if db_division in merged_gdf['watermass_name'].unique():
            division_stations = merged_gdf[merged_gdf['watermass_name'] == db_division]['zettaicode'].unique()
        elif db_division in merged_gdf['division'].unique():
            division_stations = merged_gdf[merged_gdf['division'] == db_division]['zettaicode'].unique()
        else:
            print(f"Division '{division}' not found in data. Skipping.")
            continue
            
        division_stations_str = [str(st).zfill(8) for st in division_stations]
        
        div_results = all_results[all_results['Station_ID'].astype(str).str.zfill(8).isin(division_stations_str)].copy()
        
        if div_results.empty or div_results['Decorrelation_Scale_km'].isna().all():
            print(f"No valid data found for {division}. Skipping plot.")
            continue
            
        # Filter for spatial data
        map_data = div_results.dropna(subset=['latitude', 'longitude', 'Decorrelation_Scale_km']).copy()
        if map_data.empty:
            print(f"No spatial data for mapping {division}. Skipping.")
            continue
            
        map_gdf = gpd.GeoDataFrame(map_data, geometry=gpd.points_from_xy(map_data.longitude, map_data.latitude), crs="EPSG:4326")
        
        minx, miny, maxx, maxy = map_gdf.total_bounds
        buffer = 0.2
        extent = [minx - buffer, maxx + buffer, miny - buffer, maxy + buffer]
        
        fig, ax = plt.subplots(figsize=(10, 8), subplot_kw={'projection': ccrs.PlateCarree()})
        ax.set_facecolor(MappingConfig.COLOR_OCEAN)
        
        # Load land boundary
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
            
        gl = MappingConfig.apply_gridlines(ax)
        
        sc = ax.scatter(
            map_gdf['longitude'], map_gdf['latitude'],
            c=map_gdf['Decorrelation_Scale_km'],
            cmap='viridis',
            s=80, alpha=0.9,
            edgecolors='black', linewidths=0.5,
            transform=ccrs.PlateCarree(),
            zorder=MappingConfig.ZORDER_PREDICTED
        )
        
        ax.set_extent(extent, crs=ccrs.PlateCarree())
        ax.set_title(f"{division}: {season} - {layer} DO Decorrelation Scale (km)", fontsize=12, fontweight='bold')
        
        cbar = fig.colorbar(sc, ax=ax, orientation='horizontal', pad=0.08, shrink=0.7)
        cbar.set_label('Decorrelation Scale (km)', fontsize=10, fontweight='bold')
        
        out_img = OUTPUT_DIR / f"{division.replace(' ', '_').lower()}_decorrelation_spatial_map.png"
        plt.savefig(out_img, bbox_inches='tight', dpi=300)
        plt.close()
        print(f"Saved single spatial map for {division} to: {out_img}")

if __name__ == '__main__':
    main()
