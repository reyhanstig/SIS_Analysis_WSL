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
import shutil
OUTPUT_DIR = Path('/home/reyha/SIS_Analysis_WSL/figures') / STEP_DIR / SCRIPT_NAME
if not OUTPUT_DIR.exists():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR = Path('/home/reyha/SIS_Analysis_WSL/data/processed') / STEP_DIR / SCRIPT_NAME
if not PROCESSED_DATA_DIR.exists():
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

"""
Hypoxia Frequency Map — Per Bay
Produces Hypoxia Frequency Map (Hypoxic 0-2 mg/L) for a specified division.
Uses a uniform spatial extent based on Iyo Nada (UNIFORM_DX=1.264, UNIFORM_DY=0.709).
"""

import argparse
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, box
from matplotlib.patches import Polygon as MplPolygon, PathPatch
from matplotlib.collections import PatchCollection
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import warnings

warnings.filterwarnings('ignore')

from utils.paths import ProjectPaths
from utils.mapping_config import MappingConfig
from utils.data_loader import load_and_process_data

# Compact subplot style overrides
SUBPLOT_TITLE_SIZE = 20
SUBPLOT_LABEL_SIZE = 18
SUBPLOT_TICK_SIZE = 16
SUBPLOT_CBAR_LABEL_SIZE = 18
SUBPLOT_CBAR_TICK_SIZE = 16
SUBPLOT_LAND_LW = 0.3
OUTPUT_DPI = 250


MappingConfig.apply_global_plot_styles()
plt.rcParams.update({
    'font.size': 16,
    'axes.titlesize': SUBPLOT_TITLE_SIZE,
    'axes.labelsize': SUBPLOT_LABEL_SIZE,
    'xtick.labelsize': SUBPLOT_TICK_SIZE,
    'ytick.labelsize': SUBPLOT_TICK_SIZE,
    'legend.fontsize': 12,
})

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--division', required=True, help="Target division (e.g. 'Tokyo Bay')")
    return parser.parse_args()

def build_land_patches(gdf, facecolor, edgecolor, linewidth):
    patches = []
    for geom in gdf.geometry:
        if geom.geom_type == 'Polygon':
            patches.append(MplPolygon(np.array(geom.exterior.coords), closed=True))
        elif geom.geom_type == 'MultiPolygon':
            for poly in geom.geoms:
                patches.append(MplPolygon(np.array(poly.exterior.coords), closed=True))
    return patches, facecolor, edgecolor, linewidth

def add_land_to_ax(ax, patches_data):
    patches, fc, ec, lw = patches_data
    ax.add_feature(cfeature.LAND, facecolor=MappingConfig.COLOR_LAND,
                   zorder=MappingConfig.ZORDER_CARTOPY_LAND)
    ax.add_feature(cfeature.COASTLINE, linewidth=SUBPLOT_LAND_LW, edgecolor='black',
                   zorder=MappingConfig.ZORDER_CARTOPY_COASTLINE)
    pc = PatchCollection(
        [MplPolygon(p.get_xy(), closed=True) for p in patches],
        facecolor=fc, edgecolor=ec, linewidth=lw,
        transform=ccrs.PlateCarree(),
        zorder=MappingConfig.ZORDER_LAND
    )
    ax.add_collection(pc)

def _add_gridlines(ax):
    return MappingConfig.apply_gridlines(ax)

def add_global_scalebar(ax_scale, dx, dy):
    ax_scale.set_visible(True)
    ax_scale.axis('off')
    ax_scale.set_extent([0, dx, 0, dy], crs=ccrs.PlateCarree())
    
    km_per_deg_lon = 111.32 * np.cos(np.radians(34.0))
    deg_20km = 20.0 / km_per_deg_lon
    
    lon_start = dx * 0.4
    lon_end = lon_start + deg_20km
    lat_pos = dy * 0.1
    
    ax_scale.plot([lon_start, lon_end], [lat_pos, lat_pos], color='black', lw=3, transform=ccrs.PlateCarree())
    ax_scale.text((lon_start + lon_end)/2, lat_pos + dy * 0.05, '20 km', ha='center', va='bottom', 
                  fontsize=SUBPLOT_LABEL_SIZE, fontweight='bold', transform=ccrs.PlateCarree())

def load_spatial_data(division):
    if division == 'Tokyo Bay':
        land_boundary = gpd.read_file(ProjectPaths.BOUNDARIES_DIR / 'SIS_prefecture_boundaries' / 'Tokyobay_boundary.shp')
        water_mask = gpd.read_file(ProjectPaths.BOUNDARIES_DIR / 'SIS water mass polygon' / 'sea_area_mask_Tokyo.shp')
    elif division == 'Ise Bay':
        land_boundary = gpd.read_file(ProjectPaths.BOUNDARIES_DIR / 'SIS_prefecture_boundaries' / 'Isebay_boundary.shp')
        water_mask = gpd.read_file(ProjectPaths.BOUNDARIES_DIR / 'SIS water mass polygon' / 'sea_area_mask_Ise.shp')
    else:
        land_boundary = gpd.read_file(ProjectPaths.BOUNDARIES_DIR / 'SIS_prefecture_boundaries' / 'Setonaikai_boundary_2.shp')
        water_mask = gpd.read_file(ProjectPaths.BOUNDARIES_DIR / 'SIS water mass polygon' / 'sea_area_mask_sis_simplified.shp')
    
    return land_boundary.to_crs("EPSG:4326"), water_mask.to_crs("EPSG:4326")

def main():
    args = parse_args()
    division = args.division
    div_clean = division.replace(' ', '_').lower()
    TARGET_SEASON = 'Summer'
    
    logging.info(f"Loading data for division: {division}")
    merged_gdf = load_and_process_data(force_reload=False)
    
    df = merged_gdf[(merged_gdf['season'] == TARGET_SEASON) & (merged_gdf['saisuipoin'] == 2)].copy()
    df['do_'] = pd.to_numeric(df['do_'], errors='coerce')
    df = df.dropna(subset=['do_'])
    
    if division in ['Tokyo Bay', 'Ise Bay', 'Seto Inland Sea']:
        df = df[df['watermass_name'] == division]
    else:
        df = df[df['division'] == division]

    if df.empty:
        logging.warning(f"No data available for division: {division}")
        return

    land_boundary, _ = load_spatial_data(division)
    
    minx, maxx = df['longitude'].min(), df['longitude'].max()
    miny, maxy = df['latitude'].min(), df['latitude'].max()
    buffer = 0.2
    
    uniform_extent = [minx - buffer, maxx + buffer, miny - buffer, maxy + buffer]
    dx = uniform_extent[1] - uniform_extent[0]
    dy = uniform_extent[3] - uniform_extent[2]
    land_patches_data = build_land_patches(land_boundary, MappingConfig.COLOR_LAND, MappingConfig.COLOR_LAND_EDGE, SUBPLOT_LAND_LW)

    # Figure 2: Hypoxia Frequency (0-2 mg/L)
    logging.info("Generating Figure 2: Hypoxia Frequency Map")
    def calc_freq(group):
        total_years = group['year'].nunique()
        cond_years = group[(group['do_'] >= 0.0) & (group['do_'] <= 2.0)]['year'].nunique()
        return (cond_years / total_years) * 100

    freq_df = df.groupby(['zettaicode', 'longitude', 'latitude']).apply(calc_freq).reset_index(name='frequency')
    
    fig, ax = plt.subplots(1, 1, figsize=(8, 6), subplot_kw={'projection': ccrs.PlateCarree()})
    ax.set_facecolor(MappingConfig.COLOR_OCEAN)
    add_land_to_ax(ax, land_patches_data)
    ax.set_extent(uniform_extent, crs=ccrs.PlateCarree())
    
    marker_sizes = freq_df['frequency'] * 2.4 + 24
    sc = ax.scatter(freq_df['longitude'], freq_df['latitude'], c=freq_df['frequency'], cmap='Reds', vmin=0, vmax=100,
                    s=marker_sizes, edgecolor='k', linewidth=0.3, transform=ccrs.PlateCarree(), zorder=MappingConfig.ZORDER_OBSERVATIONS)
    
    ax.set_title(f"Hypoxia Frequency (0-2 mg/L)\n{division}", fontsize=SUBPLOT_TITLE_SIZE, fontweight='bold')
    _add_gridlines(ax)
    
    cbar = fig.colorbar(sc, ax=ax, orientation='vertical', fraction=0.046, pad=0.04)
    cbar.set_label('Frequency (%)', fontsize=SUBPLOT_CBAR_LABEL_SIZE)
    cbar.ax.tick_params(labelsize=SUBPLOT_CBAR_TICK_SIZE)
    add_global_scalebar(fig.add_axes([0.65, 0.15, 0.2, 0.1], projection=ccrs.PlateCarree()), dx, dy)
    
    out_path = OUTPUT_DIR / f"hypoxia_freq_0_2_{div_clean}_{TARGET_SEASON.lower()}.png"
    plt.savefig(out_path, dpi=OUTPUT_DPI, bbox_inches='tight')
    plt.close()

    logging.info(f"Finished processing {division}.")

if __name__ == '__main__':
    main()
