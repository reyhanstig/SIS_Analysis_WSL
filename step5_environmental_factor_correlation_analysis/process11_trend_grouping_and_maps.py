# -*- coding: utf-8 -*-
import argparse
import sys
from pathlib import Path
import os
import pandas as pd
import numpy as np
import logging
import yaml
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import geopandas as gpd
from matplotlib.lines import Line2D

# --- BOILERPLATE INJECTED BY AGENT ---
CURRENT_SCRIPT = Path(__file__).resolve()
sys.path.insert(0, str(CURRENT_SCRIPT.parent.parent))
STEP_DIR = CURRENT_SCRIPT.parent.name
SCRIPT_NAME = CURRENT_SCRIPT.stem
import shutil
OUTPUT_DIR = Path('/home/reyha/SIS_Analysis_WSL/figures') / STEP_DIR / SCRIPT_NAME
# Loop orchestration handles rm_tree for OUTPUT_DIR
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR = Path('/home/reyha/SIS_Analysis_WSL/data/processed') / STEP_DIR / SCRIPT_NAME
# Loop orchestration handles rm_tree for PROCESSED_DATA_DIR
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

project_root = CURRENT_SCRIPT.parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))
if str(project_root / 'scripts') not in sys.path:
    sys.path.append(str(project_root / 'scripts'))

from utils.paths import ProjectPaths
from utils.mapping_config import MappingConfig
from utils.data_loader import load_and_process_data

# Apply the global project style
plt.style.use(str(ProjectPaths.PROJECT_ROOT / 'project_style.mplstyle'))

# Load global parameters
with open(ProjectPaths.PROJECT_ROOT / 'params.yaml', 'r') as f:
    project_params = yaml.safe_load(f)
REGION_COLUMN = project_params['mapping']['region_column']
LOW_DO_THRESHOLD = 5.0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target_region', required=True)
    parser.add_argument('--season', default='Summer')
    parser.add_argument('--layer', default='bottom')
    args = parser.parse_args()
    
    target_region = args.target_region
    season = args.season
    layer = args.layer
    layer_map = {'surface': 1, 'bottom': 2}
    layer_idx = layer_map.get(layer.lower(), 2)
    rep_months = project_params['seasonal_subsets']['representative_months'].get(season, [7, 8, 9])
    
    logging.info(f"Running process11 for {target_region}")
    
    merged_gdf = load_and_process_data(force_reload=False)
    merged_gdf['zettaicode'] = merged_gdf['zettaicode'].astype(str).str.zfill(8)

    df = merged_gdf[merged_gdf[REGION_COLUMN] == target_region].copy()
    season_layer = df[
        (df['surveymont'].isin(rep_months) if isinstance(rep_months, list) else df['surveymont'] == rep_months) &
        (df['saisuipoin'] == layer_idx)
    ].copy()
    season_layer['do_'] = pd.to_numeric(season_layer['do_'], errors='coerce')
    season_layer = season_layer.dropna(subset=['do_'])

    pivot_df = season_layer.pivot_table(index='zettaicode', columns='year', values='do_', aggfunc='mean')
    pivot_df.index = pivot_df.index.astype(str).str.zfill(8)

    years = pivot_df.columns.astype(int)
    hist_years = [y for y in years if 1981 <= y <= 2013]
    recent_years = [y for y in years if 2014 <= y <= 2023]

    p_hist = (pivot_df[hist_years] < LOW_DO_THRESHOLD).sum(axis=1) / 33
    p_recent = (pivot_df[recent_years] < LOW_DO_THRESHOLD).sum(axis=1) / 10
    delta = p_recent - p_hist

    coords = season_layer.groupby('zettaicode')[['latitude', 'longitude']].first()

    subset_dir = ProjectPaths.get_subset_dir(season, layer)
    decorr_file = subset_dir / "stations_decorrelation_scale.csv"
    if decorr_file.exists():
        df_decorr = pd.read_csv(decorr_file, dtype={'Station_ID': str})
        df_decorr['Station_ID'] = df_decorr['Station_ID'].str.zfill(8)
    else:
        logging.warning(f"{decorr_file} not found.")
        df_decorr = pd.DataFrame(columns=['Station_ID', 'Decorrelation_Scale_km'])

    map_df = pd.DataFrame({
        'delta': delta,
        'p_recent': p_recent,
        'lat': coords['latitude'],
        'lon': coords['longitude']
    }).dropna().reset_index().rename(columns={'zettaicode': 'Station_ID'})

    stats_df = map_df.merge(
        df_decorr[['Station_ID', 'Decorrelation_Scale_km']], 
        on='Station_ID', 
        how='inner'
    )

    group1_mask = (stats_df['Decorrelation_Scale_km'] < 20) & (stats_df['delta'] > 0)
    group2_mask = (stats_df['Decorrelation_Scale_km'] > 10) & (stats_df['delta'] < -0.2)

    stats_df['Group'] = 'Other'
    stats_df.loc[group1_mask, 'Group'] = 'Group 1 (Local & Worsening)'
    stats_df.loc[group2_mask, 'Group'] = 'Group 2 (Regional & Improving)'

    selected_stations = stats_df[stats_df['Group'] != 'Other'].copy()
    
    # Save the groups to PROCESSED_DATA_DIR for downstream scripts
    region_slug = target_region.replace(' ', '_')
    out_csv = PROCESSED_DATA_DIR / f'stations_trend_groups_{region_slug}_{season}_{layer}.csv'
    selected_stations.to_csv(out_csv, index=False)
    logging.info(f"Saved grouped stations to {out_csv.name}")

    # Plotting
    water_boundary_files = {
        'Seto Inland Sea': 'sea_area_mask_sis_simplified.shp',
        'Tokyo Bay': 'sea_area_mask_Tokyo.shp',
        'Ise Bay': 'sea_area_mask_Ise.shp'
    }
    water_boundary_file = water_boundary_files.get(target_region, 'sea_area_mask_sis_simplified.shp')
    water_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS water mass polygon" / water_boundary_file
    
    if water_boundary_path.exists():
        sis_water_boundary = gpd.read_file(water_boundary_path)
    if sis_water_boundary.crs != "EPSG:4326":
        sis_water_boundary = sis_water_boundary.to_crs("EPSG:4326")
    bounds = sis_water_boundary.total_bounds
    
    x_range = bounds[2] - bounds[0]
    y_range = bounds[3] - bounds[1]
    x_buffer = x_range * 0.05
    y_buffer = y_range * 0.05
    extent = [bounds[0] - x_buffer, bounds[2] + x_buffer, bounds[1] - y_buffer, bounds[3] + y_buffer]
    aspect_ratio = (extent[3] - extent[2]) / (extent[1] - extent[0])
    
    if aspect_ratio > 1:
        fig_height = 10
        fig_width = fig_height / aspect_ratio
    else:
        fig_width = 10
        fig_height = fig_width * aspect_ratio
    single_fig_height = fig_height + 1.4
    
    land_boundary_file = "polbnda_jpn.shp" 
    if hasattr(MappingConfig, 'get_boundary_file'):
        land_boundary_file = MappingConfig.get_boundary_file(target_region)
    land_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS_prefecture_boundaries" / land_boundary_file
    
    if land_boundary_path.exists():
        sis_land_boundary = gpd.read_file(land_boundary_path)
        if sis_land_boundary.crs != "EPSG:4326":
            sis_land_boundary = sis_land_boundary.to_crs("EPSG:4326")
    else:
        sis_land_boundary = None

    # Figure 1: Continuous Delta & Size
    fig1 = plt.figure(figsize=(fig_width, single_fig_height))
    ax1 = plt.axes(projection=ccrs.PlateCarree())
    ax1.set_facecolor(MappingConfig.COLOR_OCEAN if hasattr(MappingConfig, 'COLOR_OCEAN') else 'lightblue')
    ax1.add_feature(cfeature.LAND, facecolor='#f5f5f5', edgecolor='dimgray', zorder=0)
    ax1.add_feature(cfeature.COASTLINE, linewidth=0.5, color='black', zorder=2)
    if sis_land_boundary is not None:
        sis_land_boundary.plot(ax=ax1, facecolor='#f5f5f5', edgecolor='dimgray', linewidth=0.5, transform=ccrs.PlateCarree(), zorder=1)

    gl1 = ax1.gridlines(draw_labels=True, linestyle='--', color='gray', alpha=0.3, zorder=2)
    gl1.top_labels = False
    gl1.right_labels = False
    ax1.set_extent(extent, crs=ccrs.PlateCarree())

    vmax = max(abs(selected_stations['delta'].min()), abs(selected_stations['delta'].max()), 0.1)
    sc1 = ax1.scatter(
        selected_stations['lon'], selected_stations['lat'],
        c=selected_stations['delta'],
        s=selected_stations['p_recent'] * 1500 + 20, 
        cmap='RdBu_r', vmin=-vmax, vmax=vmax,
        edgecolors='black', linewidths=0.5, alpha=0.9, transform=ccrs.PlateCarree(), zorder=3
    )
    cbar1 = plt.colorbar(sc1, ax=ax1, orientation='horizontal', pad=0.08, shrink=0.8)
    cbar1.set_label('Proportional Delta (Recent - Historical)', fontsize=14)

    sizes = [0.2, 0.6, 1.2]
    labels = ['10% freq', '50% freq', '100% freq']
    legend_elements = [Line2D([0], [0], marker='o', color='w', label=l,
                              markerfacecolor='gray', markersize=np.sqrt(s * 1000 + 20),
                              markeredgecolor='k', alpha=0.6) for s, l in zip(sizes, labels)]
    ax1.legend(handles=legend_elements, loc='lower right', title='Recent Severity', fontsize=12, title_fontsize=12)
    ax1.set_title(f'Target Groups: Trend and Severity\n{target_region}', fontsize=16, fontweight='bold')

    map_output1 = OUTPUT_DIR / f'lowDO_trend_severity_{region_slug}_{season}_{layer}.png'
    plt.savefig(map_output1, dpi=300, bbox_inches='tight')
    plt.close()

    # Figure 2: Discrete Groups with Labels
    fig2 = plt.figure(figsize=(fig_width, single_fig_height))
    ax2 = plt.axes(projection=ccrs.PlateCarree())
    ax2.set_facecolor(MappingConfig.COLOR_OCEAN if hasattr(MappingConfig, 'COLOR_OCEAN') else 'lightblue')
    ax2.add_feature(cfeature.LAND, facecolor='#f5f5f5', edgecolor='dimgray', zorder=0)
    ax2.add_feature(cfeature.COASTLINE, linewidth=0.4, color='black', zorder=2)
    if sis_land_boundary is not None:
        sis_land_boundary.plot(ax=ax2, facecolor='#f5f5f5', edgecolor='dimgray', linewidth=0.5, transform=ccrs.PlateCarree(), zorder=1)

    gl2 = ax2.gridlines(draw_labels=True, linestyle='--', color='gray', alpha=0.3, zorder=2)
    gl2.top_labels = False
    gl2.right_labels = False
    ax2.set_extent(extent, crs=ccrs.PlateCarree())

    g1 = selected_stations[selected_stations['Group'] == 'Group 1 (Local & Worsening)']
    g2 = selected_stations[selected_stations['Group'] == 'Group 2 (Regional & Improving)']

    ax2.scatter(g1['lon'], g1['lat'], c='indianred', s=100, edgecolors='black', linewidths=0.5, alpha=0.9, transform=ccrs.PlateCarree(), zorder=3, label='Group 1 (Worsening)')
    ax2.scatter(g2['lon'], g2['lat'], c='steelblue', s=100, edgecolors='black', linewidths=0.5, alpha=0.9, transform=ccrs.PlateCarree(), zorder=3, label='Group 2 (Improving)')

    for idx, row in selected_stations.iterrows():
        ax2.text(row['lon'], row['lat'], row['Station_ID'], 
                 transform=ccrs.PlateCarree(), fontsize=8, fontweight='bold',
                 ha='center', va='bottom', zorder=4)

    ax2.legend(loc='lower right', fontsize=12)
    ax2.set_title(f'Target Groups: Discrete Classification\n{target_region}', fontsize=16, fontweight='bold')

    map_output2 = OUTPUT_DIR / f'lowDO_discrete_groups_{region_slug}_{season}_{layer}.png'
    plt.savefig(map_output2, dpi=300, bbox_inches='tight')
    plt.close()

if __name__ == '__main__':
    main()
