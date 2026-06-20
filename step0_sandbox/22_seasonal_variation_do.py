# -*- coding: utf-8 -*-
# Auto-generated from: 22_seasonal_variation.ipynb
# Generated on: 2026-03-01 19:45:35
# This script was converted from a Jupyter Notebook.
# Markdown cells have been converted to comments.


# # Seasonal Variation using Diffusion Interpolation (v3 - Optimized)
#
# This notebook visualizes the seasonal variation of Dissolved Oxygen using
# the physics-based steady-state diffusion interpolation method.
#
# **Key optimizations over v2:**
# - Grid resolution: 4000 m (vs 2000 m) — ~4× fewer cells
# - Water mask: `shapely.prepared.prep` for vectorized spatial lookup
# - Coordinate reprojection: `pyproj.Transformer` (vectorized, no GeoDataFrame)
# - Station snapping: `scipy.spatial.cKDTree` (vectorized, no per-row loop)
# - SOR solver: `max_iters=500`, `tol=1e-3`, `omega=1.8`
# - Plotting: Pre-built `PatchCollection` for land (avoids repeated `draw_idle()`)

# --- 1. Imports ---
import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import scipy.ndimage as ndimage
from scipy.spatial import cKDTree
from shapely.geometry import Point
from shapely.prepared import prep
from pyproj import Transformer
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon as MplPolygon
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.paths import ProjectPaths
from scripts.mapping_config import MappingConfig


# ## 2. Parameters (The "Control Panel")

# --- Parameters ---
season = 'Summer'
layer = 'bottom'
target_year = '1991'

# --- Performance Tuning ---
GRID_RES = 4000    # Grid resolution in meters (4000m is ~4x faster than 2000m)
MAX_ITERS = 500    # Max SOR iterations
TOL = 1e-3         # Convergence tolerance
OMEGA = 1.8        # SOR relaxation factor


# ## 3. Data Loading & Preprocessing

# 1. Load Custom Boundary Shapefiles (WGS84)
water_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS water mass polygon" / "sea_area_mask_simplified.shp"
sis_water_boundary = gpd.read_file(water_boundary_path)
land_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS_prefecture_boundaries" / "Setonaikai_boundary.shp"
sis_land_boundary = gpd.read_file(land_boundary_path)

if sis_water_boundary.crs != "EPSG:4326":
    sis_water_boundary = sis_water_boundary.to_crs("EPSG:4326")
if sis_land_boundary.crs != "EPSG:4326":
    sis_land_boundary = sis_land_boundary.to_crs("EPSG:4326")

bounds = sis_water_boundary.total_bounds

# 2. Project water mask to UTM Zone 53N to define the computation grid
utm_crs = 'EPSG:32653'
sis_water_utm = sis_water_boundary.to_crs(utm_crs)
bounds_utm = sis_water_utm.total_bounds

# 3. Create grid (optimized resolution)
grid_x_1d = np.arange(bounds_utm[0], bounds_utm[2], GRID_RES)
grid_y_1d = np.arange(bounds_utm[1], bounds_utm[3], GRID_RES)
grid_x, grid_y = np.meshgrid(grid_x_1d, grid_y_1d)
print(f'Grid shape: {grid_x.shape} ({grid_x.size} points)')

# 4. OPTIMIZED water mask: prepared geometry for fast spatial lookup
water_polygon = sis_water_utm.geometry.union_all()
prepared_poly = prep(water_polygon)
flat_x = grid_x.flatten()
flat_y = grid_y.flatten()
grid_points = [Point(x, y) for x, y in zip(flat_x, flat_y)]
valid_points_mask = np.array([prepared_poly.contains(pt) for pt in grid_points])
water_mask = valid_points_mask.reshape(grid_x.shape)
print(f'Water cells: {water_mask.sum()} / {water_mask.size}')

# 5. OPTIMIZED coordinate transform: pyproj Transformer (vectorized)
transformer = Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)
lon_flat, lat_flat = transformer.transform(flat_x, flat_y)
lon_wgs = lon_flat.reshape(grid_x.shape)
lat_wgs = lat_flat.reshape(grid_y.shape)

# 6. Load station data
merged_gdf = gpd.read_feather(ProjectPaths.MERGED_DATA_FILE)
stations_gdf = merged_gdf[['zettaicode', 'longitude', 'latitude']].drop_duplicates().set_index('zettaicode')
stations_utm = gpd.GeoDataFrame(
    stations_gdf,
    geometry=[Point(xy) for xy in zip(stations_gdf.longitude, stations_gdf.latitude)],
    crs='EPSG:4326'
).to_crs(utm_crs)

# 7. Pre-compute SOR helper matrices (reused for every year)
kernel = np.array([[0, 1, 0],
                   [1, 0, 1],
                   [0, 1, 0]])
water_float = water_mask.astype(np.float64)
W = ndimage.convolve(water_float, kernel, mode='constant', cval=0.0)
valid_W_mask = W > 0

i_indices, j_indices = np.indices(grid_x.shape)
red_mask = (i_indices + j_indices) % 2 == 0
black_mask = ~red_mask

# 8. Build KDTree of water grid cells for fast station snapping
water_iy, water_ix = np.where(water_mask)
water_coords = np.column_stack([grid_x[water_iy, water_ix],
                                 grid_y[water_iy, water_ix]])
water_tree = cKDTree(water_coords)


# 4. Optimized Diffusion Interpolation Solver
def run_diffusion_interpolation(year_data, stations_utm_local,
                                grid_x_1d, grid_y_1d,
                                water_mask, grid_x, grid_y,
                                max_iters=MAX_ITERS, tol=TOL, omega=OMEGA):
    """Optimized SOR diffusion solver with vectorized station snapping."""
    Z = np.full(water_mask.shape, np.nan)
    mean_val = year_data['do_'].mean()
    Z[water_mask] = mean_val
    fixed_mask = np.zeros_like(water_mask, dtype=bool)

    # Vectorized station snapping via KDTree
    common_ids = year_data.index.intersection(stations_utm_local.index)
    if len(common_ids) == 0:
        return Z

    pts_x = stations_utm_local.loc[common_ids].geometry.x.values
    pts_y = stations_utm_local.loc[common_ids].geometry.y.values
    do_vals = year_data.loc[common_ids, 'do_'].values

    station_coords = np.column_stack([pts_x, pts_y])
    _, nearest_idx = water_tree.query(station_coords)

    for k in range(len(common_ids)):
        iy = water_iy[nearest_idx[k]]
        ix = water_ix[nearest_idx[k]]
        Z[iy, ix] = do_vals[k]
        fixed_mask[iy, ix] = True

    # Pre-allocate work array
    Z_water = np.zeros_like(Z)

    for it in range(max_iters):
        Z_old_water = Z[water_mask].copy()

        with np.errstate(divide='ignore', invalid='ignore'):
            # Red update
            Z_water[:] = 0.0
            Z_water[water_mask] = Z[water_mask]
            Z_sum = ndimage.convolve(Z_water, kernel, mode='constant', cval=0.0)
            Z_avg = np.where(valid_W_mask, Z_sum / W, Z)
            update_red = red_mask & water_mask & (~fixed_mask)
            Z[update_red] = (1 - omega) * Z[update_red] + omega * Z_avg[update_red]

            # Black update
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


# Helper function to load data
def load_year_data(s, l, y):
    subset_dir = ProjectPaths.get_subset_dir(s, l)
    yearly_do_file = subset_dir / "yearly_do_df.csv"
    if not yearly_do_file.exists():
        return None
    yearly_do_df = pd.read_csv(yearly_do_file, dtype={'zettaicode': str}).set_index('zettaicode')
    if str(y) in yearly_do_df.columns:
        y_col = str(y)
    elif int(y) in yearly_do_df.columns:
        y_col = int(y)
    else:
        return None
    do_values = yearly_do_df[[y_col]].dropna().rename(columns={y_col: 'do_'})
    return do_values


# Pre-build land patches once (avoids expensive .plot() + draw_idle() per subplot)
def build_land_patches(gdf, facecolor, edgecolor, linewidth):
    patches = []
    for geom in gdf.geometry:
        if geom.geom_type == 'Polygon':
            patches.append(MplPolygon(np.array(geom.exterior.coords), closed=True))
        elif geom.geom_type == 'MultiPolygon':
            for poly in geom.geoms:
                patches.append(MplPolygon(np.array(poly.exterior.coords), closed=True))
    return patches, facecolor, edgecolor, linewidth

land_patches_data = build_land_patches(
    sis_land_boundary,
    MappingConfig.COLOR_LAND,
    MappingConfig.COLOR_LAND_EDGE,
    MappingConfig.LINEWIDTH_LAND
)

def add_land_to_ax(ax, patches_data):
    patches, fc, ec, lw = patches_data
    
    # 1. Plot standard Cartopy Land and Coastlines underneath
    ax.add_feature(cfeature.LAND, facecolor=MappingConfig.COLOR_LAND, zorder=MappingConfig.ZORDER_CARTOPY_LAND)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5, edgecolor='black', zorder=MappingConfig.ZORDER_CARTOPY_COASTLINE)

    # 2. Plot high-resolution land masses on top
    pc = PatchCollection(
        [MplPolygon(p.get_xy(), closed=True) for p in patches],
        facecolor=fc, edgecolor=ec, linewidth=lw,
        transform=ccrs.PlateCarree(),
        zorder=MappingConfig.ZORDER_LAND
    )
    ax.add_collection(pc)


# ## 4. Single Map Visualization
# Single map for a single year for a single parameter (DO)

do_values = load_year_data(season, layer, target_year)

if do_values is not None and len(do_values) > 0:
    Z = run_diffusion_interpolation(do_values, stations_utm,
                                     grid_x_1d, grid_y_1d,
                                     water_mask, grid_x, grid_y)

    var_cfg = MappingConfig.get_var_settings('do_')
    vmin, vmax = var_cfg['vmin'], var_cfg['vmax']
    cmap = var_cfg['cmap']
    label = var_cfg['label']

    fig, ax = plt.subplots(1, 1, figsize=(14, 10),
                           subplot_kw={'projection': ccrs.PlateCarree()})
    
    # Ocean Background
    ax.set_facecolor(MappingConfig.COLOR_OCEAN)
    
    # Custom Coastal Boundaries (Land) - keeps the optimized patch drawing from v3
    add_land_to_ax(ax, land_patches_data)
    
    # Extent
    ax.set_extent([bounds[0]+0.1, bounds[2]+0.1,
                   bounds[1]-0, bounds[3]+0.2], crs=ccrs.PlateCarree())

    # Add Gridlines to match SIS Mapping Standard
    gl = ax.gridlines(draw_labels=True, 
                      linestyle=MappingConfig.GRID_LINESTYLE, 
                      color=MappingConfig.GRID_COLOR, 
                      alpha=MappingConfig.GRID_ALPHA, 
                      linewidth=MappingConfig.GRID_LINEWIDTH, 
                      zorder=MappingConfig.ZORDER_GRIDLINES)
    gl.top_labels = False
    gl.right_labels = False

    # Predicted Data Overlay
    c_m = ax.pcolormesh(lon_wgs, lat_wgs, Z,
                        transform=ccrs.PlateCarree(),
                        cmap=cmap, shading='nearest',
                        zorder=MappingConfig.ZORDER_PREDICTED,
                        vmin=vmin, vmax=vmax)

    # Observation Data Overlay
    plot_df = do_values.join(stations_gdf, how='inner')
    ax.scatter(plot_df['longitude'], plot_df['latitude'],
               c=plot_df['do_'], cmap=cmap,
               edgecolors='black', linewidth=0.2,
               transform=ccrs.PlateCarree(),
               zorder=MappingConfig.ZORDER_OBSERVATIONS,
               marker='^', s=25, vmin=vmin, vmax=vmax)

    cbar = fig.colorbar(c_m, ax=ax, shrink=0.7)
    cbar.set_label(label, fontsize=14)
    ax.set_title(f'DO Interpolation: {season} {target_year} ({layer})',
                 fontsize=16, fontweight='bold')
    
    # Removed set_xticks([]) and set_yticks([]) to allow standard gridlines to show
    plt.tight_layout()
    plt.show()
else:
    print(f'No data for {season} {target_year} ({layer})')


# ## 5. Four-Season Layout (2×2) for Target Year

seasons = ['Spring', 'Summer', 'Autumn', 'Winter']
var_cfg = MappingConfig.get_var_settings('do_')
vmin, vmax = var_cfg['vmin'], var_cfg['vmax']
cmap = var_cfg['cmap']
label = var_cfg['label']

# Dynamically calculated height based on extent aspect ratio
extent = [bounds[0]+0.1, bounds[2]+0.1, bounds[1]-0, bounds[3]+0.2]
aspect_ratio = (extent[3] - extent[2]) / (extent[1] - extent[0])

fig_width = 18
width_per_subplot = fig_width / 2
height_per_subplot = (width_per_subplot * aspect_ratio) + 0.3
fig_height = height_per_subplot * 2

fig, axes = plt.subplots(2, 2, figsize=(fig_width, fig_height),
                          subplot_kw={'projection': ccrs.PlateCarree()})
axes = axes.flatten()

for i, s in enumerate(seasons):
    ax = axes[i]
    ax.set_facecolor(MappingConfig.COLOR_OCEAN)
    add_land_to_ax(ax, land_patches_data)
    ax.set_extent([bounds[0]+0.1, bounds[2]+0.1, bounds[1]-0, bounds[3]+0.2],
                  crs=ccrs.PlateCarree())

    do_values = load_year_data(s, layer, target_year)
    if do_values is not None and len(do_values) > 0:
        Z = run_diffusion_interpolation(do_values, stations_utm,
                                         grid_x_1d, grid_y_1d,
                                         water_mask, grid_x, grid_y)
        c_m = ax.pcolormesh(lon_wgs, lat_wgs, Z,
                            transform=ccrs.PlateCarree(),
                            cmap=cmap, shading='nearest',
                            zorder=MappingConfig.ZORDER_PREDICTED,
                            vmin=vmin, vmax=vmax)

        plot_df = do_values.join(stations_gdf, how='inner')
        ax.scatter(plot_df['longitude'], plot_df['latitude'],
                   c=plot_df['do_'], cmap=cmap,
                   edgecolors='black', linewidth=0.2,
                   transform=ccrs.PlateCarree(),
                   zorder=MappingConfig.ZORDER_OBSERVATIONS,
                   marker='^', s=10, vmin=vmin, vmax=vmax)

    ax.set_title(f'{s} {target_year}', fontsize=14)
    
    # Gridlines and Tickers following SIS Mapping Standard
    # "only keep the bottom most and leftmost ticker labels"
    gl = ax.gridlines(draw_labels=True, linestyle=MappingConfig.GRID_LINESTYLE,
                      color=MappingConfig.GRID_COLOR, alpha=MappingConfig.GRID_ALPHA,
                      linewidth=MappingConfig.GRID_LINEWIDTH, zorder=MappingConfig.ZORDER_GRIDLINES)
    gl.top_labels = False
    gl.right_labels = False
    gl.bottom_labels = True if i >= 2 else False
    gl.left_labels = True if i % 2 == 0 else False

# Colorbar
cbar_ax = fig.add_axes([0.92, 0.15, 0.015, 0.7])
cbar = fig.colorbar(c_m, cax=cbar_ax)
cbar.set_label(label, fontsize=14)
plt.suptitle(f'Seasonal DO Distribution: {target_year} ({layer})',
             fontsize=18, fontweight='bold', y=0.95)
plt.subplots_adjust(right=0.9, wspace=0.05, hspace=0.1)
plt.show()


# ## 6. Progressive Seasonal Subplots (All Years)
# All available years for the target season, plotted in a grid.

import time

seasons = ['Spring', 'Summer', 'Autumn', 'Winter']

for season in seasons:
    print(f"--- Processing {season} ---")
    t_start = time.time()
    
    # Load yearly data for the specific season
    subset_dir = ProjectPaths.get_subset_dir(season, layer)
    yearly_do_file = subset_dir / "yearly_do_df.csv"
    
    if not yearly_do_file.exists():
        print(f"Data file not found for {season}. Skipping.\n")
        continue
        
    yearly_do_df = pd.read_csv(yearly_do_file, dtype={'zettaicode': str}).set_index('zettaicode')
    available_years = sorted([col for col in yearly_do_df.columns if str(col).isdigit()])
    n_years = len(available_years)
    print(f'Interpolating {n_years} years...')
    
    # --- Interpolation pass (the expensive part) ---
    all_Z = {}
    for y in available_years:
        do_values = yearly_do_df[[y]].dropna().rename(columns={y: 'do_'})
        if len(do_values) > 0:
            all_Z[y] = run_diffusion_interpolation(
                do_values, stations_utm,
                grid_x_1d, grid_y_1d,
                water_mask, grid_x, grid_y)
    
    t_interp = time.time() - t_start
    print(f'{season} interpolation done in {t_interp:.2f}s')
    
    if n_years == 0:
        continue
        
    # --- Plotting pass ---
    var_cfg = MappingConfig.get_var_settings('do_')
    vmin, vmax = var_cfg['vmin'], var_cfg['vmax']
    cmap = var_cfg['cmap']
    label = var_cfg['label']
    
    n_cols = 5
    n_rows = int(np.ceil(n_years / n_cols))

    # Dynamically calculated height based on extent aspect ratio
    extent = [bounds[0]+0.1, bounds[2]+0.1, bounds[1]-0, bounds[3]+0.2]
    aspect_ratio = (extent[3] - extent[2]) / (extent[1] - extent[0])

    fig_width = 25
    width_per_subplot = fig_width / n_cols
    height_per_subplot = (width_per_subplot * aspect_ratio) + 0.3
    fig_height = height_per_subplot * n_rows

    fig, axes = plt.subplots(n_rows, n_cols,
                            figsize=(fig_width, fig_height),
                            subplot_kw={'projection': ccrs.PlateCarree()})

    
    # Safely flatten axes 
    if isinstance(axes, np.ndarray):
        axes = axes.flatten()
    else:
        axes = [axes]
        
    c_m = None
    
    for i, y in enumerate(available_years):
        ax = axes[i]
        ax.set_facecolor(MappingConfig.COLOR_OCEAN)
        add_land_to_ax(ax, land_patches_data)
        ax.set_extent([bounds[0]+0.1, bounds[2]+0.1,
                       bounds[1]-0, bounds[3]+0.2],
                      crs=ccrs.PlateCarree())
    
        if y in all_Z:
            Z = all_Z[y]
            c_m = ax.pcolormesh(lon_wgs, lat_wgs, Z,
                                transform=ccrs.PlateCarree(),
                                cmap=cmap, shading='nearest',
                                zorder=MappingConfig.ZORDER_PREDICTED,
                                vmin=vmin, vmax=vmax)
    
            do_values = yearly_do_df[[y]].dropna().rename(columns={y: 'do_'})
            plot_df = do_values.join(stations_gdf, how='inner')
            ax.scatter(plot_df['longitude'], plot_df['latitude'],
                       c=plot_df['do_'], cmap=cmap,
                       edgecolors='black', linewidth=0.2,
                       transform=ccrs.PlateCarree(),
                       zorder=MappingConfig.ZORDER_OBSERVATIONS,
                       marker='^', s=10, vmin=vmin, vmax=vmax)
    
        ax.set_title(f'{y}', fontsize=12)
        ax.set_xticks([])
        ax.set_yticks([])
    
    # Remove unused axes for the specific season's grid
    for j in range(len(available_years), len(axes)):
        fig.delaxes(axes[j])
    
    # Single colorbar per season figure
    if c_m is not None:
        cbar_ax = fig.add_axes([0.92, 0.15, 0.015, 0.7])
        cbar = fig.colorbar(c_m, cax=cbar_ax)
        cbar.set_label(label, fontsize=14)
    
    plt.suptitle(f'Progressive DO Interpolation: {season}',
                 fontsize=20, fontweight='bold', y=0.92)
    plt.subplots_adjust(right=0.9, wspace=0.05, hspace=0.1)
    
    t_total = time.time() - t_start
    print(f'Total {season} cell time: {t_total:.2f}s\n')
    plt.show()
