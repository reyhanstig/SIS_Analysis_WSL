# -*- coding: utf-8 -*-
# Script: 22_seasonal_variation_do_bottom_animation.py
# Generated from: 22_seasonal_variation_do.ipynb
#
# This script produces two animations (surface and bottom) for the
# seasonal DO distribution. Each frame shows a 2×2 grid of seasons
# (Spring, Summer, Autumn, Winter) for a single year, using the
# diffusion interpolation method from the notebook.
# Output: 2 fps GIF animations.

# --- 1. Imports ---
import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for animation rendering
import matplotlib.pyplot as plt
import matplotlib.animation as animation
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
import time
from pathlib import Path

project_root = Path("../").resolve()
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from scripts.paths import ProjectPaths
from scripts.mapping_config import MappingConfig

# --- 2. Parameters ---
GRID_RES = 4000    # Grid resolution in meters
MAX_ITERS = 500    # Max SOR iterations
TOL = 1e-3         # Convergence tolerance
OMEGA = 1.8        # SOR relaxation factor
FPS = 2            # Frames per second for the animation

SEASONS = ['Spring', 'Summer', 'Autumn', 'Winter']
LAYERS = ['surface', 'bottom']

# --- 3. Data Loading & Preprocessing ---
print("Loading boundary data...")
water_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS water mass polygon" / "sea_area_mask_simplified.shp"
sis_water_boundary = gpd.read_file(water_boundary_path)
land_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS_prefecture_boundaries" / "Setonaikai_boundary_2.shp"
sis_land_boundary = gpd.read_file(land_boundary_path)

if sis_water_boundary.crs != "EPSG:4326":
    sis_water_boundary = sis_water_boundary.to_crs("EPSG:4326")
if sis_land_boundary.crs != "EPSG:4326":
    sis_land_boundary = sis_land_boundary.to_crs("EPSG:4326")

bounds = sis_water_boundary.total_bounds

# Project water mask to UTM Zone 53N
utm_crs = 'EPSG:32653'
sis_water_utm = sis_water_boundary.to_crs(utm_crs)
bounds_utm = sis_water_utm.total_bounds

# Create grid
grid_x_1d = np.arange(bounds_utm[0], bounds_utm[2], GRID_RES)
grid_y_1d = np.arange(bounds_utm[1], bounds_utm[3], GRID_RES)
grid_x, grid_y = np.meshgrid(grid_x_1d, grid_y_1d)
print(f'Grid shape: {grid_x.shape} ({grid_x.size} points)')

# OPTIMIZED water mask
print("Building water mask...")
water_polygon = sis_water_utm.geometry.union_all()
prepared_poly = prep(water_polygon)
flat_x = grid_x.flatten()
flat_y = grid_y.flatten()
grid_points = [Point(x, y) for x, y in zip(flat_x, flat_y)]
valid_points_mask = np.array([prepared_poly.contains(pt) for pt in grid_points])
water_mask = valid_points_mask.reshape(grid_x.shape)
print(f'Water cells: {water_mask.sum()} / {water_mask.size}')

# Coordinate transform
transformer = Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)
lon_flat, lat_flat = transformer.transform(flat_x, flat_y)
lon_wgs = lon_flat.reshape(grid_x.shape)
lat_wgs = lat_flat.reshape(grid_y.shape)

# Load station data
print("Loading station data...")
merged_gdf = gpd.read_feather(ProjectPaths.MERGED_DATA_FILE)
stations_gdf = merged_gdf[['zettaicode', 'longitude', 'latitude']].drop_duplicates().set_index('zettaicode')
stations_utm = gpd.GeoDataFrame(
    stations_gdf,
    geometry=[Point(xy) for xy in zip(stations_gdf.longitude, stations_gdf.latitude)],
    crs='EPSG:4326'
).to_crs(utm_crs)

# Pre-compute SOR helper matrices
kernel = np.array([[0, 1, 0],
                   [1, 0, 1],
                   [0, 1, 0]])
water_float = water_mask.astype(np.float64)
W = ndimage.convolve(water_float, kernel, mode='constant', cval=0.0)
valid_W_mask = W > 0

i_indices, j_indices = np.indices(grid_x.shape)
red_mask = (i_indices + j_indices) % 2 == 0
black_mask = ~red_mask

# Build KDTree
water_iy, water_ix = np.where(water_mask)
water_coords = np.column_stack([grid_x[water_iy, water_ix],
                                 grid_y[water_iy, water_ix]])
water_tree = cKDTree(water_coords)


# --- 4. Helper Functions ---
def run_diffusion_interpolation(year_data, stations_utm_local,
                                grid_x_1d, grid_y_1d,
                                water_mask, grid_x, grid_y,
                                max_iters=MAX_ITERS, tol=TOL, omega=OMEGA):
    """Optimized SOR diffusion solver with vectorized station snapping."""
    Z = np.full(water_mask.shape, np.nan)
    mean_val = year_data['do_'].mean()
    Z[water_mask] = mean_val
    fixed_mask = np.zeros_like(water_mask, dtype=bool)

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


def load_year_data(s, l, y):
    """Load yearly DO data for a specific season, layer, and year."""
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


def build_land_patches(gdf, facecolor, edgecolor, linewidth):
    """Pre-build land patches for fast rendering."""
    patches = []
    for geom in gdf.geometry:
        if geom.geom_type == 'Polygon':
            patches.append(MplPolygon(np.array(geom.exterior.coords), closed=True))
        elif geom.geom_type == 'MultiPolygon':
            for poly in geom.geoms:
                patches.append(MplPolygon(np.array(poly.exterior.coords), closed=True))
    return patches, facecolor, edgecolor, linewidth


def add_land_to_ax(ax, patches_data):
    """Add land patches to a cartopy axis."""
    patches, fc, ec, lw = patches_data
    
    # Add standard Cartopy Land and Coastlines underneath (standardized baseline)
    ax.add_feature(cfeature.LAND, facecolor=MappingConfig.COLOR_LAND, 
                   zorder=MappingConfig.ZORDER_CARTOPY_LAND)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5, edgecolor='black', 
                   zorder=MappingConfig.ZORDER_CARTOPY_COASTLINE)

    pc = PatchCollection(
        [MplPolygon(p.get_xy(), closed=True) for p in patches],
        facecolor=fc, edgecolor=ec, linewidth=lw,
        transform=ccrs.PlateCarree(),
        zorder=MappingConfig.ZORDER_LAND
    )
    ax.add_collection(pc)


def get_available_years(layer):
    """Get the sorted list of available years across all seasons for a layer."""
    all_years = set()
    for season in SEASONS:
        subset_dir = ProjectPaths.get_subset_dir(season, layer)
        yearly_do_file = subset_dir / "yearly_do_df.csv"
        if yearly_do_file.exists():
            yearly_do_df = pd.read_csv(yearly_do_file, dtype={'zettaicode': str}).set_index('zettaicode')
            years = [col for col in yearly_do_df.columns if str(col).isdigit()]
            all_years.update(years)
    return sorted(all_years)


# --- 5. Build land patches ---
print("Building land patches...")
land_patches_data = build_land_patches(
    sis_land_boundary,
    MappingConfig.COLOR_LAND,
    MappingConfig.COLOR_LAND_EDGE,
    MappingConfig.LINEWIDTH_LAND
)


# --- 6. Pre-compute all interpolation data ---
def precompute_all_data(layer):
    """Pre-compute all diffusion interpolation results for all years and seasons."""
    available_years = get_available_years(layer)
    print(f"  Available years for {layer}: {len(available_years)}")

    all_data = {}  # {year: {season: (Z, do_values)}}

    for y_idx, y in enumerate(available_years):
        year_data = {}
        for season in SEASONS:
            do_values = load_year_data(season, layer, y)
            if do_values is not None and len(do_values) > 0:
                Z = run_diffusion_interpolation(do_values, stations_utm,
                                                 grid_x_1d, grid_y_1d,
                                                 water_mask, grid_x, grid_y)
                year_data[season] = (Z, do_values)
            else:
                year_data[season] = (None, None)
        all_data[y] = year_data
        print(f"    Interpolated year {y} ({y_idx + 1}/{len(available_years)})")

    return available_years, all_data


# --- 7. Create animation ---
def create_animation(layer, available_years, all_data, output_path):
    """Create an MP4 animation for the given layer."""
    var_cfg = MappingConfig.get_var_settings('do_')
    vmin, vmax = var_cfg['vmin'], var_cfg['vmax']
    cmap = var_cfg['cmap']
    label = var_cfg['label']

    # Calculate figure dimensions based on extent aspect ratio
    extent = [bounds[0] - 0.2, bounds[2] + 0.2, bounds[1] - 0.2, bounds[3] + 0.2]
    aspect_ratio = (extent[3] - extent[2]) / (extent[1] - extent[0])

    fig_width = 18
    width_per_subplot = fig_width / 2
    height_per_subplot = (width_per_subplot * aspect_ratio) + 0.3
    fig_height = height_per_subplot * 2

    fig, axes = plt.subplots(2, 2, figsize=(fig_width, fig_height),
                              subplot_kw={'projection': ccrs.PlateCarree()})
    axes_flat = axes.flatten()

    # Reserve space for colorbar
    cbar_ax = fig.add_axes([0.92, 0.15, 0.015, 0.7])

    # Create a dummy ScalarMappable for the colorbar
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
    sm.set_array([])
    cbar = fig.colorbar(sm, cax=cbar_ax)
    cbar.set_label(label, fontsize=14)

    # Title
    suptitle = fig.suptitle('', fontsize=18, fontweight='bold', y=0.95)

    plt.subplots_adjust(right=0.9, wspace=0.05, hspace=0.1)

    def update_frame(frame_idx):
        """Update function for each animation frame."""
        year = available_years[frame_idx]
        year_data = all_data[year]

        for i, season in enumerate(SEASONS):
            ax = axes_flat[i]
            ax.clear()

            ax.set_facecolor(MappingConfig.COLOR_OCEAN)
            add_land_to_ax(ax, land_patches_data)
            ax.set_extent([bounds[0] - 0.2, bounds[2] + 0.2,
                           bounds[1] - 0.2, bounds[3] + 0.2],
                          crs=ccrs.PlateCarree())

            Z, do_values = year_data[season]

            if Z is not None and do_values is not None:
                ax.pcolormesh(lon_wgs, lat_wgs, Z,
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

            ax.set_title(f'{season} {year}', fontsize=14)
            ax.set_xticks([])
            ax.set_yticks([])

        suptitle.set_text(f'Seasonal DO Distribution: {year} ({layer})')
        return axes_flat

    print(f"  Creating animation with {len(available_years)} frames at {FPS} fps...")
    anim = animation.FuncAnimation(
        fig, update_frame,
        frames=len(available_years),
        interval=1000 // FPS,
        blit=False
    )

    # Save animation using Pillow writer (GIF format)
    writer = animation.PillowWriter(fps=FPS)
    anim.save(str(output_path), writer=writer, dpi=150)
    print(f"  Animation saved to: {output_path}")

    plt.close(fig)


# --- 8. Main execution ---
if __name__ == '__main__':
    # Use standardized output directory logic from ProjectPaths
    output_dir = ProjectPaths.get_seasonal_plots_dir('do_', 'grid_2x2')

    for layer in LAYERS:
        print(f"\n{'=' * 60}")
        print(f"Processing layer: {layer}")
        print(f"{'=' * 60}")

        t_start = time.time()

        # Pre-compute all interpolation data
        print("Pre-computing interpolation data...")
        available_years, all_data = precompute_all_data(layer)

        t_interp = time.time() - t_start
        print(f"  Interpolation done in {t_interp:.2f}s")

        if len(available_years) == 0:
            print(f"  No data available for {layer}. Skipping.")
            continue

        # Create animation
        output_path = output_dir / f"seasonal_do_{layer}_animation.gif"
        create_animation(layer, available_years, all_data, output_path)

        t_total = time.time() - t_start
        print(f"  Total time for {layer}: {t_total:.2f}s")

    print("\nAll animations complete!")
