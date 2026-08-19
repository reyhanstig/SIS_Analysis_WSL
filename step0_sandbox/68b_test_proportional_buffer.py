import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.colors as mcolors

project_root = Path('/home/reyha/SIS_Analysis_WSL')
sys.path.append(str(project_root))

from utils.paths import ProjectPaths
from utils.mapping_config import MappingConfig

plt.style.use(str(ProjectPaths.PROJECT_ROOT / 'project_style.mplstyle'))

OUT_DIR = project_root / 'figures' / 'test' / 'new_logic'
OUT_DIR.mkdir(parents=True, exist_ok=True)

merged_df = pd.read_feather(ProjectPaths.MERGED_DATA_FILE)

def get_station_coords(target_region):
    if target_region in ['Tokyo Bay', 'Ise Bay', 'Seto Inland Sea']:
        df = merged_df[merged_df['watermass_name'] == target_region]
    else:
        df = merged_df[merged_df['division'] == target_region]
    stations = df[['zettaicode', 'latitude', 'longitude']].drop_duplicates('zettaicode')
    stations['synthetic_val'] = np.random.uniform(-1, 1, size=len(stations))
    return stations

def apply_base_map(ax, target_region):
    ax.add_feature(cfeature.LAND, facecolor=MappingConfig.COLOR_LAND, edgecolor='gray', zorder=MappingConfig.ZORDER_CARTOPY_LAND)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5, edgecolor='black', zorder=MappingConfig.ZORDER_CARTOPY_COASTLINE)
    try:
        land_boundary_file = MappingConfig.get_boundary_file(target_region) if hasattr(MappingConfig, 'get_boundary_file') else "polbnda_jpn.shp"
        land_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS_prefecture_boundaries" / land_boundary_file
        if land_boundary_path.exists():
            sis_land_boundary = gpd.read_file(land_boundary_path)
            if sis_land_boundary.crs != "EPSG:4326":
                sis_land_boundary = sis_land_boundary.to_crs("EPSG:4326")
            sis_land_boundary.plot(ax=ax, facecolor=MappingConfig.COLOR_LAND, edgecolor='gray', linewidth=0.5, transform=ccrs.PlateCarree(), zorder=MappingConfig.ZORDER_LAND)
    except: pass
    MappingConfig.apply_gridlines(ax)

# ================= NEW LOGIC: PROPORTIONAL 10% BUFFER AND ASPECT RATIO SIZING =================
def new_logic_extent(plot_data, target_region):
    if target_region == 'Seto Inland Sea':
        water_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS water mass polygon" / "sea_area_mask_sis_simplified.shp"
        if water_boundary_path.exists():
            sis_water_boundary = gpd.read_file(water_boundary_path)
            if sis_water_boundary.crs != "EPSG:4326":
                sis_water_boundary = sis_water_boundary.to_crs("EPSG:4326")
            bounds = sis_water_boundary.total_bounds
            return [bounds[0] + 0.1, bounds[2] + 0.1, bounds[1] - 0, bounds[3] + 0.2]

    minx, maxx = plot_data['longitude'].min(), plot_data['longitude'].max()
    miny, maxy = plot_data['latitude'].min(), plot_data['latitude'].max()
    
    x_range = maxx - minx
    y_range = maxy - miny
    
    x_buffer = max(x_range * 0.11, 0.06)
    y_buffer = max(y_range * 0.11, 0.06)
    
    extent = [minx - x_buffer, maxx + x_buffer, miny - y_buffer, maxy + y_buffer]
    return extent

def setup_dynamic_ax(extent):
    aspect_ratio = (extent[3] - extent[2]) / (extent[1] - extent[0])
    fig_width = 8
    fig_height = fig_width * aspect_ratio 
    fig, ax = plt.subplots(figsize=(fig_width, fig_height), subplot_kw={'projection': ccrs.PlateCarree()})
    ax.set_facecolor('lightblue')
    ax.set_extent(extent, crs=ccrs.PlateCarree())
    return fig, ax

# 1. Process 13 (DO Trend)
def plot_trend(target_region):
    plot_data = get_station_coords(target_region)
    extent = new_logic_extent(plot_data, target_region)
    fig, ax = setup_dynamic_ax(extent)
    apply_base_map(ax, target_region)
    
    sc = ax.scatter(plot_data['longitude'], plot_data['latitude'], c=plot_data['synthetic_val'], cmap='RdYlBu', s=50, transform=ccrs.PlateCarree(), zorder=10)
    plt.title(f"DO Trend (New Logic)\n{target_region}")
    plt.colorbar(sc, ax=ax, orientation='vertical')
    plt.savefig(OUT_DIR / f"trend_{target_region.replace(' ', '_').lower()}.png", bbox_inches='tight', dpi=150)
    plt.close()

# 2. Process 12 (Decorrelation)
def plot_decorrelation(target_region):
    plot_data = get_station_coords(target_region)
    extent = new_logic_extent(plot_data, target_region)
    fig, ax = setup_dynamic_ax(extent)
    apply_base_map(ax, target_region)
    
    sc = ax.scatter(plot_data['longitude'], plot_data['latitude'], c=plot_data['synthetic_val'], cmap='viridis', s=100, transform=ccrs.PlateCarree(), zorder=10)
    plt.title(f"Decorrelation (New Logic)\n{target_region}")
    plt.colorbar(sc, ax=ax, orientation='horizontal')
    plt.savefig(OUT_DIR / f"decorrelation_{target_region.replace(' ', '_').lower()}.png", bbox_inches='tight', dpi=150)
    plt.close()

# 3/4. Process 03/13 (PCA)
def plot_pca(target_region, is_global=False):
    plot_data = get_station_coords(target_region)
    extent = new_logic_extent(plot_data, target_region)
    fig, ax = setup_dynamic_ax(extent)
    apply_base_map(ax, target_region)
    
    sc = ax.scatter(plot_data['longitude'], plot_data['latitude'], c=plot_data['synthetic_val'], cmap='coolwarm', s=100, transform=ccrs.PlateCarree(), zorder=10)
    title = f"PCA Global (New Logic)" if is_global else f"PCA Per Bay (New Logic)\n{target_region}"
    plt.title(title)
    plt.colorbar(sc, ax=ax, orientation='horizontal')
    prefix = "pca_global" if is_global else f"pca_{target_region.replace(' ', '_').lower()}"
    plt.savefig(OUT_DIR / f"{prefix}.png", bbox_inches='tight', dpi=150)
    plt.close()

# 5. Process 41 (Spatial Corr)
def plot_spatial_corr(target_region):
    plot_data = get_station_coords(target_region)
    extent = new_logic_extent(plot_data, target_region)
    fig, ax = setup_dynamic_ax(extent)
    apply_base_map(ax, target_region)
    
    sc = ax.scatter(plot_data['longitude'], plot_data['latitude'], c=plot_data['synthetic_val'], cmap='coolwarm', s=100, transform=ccrs.PlateCarree(), zorder=10)
    plt.title(f"Spatial Corr (New Logic)\n{target_region}")
    plt.colorbar(sc, ax=ax, orientation='vertical')
    plt.savefig(OUT_DIR / f"spatial_corr_{target_region.replace(' ', '_').lower()}.png", bbox_inches='tight', dpi=150)
    plt.close()

if __name__ == '__main__':
    for basin in ['Tokyo Bay', 'Ise Bay', 'Seto Inland Sea']:
        print(f"Plotting NEW LOGIC for {basin}...")
        plot_trend(basin)
        plot_decorrelation(basin)
        plot_spatial_corr(basin)
    plot_pca('Seto Inland Sea', is_global=True)
    plot_pca('Tokyo Bay', is_global=False)
    plot_pca('Ise Bay', is_global=False)
    print("Done generating new logic maps.")
