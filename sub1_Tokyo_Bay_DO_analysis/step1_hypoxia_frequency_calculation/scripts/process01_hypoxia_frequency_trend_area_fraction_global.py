# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Auto-generated from: notebooks/55_hypoxia_frequency_trend_v2.ipynb

# # 55. Hypoxia Frequency Trend v2 (Normalized by Basin Area)
#
# This notebook normalizes the hypoxic area by computing the **Hypoxic Area Fraction** (Hypoxic Area divided by Total Basin Area) for each basin over time.
# Instead of generating spatial horizontal maps, this notebook focuses on statistical comparisons and temporal trend analysis using tables, line plots, and box plots. It evaluates hypoxia using a **2.0 mg/L** threshold and presents both the raw yearly trends and smoothed temporal trends (3-year rolling average).
#
# Sections:
# 1. Data Loading & Regional Grid Setup
# 2. Hypoxic Area Fraction Calculation (Iterative)
# 3. Visualization & Comparison (Raw Results)
# 4. Temporal Smoothing & Trend Analysis

import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
from shapely.prepared import prep
from scipy import ndimage
from scipy.spatial import cKDTree
from pyproj import Transformer
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.collections import PatchCollection
import sys
from pathlib import Path
import warnings
from scipy import stats


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
warnings.filterwarnings('ignore')

# Project Path Setup
project_root = Path.cwd().parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.paths import ProjectPaths
from utils.mapping_config import MappingConfig
from utils.data_loader import load_and_process_data

# Setup global mapping config
MappingConfig.apply_global_plot_styles()



# Constants for diffusion interpolation
GRID_RES = 1000  # finer grid res to account for sub-basins
MAX_ITERS = 500
TOL = 1e-3
OMEGA = 1.8

# Load the pre-processed data
merged_gdf = load_and_process_data(force_reload=False)

TARGET_SEASON = 'Summer'
SAISUIPOIN_ID = 2

summer_bottom_df = merged_gdf[
    (merged_gdf['season'] == TARGET_SEASON) & 
    (merged_gdf['saisuipoin'] == SAISUIPOIN_ID)
].copy()

summer_bottom_df['do_'] = pd.to_numeric(summer_bottom_df['do_'], errors='coerce')
summer_bottom_df = summer_bottom_df.dropna(subset=['do_'])

print(f"Total observations: {len(summer_bottom_df)}")

# Define regions
sis_df = summer_bottom_df[summer_bottom_df['watermass_name'] == 'Seto Inland Sea']
sis_divisions = sis_df['division'].dropna().unique().tolist()

regions_info = []

regions_info.append({
    'name': 'Tokyo Bay',
    'land_boundary': ProjectPaths.BOUNDARIES_DIR / 'SIS_prefecture_boundaries' / 'Tokyobay_boundary.shp',
    'water_mask': ProjectPaths.BOUNDARIES_DIR / 'SIS water mass polygon' / 'sea_area_mask_Tokyo.shp',
    'data': summer_bottom_df[summer_bottom_df['watermass_name'] == 'Tokyo Bay'].copy()
})

regions_info.append({
    'name': 'Ise Bay',
    'land_boundary': ProjectPaths.BOUNDARIES_DIR / 'SIS_prefecture_boundaries' / 'Isebay_boundary.shp',
    'water_mask': ProjectPaths.BOUNDARIES_DIR / 'SIS water mass polygon' / 'sea_area_mask_Ise.shp',
    'data': summer_bottom_df[summer_bottom_df['watermass_name'] == 'Ise Bay'].copy()
})

for div in sis_divisions:
    regions_info.append({
        'name': div,
        'land_boundary': ProjectPaths.BOUNDARIES_DIR / 'SIS_prefecture_boundaries' / 'Setonaikai_boundary_2.shp',
        'water_mask': ProjectPaths.BOUNDARIES_DIR / 'SIS water mass polygon' / 'sea_area_mask_sis_simplified.shp',
        'data': sis_df[sis_df['division'] == div].copy()
    })

print(f"Total regions defined: {len(regions_info)}")
for r in regions_info:
    print(f"{r['name']}: {len(r['data'])} observations")



# Helper to build land patches
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
    ax.add_feature(cfeature.LAND, facecolor=MappingConfig.COLOR_LAND, zorder=MappingConfig.ZORDER_CARTOPY_LAND)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5, edgecolor='black', zorder=MappingConfig.ZORDER_CARTOPY_COASTLINE)
    pc = PatchCollection(
        [MplPolygon(p.get_xy(), closed=True) for p in patches],
        facecolor=fc, edgecolor=ec, linewidth=lw,
        transform=ccrs.PlateCarree(),
        zorder=MappingConfig.ZORDER_LAND
    )
    ax.add_collection(pc)

def setup_diffusion_grid(water_boundary_path, data_bounds, grid_res=GRID_RES):
    """Sets up the grid, KDTree, and masks for diffusion interpolation."""
    water_boundary = gpd.read_file(water_boundary_path)
    if water_boundary.crs != "EPSG:4326":
        water_boundary = water_boundary.to_crs("EPSG:4326")
        
    utm_crs = 'EPSG:32653'
    water_utm = water_boundary.to_crs(utm_crs)
    bounds_utm = water_utm.total_bounds
    
    data_bounds_gdf = gpd.GeoDataFrame({'geometry': [Point(data_bounds[0], data_bounds[1]), Point(data_bounds[2], data_bounds[3])]}, crs="EPSG:4326")
    data_bounds_utm = data_bounds_gdf.to_crs(utm_crs).total_bounds
    
    # Intersect bounds to keep grid tight around the specific region/sub-basin
    minx = max(bounds_utm[0], data_bounds_utm[0] - 5000)
    miny = max(bounds_utm[1], data_bounds_utm[1] - 5000)
    maxx = min(bounds_utm[2], data_bounds_utm[2] + 5000)
    maxy = min(bounds_utm[3], data_bounds_utm[3] + 5000)
    
    # Handle edge case where no intersection
    if minx >= maxx or miny >= maxy:
        return None
        
    grid_x_1d = np.arange(minx, maxx, grid_res)
    grid_y_1d = np.arange(miny, maxy, grid_res)
    grid_x, grid_y = np.meshgrid(grid_x_1d, grid_y_1d)
    
    water_polygon = water_utm.geometry.union_all()
    prepared_poly = prep(water_polygon)
    
    flat_x = grid_x.flatten()
    flat_y = grid_y.flatten()
    grid_points = [Point(x, y) for x, y in zip(flat_x, flat_y)]
    valid_points_mask = np.array([prepared_poly.contains(pt) for pt in grid_points])
    water_mask = valid_points_mask.reshape(grid_x.shape)
    
    transformer = Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)
    lon_flat, lat_flat = transformer.transform(flat_x, flat_y)
    lon_wgs = lon_flat.reshape(grid_x.shape)
    lat_wgs = lat_flat.reshape(grid_y.shape)
    
    kernel = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]])
    water_float = water_mask.astype(np.float64)
    W = ndimage.convolve(water_float, kernel, mode='constant', cval=0.0)
    valid_W_mask = W > 0
    
    i_indices, j_indices = np.indices(grid_x.shape)
    red_mask = (i_indices + j_indices) % 2 == 0
    black_mask = ~red_mask
    
    water_iy, water_ix = np.where(water_mask)
    if len(water_iy) == 0:
        return None
    water_coords = np.column_stack([grid_x[water_iy, water_ix], grid_y[water_iy, water_ix]])
    water_tree = cKDTree(water_coords)
    
    return {
        'grid_x': grid_x, 'grid_y': grid_y,
        'lon_wgs': lon_wgs, 'lat_wgs': lat_wgs,
        'water_mask': water_mask, 'valid_W_mask': valid_W_mask,
        'W': W, 'red_mask': red_mask, 'black_mask': black_mask,
        'water_tree': water_tree, 'water_iy': water_iy, 'water_ix': water_ix,
        'kernel': kernel,
        'utm_crs': utm_crs,
        'extent': [data_bounds[0]-0.05, data_bounds[2]+0.05, data_bounds[1]-0.05, data_bounds[3]+0.05]
    }

def run_diffusion_interpolation(do_vals, pts_x, pts_y, grid_info, max_iters=MAX_ITERS, tol=TOL, omega=OMEGA):
    water_mask = grid_info['water_mask']
    Z = np.full(water_mask.shape, np.nan)
    mean_val = np.nanmean(do_vals)
    Z[water_mask] = mean_val
    fixed_mask = np.zeros_like(water_mask, dtype=bool)

    station_coords = np.column_stack([pts_x, pts_y])
    _, nearest_idx = grid_info['water_tree'].query(station_coords)

    water_iy = grid_info['water_iy']
    water_ix = grid_info['water_ix']
    
    for k in range(len(do_vals)):
        iy = water_iy[nearest_idx[k]]
        ix = water_ix[nearest_idx[k]]
        Z[iy, ix] = do_vals[k]
        fixed_mask[iy, ix] = True

    Z_water = np.zeros_like(Z)
    kernel = grid_info['kernel']
    valid_W_mask = grid_info['valid_W_mask']
    W = grid_info['W']
    red_mask = grid_info['red_mask']
    black_mask = grid_info['black_mask']

    for it in range(max_iters):
        Z_old_water = Z[water_mask].copy()
        with np.errstate(divide='ignore', invalid='ignore'):
            Z_water[:] = 0.0
            Z_water[water_mask] = Z[water_mask]
            Z_sum = ndimage.convolve(Z_water, kernel, mode='constant', cval=0.0)
            Z_avg = np.where(valid_W_mask, Z_sum / W, Z)
            update_red = red_mask & water_mask & (~fixed_mask)
            Z[update_red] = (1 - omega) * Z[update_red] + omega * Z_avg[update_red]

            Z_water[:] = 0.0
            Z_water[water_mask] = Z[water_mask]
            Z_sum = ndimage.convolve(Z_water, kernel, mode='constant', cval=0.0)
            Z_avg = np.where(valid_W_mask, Z_sum / W, Z)
            update_black = black_mask & water_mask & (~fixed_mask)
            Z[update_black] = (1 - omega) * Z[update_black] + omega * Z_avg[update_black]

        max_diff = np.max(np.abs(Z[water_mask] - Z_old_water))
        if max_diff < tol:
            break

    return Z
import matplotlib.path as mpath
from matplotlib.patches import PathPatch

def gdf_to_clip_path(gdf, ax):
    """Convert a GeoDataFrame's geometry to a matplotlib Path for clipping on a GeoAxes."""
    union_geom = gdf.geometry.union_all()
    verts = []
    codes = []
    polys = [union_geom] if union_geom.geom_type == 'Polygon' else list(union_geom.geoms)
    for poly in polys:
        coords = np.array(poly.exterior.coords)
        verts.extend(coords)
        codes.append(mpath.Path.MOVETO)
        codes.extend([mpath.Path.LINETO] * (len(coords) - 2))
        codes.append(mpath.Path.CLOSEPOLY)
    return mpath.Path(verts, codes)



# ## 2. Hypoxic Area Fraction Calculation

# Initialize a list to hold the results
fraction_records = []
HYPOXIA_THRESHOLD = 2.0

print(f"Calculating Hypoxic Area Fraction (< {HYPOXIA_THRESHOLD} mg/L) for all regions and years...")
for r_info in regions_info:
    region_name = r_info['name']
    region_data = r_info['data']
    
    # Setup diffusion grid for this region
    data_bounds = region_data.total_bounds
    grid_info = setup_diffusion_grid(r_info['water_mask'], data_bounds)
    if grid_info is None:
        print(f"Skipping {region_name} due to empty grid.")
        continue
        
    valid_w_mask_sum = np.sum(grid_info['valid_W_mask'])
    if valid_w_mask_sum == 0:
        continue
        
    years = sorted(region_data['year'].dropna().unique())
    for y in years:
        df_year = region_data[region_data['year'] == y]
        if len(df_year) < 3: # Need some minimum points to interpolate reasonably
            continue
            
        # Get point coordinates and values
        pts_gdf = df_year.to_crs(grid_info['utm_crs'])
        pts_x = pts_gdf.geometry.x.values
        pts_y = pts_gdf.geometry.y.values
        do_vals = pts_gdf['do_'].values
        
        # Run interpolation
        Z = run_diffusion_interpolation(do_vals, pts_x, pts_y, grid_info)
        
        # Calculate hypoxic area fraction
        # Only evaluate over valid_W_mask (the water area)
        hypoxic_cells = np.sum((Z < HYPOXIA_THRESHOLD) & grid_info['valid_W_mask'])
        hypoxic_fraction = hypoxic_cells / valid_w_mask_sum
        mean_do = np.nanmean(Z[grid_info['valid_W_mask']])
        
        fraction_records.append({
            'Year': y,
            'Region': region_name,
            'Hypoxic_Fraction': hypoxic_fraction,
            'Mean_DO': mean_do,
            'Num_Stations': len(df_year)
        })

df_fractions = pd.DataFrame(fraction_records)
print("Calculation complete!")
df_fractions.head()



# ## 3. Visualization & Comparison (Raw Results)

import seaborn as sns
import matplotlib.pyplot as plt
from utils.mapping_config import MappingConfig

sns.set_theme(style="whitegrid", font_scale=1.5)
MappingConfig.apply_global_plot_styles() # Re-apply to overwrite seaborn defaults
plt.rcParams.update({"figure.autolayout": True, "xtick.labelsize": 14, "ytick.labelsize": 14, "axes.labelsize": 16})

# 3.1 Distribution Box Plots
plt.figure(figsize=(14, 6))
sns.boxplot(data=df_fractions, x='Region', y='Hypoxic_Fraction', palette="Set3")
plt.xticks(rotation=45, ha='right')
plt.title(f"Distribution of Hypoxic Area Fraction (< {HYPOXIA_THRESHOLD} mg/L) across Basins")
plt.ylabel("Hypoxic Area Fraction")
plt.tight_layout()
plt.savefig(OUTPUT_DIR / f'plot_13799.png', bbox_inches='tight', dpi=300)
plt.close()



# 3.2 Time-Series Line Plots
g = sns.FacetGrid(df_fractions, col="Region", col_wrap=4, height=3, aspect=1.5, sharey=False)
g.map(sns.lineplot, "Year", "Hypoxic_Fraction", marker="o")
g.set_axis_labels("Year", "Hypoxic Fraction")
g.set_titles("{col_name}")
plt.suptitle("Raw Yearly Hypoxic Area Fraction Over Time", y=1.02)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / f'plot_14155.png', bbox_inches='tight', dpi=300)
plt.close()



# 3.3 Summary Statistics Table
summary_stats = df_fractions.groupby('Region')['Hypoxic_Fraction'].agg(
    ['mean', 'median', 'min', 'max', 'std', 'count']
).reset_index()
summary_stats.sort_values('median', ascending=False, inplace=True)
summary_stats.style.format(precision=3).background_gradient(cmap='Reds', subset=['mean', 'median', 'max'])



# ## 4. Temporal Smoothing & Trend Analysis

# 4.1 Apply 3-year rolling average
df_fractions.sort_values(['Region', 'Year'], inplace=True)
df_fractions['Smoothed_Fraction'] = df_fractions.groupby('Region')['Hypoxic_Fraction'].transform(
    lambda x: x.rolling(window=3, min_periods=1, center=True).mean()
)

# 4.2 Smoothed Time-Series Plots
g_smooth = sns.FacetGrid(df_fractions, col="Region", col_wrap=4, height=3, aspect=1.5, sharey=False)
g_smooth.map(sns.lineplot, "Year", "Smoothed_Fraction", marker="o", color='darkred')
g_smooth.set_axis_labels("Year", "3-Year Rolling Average Hypoxic Fraction")
g_smooth.set_titles("{col_name}")
plt.suptitle("Smoothed (3-Year Rolling) Hypoxic Area Fraction Over Time", y=1.02)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / f'plot_15257.png', bbox_inches='tight', dpi=300)
plt.close()



# 4.3 Trend Table using linear regression
trend_records = []
for region, group in df_fractions.groupby('Region'):
    # Need sufficient years to calculate trend
    valid_group = group.dropna(subset=['Smoothed_Fraction'])
    if len(valid_group) < 5:
        continue
        
    # Raw trend
    slope_raw, int_raw, r_raw, p_raw, err_raw = stats.linregress(group['Year'], group['Hypoxic_Fraction'])
    # Smoothed trend
    slope_smooth, int_smooth, r_smooth, p_smooth, err_smooth = stats.linregress(valid_group['Year'], valid_group['Smoothed_Fraction'])
    
    trend_records.append({
        'Region': region,
        'Raw_Slope': slope_raw,
        'Raw_P-value': p_raw,
        'Smoothed_Slope': slope_smooth,
        'Smoothed_P-value': p_smooth
    })
    
trend_df = pd.DataFrame(trend_records)
trend_df.sort_values('Smoothed_Slope', ascending=False, inplace=True)
trend_df.style.format(precision=4).background_gradient(cmap='vlag', subset=['Raw_Slope', 'Smoothed_Slope'])


