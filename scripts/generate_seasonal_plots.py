"""
Standalone Python script to generate high-quality seasonal DO plots.
Implemented with multiprocessing for performance, supporting multiple 
plot types (individual, progressive, and 2x2 grids).
"""

import sys
import time
import argparse
from pathlib import Path
from multiprocessing import Pool, cpu_count
from functools import partial

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from shapely.geometry import Point, MultiPolygon, Polygon
import shapely.wkt
import pyproj
from scipy.spatial import cKDTree
from scipy.sparse import lil_matrix
from scipy.sparse.linalg import spsolve
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon as MplPolygon
import yaml

# Add project root to path for local imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from scripts.paths import ProjectPaths
from scripts.mapping_config import MappingConfig

# ---------------------------------------------------------------------------
# Mapping Utilities & Standard Configuration
# (Ported from reports/SIS_mapping_standard.md and notebooks)
# ---------------------------------------------------------------------------

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
    pc = PatchCollection(
        [MplPolygon(p.get_xy(), closed=True) for p in patches],
        facecolor=fc, edgecolor=ec, linewidth=lw,
        transform=ccrs.PlateCarree(),
        zorder=MappingConfig.ZORDER_LAND
    )
    ax.add_collection(pc)


# ---------------------------------------------------------------------------
# Fast Diffusion Equation Solver
# ---------------------------------------------------------------------------

def compute_grid_geometry(bounds_utm, grid_res=4000):
    """Compute basic WGS84 and projected UTM mesh grids."""
    grid_x_1d = np.arange(bounds_utm[0], bounds_utm[2], grid_res)
    grid_y_1d = np.arange(bounds_utm[1], bounds_utm[3], grid_res)
    grid_x, grid_y = np.meshgrid(grid_x_1d, grid_y_1d)
    
    utm_crs = 'EPSG:32653'
    transformer = pyproj.Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)
    flat_x = grid_x.flatten()
    flat_y = grid_y.flatten()
    
    lon_flat, lat_flat = transformer.transform(flat_x, flat_y)
    lon_wgs = lon_flat.reshape(grid_x.shape)
    lat_wgs = lat_flat.reshape(grid_y.shape)
    return grid_x, grid_y, lon_wgs, lat_wgs

def create_mask_and_kdtree(boundaries_utm_gdf, grid_x, grid_y):
    """Create the sea mask and KDTree for the solver."""
    import shapely.prepared
    
    water_polygon = boundaries_utm_gdf.geometry.union_all()
    prepared_poly = shapely.prepared.prep(water_polygon)
    
    flat_x = grid_x.flatten()
    flat_y = grid_y.flatten()
    
    grid_points = [Point(x, y) for x, y in zip(flat_x, flat_y)]
    valid_points_mask = np.array([prepared_poly.contains(pt) for pt in grid_points])
    water_mask = valid_points_mask.reshape(grid_x.shape)
    
    water_iy, water_ix = np.where(water_mask)
    water_coords = np.column_stack([grid_x[water_iy, water_ix],
                                     grid_y[water_iy, water_ix]])
    tree = cKDTree(water_coords)
    return water_mask, tree, water_iy, water_ix

import scipy.ndimage as ndimage
def get_sor_helper_matrices(water_mask, grid_x):
    kernel = np.array([[0, 1, 0],
                       [1, 0, 1],
                       [0, 1, 0]])
    water_float = water_mask.astype(np.float64)
    W = ndimage.convolve(water_float, kernel, mode='constant', cval=0.0)
    valid_W_mask = W > 0

    i_indices, j_indices = np.indices(grid_x.shape)
    red_mask = (i_indices + j_indices) % 2 == 0
    black_mask = ~red_mask
    return kernel, W, valid_W_mask, red_mask, black_mask

def run_diffusion_interpolation(plot_df, stations_utm,
                                water_mask, water_tree, water_iy, water_ix,
                                kernel, W, valid_W_mask, red_mask, black_mask, parameter,
                                max_iters=500, tol=1e-3, omega=1.8):
    """Optimized SOR diffusion solver with vectorized station snapping."""
    import scipy.ndimage as ndimage
    Z = np.full(water_mask.shape, np.nan)
    mean_val = plot_df[parameter].mean()
    Z[water_mask] = mean_val
    fixed_mask = np.zeros_like(water_mask, dtype=bool)

    # Vectorized station snapping via KDTree
    common_ids = plot_df.index.intersection(stations_utm.index)
    if len(common_ids) == 0:
        return Z

    pts_x = stations_utm.loc[common_ids].geometry.x.values
    pts_y = stations_utm.loc[common_ids].geometry.y.values
    do_vals = plot_df.loc[common_ids, parameter].values

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

# ---------------------------------------------------------------------------
# Multiprocessing Worker Data Structure & Logic
# ---------------------------------------------------------------------------

# Global variables initialized once in the worker process
worker_data = {}

def init_worker(shared_objects):
    """Initialize worker process with expensive geometric and matrix data."""
    global worker_data
    worker_data = shared_objects

def process_single_permutation(task_info):
    """
    Worker function to run interpolation and general grid preparation for a single season/layer/year.
    Returns the Z matrix and metadata so the main process (or specific plotting functions) 
    can just focus on drawing to matplotlib aggressively.
    """
    year = task_info['year']
    season = task_info['season']
    layer = task_info['layer']
    parameter = task_info['parameter']
    
    key = f"{season.lower()}_{layer.lower()}"
    
    if parameter not in worker_data['yearly_param_data']:
        return None
        
    if key not in worker_data['yearly_param_data'][parameter]:
        return None
        
    yearly_df = worker_data['yearly_param_data'][parameter][key]
    
    if year not in yearly_df.columns:
        return None
        
    values = yearly_df[[year]].dropna().rename(columns={year: parameter})
    if values.empty:
        return None
        
    values.index.name = 'station_id'
    plot_df = values.join(worker_data['stations_gdf'], how='inner')
    
    # Run optimized solver
    Z = run_diffusion_interpolation(plot_df, worker_data['stations_utm'],
                                    worker_data['sea_mask'], worker_data['tree'],
                                    worker_data['water_iy'], worker_data['water_ix'],
                                    worker_data['kernel'], worker_data['W'],
                                    worker_data['valid_W_mask'], worker_data['red_mask'],
                                    worker_data['black_mask'], parameter)
                           
    return {
        'year': year,
        'season': season,
        'layer': layer,
        'parameter': parameter,
        'plot_df': plot_df,
        'Z': Z
    }

# ---------------------------------------------------------------------------
# Plotting Implementations
# ---------------------------------------------------------------------------

def draw_map_on_ax(ax, res, shared_objects, draw_labels=False):
    """Draw a standard interpolated map on a given axes."""
    var_cfg = MappingConfig.get_var_settings(res['parameter'])
    vmin, vmax = var_cfg['vmin'], var_cfg['vmax']
    cmap = var_cfg['cmap']
    
    bounds = shared_objects['bounds']
    
    ax.set_facecolor(MappingConfig.COLOR_OCEAN)
    
    # Set Map Extent (padding added to boundaries to fit perfectly)
    ax.set_extent([bounds[0]-0.2, bounds[2]+0.2, bounds[1]-0.2, bounds[3]+0.2],
                  crs=ccrs.PlateCarree())

    add_land_to_ax(ax, shared_objects['land_patches'])
                   
    # Add Gridlines to match SIS Mapping Standard
    gl = ax.gridlines(draw_labels=draw_labels, 
                      linestyle=MappingConfig.GRID_LINESTYLE, 
                      color=MappingConfig.GRID_COLOR, 
                      alpha=MappingConfig.GRID_ALPHA, 
                      linewidth=MappingConfig.GRID_LINEWIDTH, 
                      zorder=MappingConfig.ZORDER_GRIDLINES)
    gl.top_labels = False
    gl.right_labels = False
                   
    c_m = ax.pcolormesh(shared_objects['lon_wgs'], shared_objects['lat_wgs'], res['Z'],
                        transform=ccrs.PlateCarree(),
                        cmap=cmap, shading='nearest',
                        zorder=MappingConfig.ZORDER_PREDICTED,
                        vmin=vmin, vmax=vmax)
                        
    plot_df = res['plot_df']
    ax.scatter(plot_df['longitude'], plot_df['latitude'],
               c=plot_df[res['parameter']], cmap=cmap,
               edgecolors='black', linewidth=0.2,
               transform=ccrs.PlateCarree(),
               zorder=MappingConfig.ZORDER_OBSERVATIONS,
               marker='^', s=25, vmin=vmin, vmax=vmax)
               
    return c_m

def generate_individual_plot(res, shared_objects, out_dir):
    """Generate and save a single high-res plot."""
    if res is None: return
    
    fig, ax = plt.subplots(figsize=(14, 10), subplot_kw={'projection': ccrs.PlateCarree()})
    
    c_m = draw_map_on_ax(ax, res, shared_objects, draw_labels=True)
    
    ax.set_title(f"{res['year']} {res['season']} ({res['layer']})", fontsize=14)
    var_cfg = MappingConfig.get_var_settings(res['parameter'])
    cbar = plt.colorbar(c_m, ax=ax, shrink=0.7, extend=var_cfg.get('extend', 'both'))
    MappingConfig.format_colorbar_ticks(cbar, res['parameter'])
    cbar.set_label(var_cfg['label'], fontsize=14)
    
    out_path = out_dir / f"{res['year']}_{res['season']}_{res['layer']}.png"
    plt.savefig(out_path, bbox_inches='tight', dpi=300)
    plt.close(fig) # CRITICAL memory management

def generate_grid_2x2_plot(year, layer, parameter, season_results, shared_objects, out_dir):
    """Generate a 2x2 grid representing the 4 seasons of a specific year."""
    # Ensure we only try to plot if we have at least one result
    if not any(res is not None for res in season_results.values()):
        return

    fig, axes = plt.subplots(2, 2, figsize=(10, 8), subplot_kw={'projection': ccrs.PlateCarree()})
    axes = axes.flatten()
    
    seasons_order = ['Spring', 'Summer', 'Autumn', 'Winter']
    c_m_final = None
    
    for i, season in enumerate(seasons_order):
        ax = axes[i]
        res = season_results.get(season)
        
        if res is not None:
            c_m = draw_map_on_ax(ax, res, shared_objects, draw_labels=False)
            if c_m is not None:
                c_m_final = c_m
            
        ax.set_title(season, fontsize=12)
        
    if c_m_final is not None:
        cbar_ax = fig.add_axes([0.92, 0.15, 0.02, 0.7])
        var_cfg = MappingConfig.get_var_settings(parameter)
        cbar = fig.colorbar(c_m_final, cax=cbar_ax, extend=var_cfg.get('extend', 'both'))
        MappingConfig.format_colorbar_ticks(cbar, parameter)
        cbar.set_label(var_cfg['label'], fontsize=14)
        
    plt.suptitle(f"{year} Seasonal Spatial Distribution ({layer})", fontsize=16, fontweight='bold', y=0.92)
    plt.subplots_adjust(wspace=0.05, hspace=0.05)
    
    out_path = out_dir / f"grid_2x2_{year}_{layer}.png"
    plt.savefig(out_path, bbox_inches='tight', dpi=300)
    plt.close(fig)

def generate_progressive_plot(season, layer, parameter, years, year_results, shared_objects, out_dir):
    """Generate a row-based grid showing year-over-year progression for a specific season."""
    valid_results = [res for y in years if (res := year_results.get(y)) is not None]
    if not valid_results:
        return
        
    n_cols = 5
    n_rows = int(np.ceil(len(valid_results) / n_cols))
    
    bounds = shared_objects['bounds']
    aspect_ratio = (bounds[3] - bounds[2]) / (bounds[1] - bounds[0])
    
    fig_width = 25
    width_per_subplot = fig_width / n_cols
    height_per_subplot = (width_per_subplot * aspect_ratio) + 0.3
    fig_height = max(height_per_subplot * n_rows, 5) # Ensure valid height
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(fig_width, fig_height), 
                             subplot_kw={'projection': ccrs.PlateCarree()})
    
    if isinstance(axes, np.ndarray): axes = axes.flatten()
    else: axes = [axes]
    
    c_m_final = None
    for i, res in enumerate(valid_results):
        ax = axes[i]
        c_m = draw_map_on_ax(ax, res, shared_objects, draw_labels=False)
        if c_m is not None: c_m_final = c_m
        
        ax.set_title(f"{res['year']}", fontsize=12)
        
    # Remove unused axes
    for j in range(len(valid_results), len(axes)):
        fig.delaxes(axes[j])
        
    if c_m_final is not None:
        cbar_ax = fig.add_axes([0.92, 0.15, 0.015, 0.7])
        var_cfg = MappingConfig.get_var_settings(parameter)
        cbar = fig.colorbar(c_m_final, cax=cbar_ax, extend=var_cfg.get('extend', 'both'))
        MappingConfig.format_colorbar_ticks(cbar, parameter)
        cbar.set_label(var_cfg['label'], fontsize=14)
        
    plt.suptitle(f"Progressive Spatial Distribution: {season} ({layer})", fontsize=20, fontweight='bold', y=0.92)
    plt.subplots_adjust(right=0.9, wspace=0.05, hspace=0.05)
    
    out_path = out_dir / f"progressive_{season}_{layer}.png"
    plt.savefig(out_path, bbox_inches='tight', dpi=150) # lower DPI for massive grids
    plt.close(fig)

# ---------------------------------------------------------------------------
# Main Execution
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-mode", action="store_true", help="Run in sequential mode for testing")
    args = parser.parse_args()

    print("Loading parameters from params.yaml...")
    with open(ProjectPaths.PROJECT_ROOT / "params.yaml", "r") as f:
        params = yaml.safe_load(f)
        
    cfg = params.get('seasonal_plots', {})
    parameters = cfg.get('parameters', ['do_'])
    seasons = cfg.get('seasons', ['Spring', 'Summer', 'Autumn', 'Winter'])
    layers = cfg.get('layers', ['surface', 'bottom'])
    years_to_process = [str(y) for y in cfg.get('years', ['1991'])]
    plot_types = cfg.get('plot_types', {})
    
    print("Loading geographic boundaries...")
    water_boundary_file = ProjectPaths.BOUNDARIES_DIR / "SIS water mass polygon" / "sea_area_mask_simplified.shp"
    boundaries_gdf = gpd.read_file(water_boundary_file).to_crs("EPSG:4326")
    bounds = boundaries_gdf.total_bounds # [minx, miny, maxx, maxy]
    
    land_boundary_file = ProjectPaths.BOUNDARIES_DIR / "SIS_prefecture_boundaries" / "Setonaikai_boundary.shp"
    sis_land_boundary = gpd.read_file(land_boundary_file).to_crs("EPSG:4326")
    
    print("Pre-calculating geometry and masks...")
    utm_crs = 'EPSG:32653'
    sis_water_utm = boundaries_gdf.to_crs(utm_crs)
    bounds_utm = sis_water_utm.total_bounds
    
    grid_x, grid_y, lon_wgs, lat_wgs = compute_grid_geometry(bounds_utm, 4000)
    sea_mask, tree, water_iy, water_ix = create_mask_and_kdtree(sis_water_utm, grid_x, grid_y)
    kernel, W, valid_W_mask, red_mask, black_mask = get_sor_helper_matrices(sea_mask, grid_x)
    land_patches = build_land_patches(sis_land_boundary, MappingConfig.COLOR_LAND, MappingConfig.COLOR_LAND_EDGE, MappingConfig.LINEWIDTH_LAND)
    
    print("Loading station logic...")
    merged_data_path = ProjectPaths.MERGED_DATA_FILE
    df = pd.read_feather(merged_data_path)
    stations_df = df[['zettaicode', 'latitude', 'longitude']].drop_duplicates(subset=['zettaicode'])
    stations_df['station_id'] = stations_df['zettaicode']
    stations_df.set_index('station_id', inplace=True)
    stations_gdf = gpd.GeoDataFrame(stations_df, 
                                    geometry=gpd.points_from_xy(stations_df.longitude, stations_df.latitude), 
                                    crs="EPSG:4326")
    stations_utm = stations_gdf.to_crs(utm_crs)
                                    
    print("Loading seasonal datasets into memory...")
    yearly_param_data = {}
    for param in parameters:
        yearly_param_data[param] = {}
        for season in seasons:
            for layer in layers:
                key = f"{season.lower()}_{layer.lower()}"
                sub_dir = ProjectPaths.get_subset_dir(season, layer)
                param_file = sub_dir / f"yearly_{param}_df.csv"
                if param_file.exists():
                    df_param = pd.read_csv(param_file, dtype={'zettaicode': str}).set_index('zettaicode')
                    # Ensure columns are strings
                    df_param.columns = df_param.columns.astype(str)
                    yearly_param_data[param][key] = df_param
                
    # Build shared objects dict for multiprocessing workers
    shared_objects = {
        'sea_mask': sea_mask,
        'tree': tree,
        'water_iy': water_iy,
        'water_ix': water_ix,
        'kernel': kernel,
        'W': W,
        'valid_W_mask': valid_W_mask,
        'red_mask': red_mask,
        'black_mask': black_mask,
        'stations_gdf': stations_gdf,
        'stations_utm': stations_utm,
        'yearly_param_data': yearly_param_data,
        'bounds': bounds,
        'lon_wgs': lon_wgs,
        'lat_wgs': lat_wgs,
        'land_patches': land_patches
    }
    
    # Create all task permutations
    # Identify permutations. For progressive plots, we must calculate ALL years.
    tasks = []
    
    for p in parameters:
        for s in seasons:
            for l in layers:
                key = f"{s.lower()}_{l.lower()}"
                
                # If we need progressive plots, ensure we include all years
                if plot_types.get('progressive', False) and p in yearly_param_data and key in yearly_param_data[p]:
                    all_years = [c for c in yearly_param_data[p][key].columns if c.isdigit()]
                    target_years = sorted(list(set(years_to_process + all_years)))
                else:
                    target_years = years_to_process
                    
                for y in target_years:
                    # Prevent duplicates
                    if not any(t['parameter']==p and t['year']==y and t['season']==s and t['layer']==l for t in tasks):
                        tasks.append({
                            'parameter': p,
                            'year': y,
                            'season': s,
                            'layer': l
                        })
                    
    print(f"Prepared {len(tasks)} target permutations.")
    
    # 1. Run interpolation heavily in parallel. 
    # The solver is the huge bottleneck. Matplotlib is also a bottleneck, but we'll return 
    # the matrices and selectively plot what we need.
    print(f"Beginning spatial interpolation sweeps...")
    t_start = time.time()
    
    results = []
    if args.test_mode:
        print("Running in TEST (Sequential) Mode...")
        init_worker(shared_objects)
        for t in tasks:
            results.append(process_single_permutation(t))
    else:
        cores = max(1, cpu_count() - 1)
        print(f"Running via Multiprocessing ({cores} cores)...")
        with Pool(cores, initializer=init_worker, initargs=(shared_objects,)) as pool:
            results = pool.map(process_single_permutation, tasks)
            
    # Filter out empty results
    valid_results = [r for r in results if r is not None]
    print(f"Interpolation complete in {time.time() - t_start:.2f}s. Valid grids generated: {len(valid_results)}")
    
    # Organize results by identifiers for easy grid retrieval
    def get_res(p_name, y_name, s_name, l_name):
        return next((r for r in valid_results if r['parameter']==p_name and r['year']==y_name and r['season']==s_name and r['layer']==l_name), None)

    # 2. Draw Plots based on user flags
    print("Beginning plot rendering to disk...")
    
    for parameter in parameters:
        if plot_types.get('individual', False):
            ind_dir = ProjectPaths.get_seasonal_plots_dir(parameter, 'individual')
            for res in valid_results:
                if res['parameter'] == parameter:
                    generate_individual_plot(res, shared_objects, ind_dir)
                    
        if plot_types.get('grid_2x2', False):
            grid_dir = ProjectPaths.get_seasonal_plots_dir(parameter, 'grid_2x2')
            for year in years_to_process:
                for layer in layers:
                    season_dict = {s: get_res(parameter, year, s, layer) for s in seasons}
                    generate_grid_2x2_plot(year, layer, parameter, season_dict, shared_objects, grid_dir)
                    
        if plot_types.get('progressive', False):
            prog_dir = ProjectPaths.get_seasonal_plots_dir(parameter, 'progressive')
            for season in seasons:
                for layer in layers:
                    key = f"{season.lower()}_{layer.lower()}"
                    if parameter in yearly_param_data and key in yearly_param_data[parameter]:
                        avail_years = sorted([c for c in yearly_param_data[parameter][key].columns if c.isdigit()])
                    else:
                        avail_years = []
                    
                    year_dict = {y: get_res(parameter, y, season, layer) for y in avail_years}
                    generate_progressive_plot(season, layer, parameter, avail_years, year_dict, shared_objects, prog_dir)

    print("All plotting operations completed successfully!")

if __name__ == "__main__":
    main()
