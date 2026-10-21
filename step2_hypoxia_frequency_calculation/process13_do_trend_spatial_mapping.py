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

# Regions filtered on 'watermass_name' (all others are sub-basins filtered on 'division')
WATERMASS_REGIONS = [str(PARAMS.get('whole_area_region', 'Seto Inland Sea')).strip()] + \
    [v.strip() for v in str(PARAMS.get('bay_regions', 'Tokyo Bay;Ise Bay')).split(';') if v.strip()]

"""
DO Trend Spatial Mapping — Per Bay
Produces DO Trend and Severity Spatial Mapping for a specified division.
Uses a uniform spatial extent based on Iyo Nada (UNIFORM_DX=1.264, UNIFORM_DY=0.709).
"""

import argparse
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, box
from shapely.prepared import prep
from scipy import ndimage, stats
from scipy.spatial import cKDTree
from pyproj import Transformer
import matplotlib.path as mpath
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
SUBPLOT_STATION_SIZE = 16
SUBPLOT_LAND_LW = 0.3
OUTPUT_DPI = 250


GRID_RES = 1000
MAX_ITERS = 500
TOL = 1e-3
OMEGA = 1.8

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

def setup_diffusion_grid(water_boundary_gdf, data_bounds, grid_res=GRID_RES):
    if water_boundary_gdf.crs != "EPSG:4326":
        water_boundary_gdf = water_boundary_gdf.to_crs("EPSG:4326")

    utm_crs = 'EPSG:32653'
    water_utm = water_boundary_gdf.to_crs(utm_crs)
    
    data_bounds_gdf = gpd.GeoDataFrame(
        {'geometry': [Point(data_bounds[0], data_bounds[1]),
                      Point(data_bounds[2], data_bounds[3])]},
        crs="EPSG:4326"
    )
    data_bounds_utm = data_bounds_gdf.to_crs(utm_crs).total_bounds

    minx = data_bounds_utm[0] - 2000
    miny = data_bounds_utm[1] - 2000
    maxx = data_bounds_utm[2] + 2000
    maxy = data_bounds_utm[3] + 2000

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
    water_coords = np.column_stack([grid_x[water_iy, water_ix],
                                     grid_y[water_iy, water_ix]])
    water_tree = cKDTree(water_coords)

    return {
        'grid_x': grid_x, 'grid_y': grid_y,
        'lon_wgs': lon_wgs, 'lat_wgs': lat_wgs,
        'water_mask': water_mask, 'valid_W_mask': valid_W_mask,
        'W': W, 'red_mask': red_mask, 'black_mask': black_mask,
        'water_tree': water_tree, 'water_iy': water_iy, 'water_ix': water_ix,
        'kernel': kernel, 'utm_crs': utm_crs,
        'extent': [data_bounds[0], data_bounds[2], data_bounds[1], data_bounds[3]]
    }

def run_diffusion_interpolation(do_vals, pts_x, pts_y, grid_info,
                                 max_iters=MAX_ITERS, tol=TOL, omega=OMEGA):
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

def gdf_to_clip_path(gdf):
    union_geom = gdf.geometry.union_all()
    verts, codes = [], []
    polys = [union_geom] if union_geom.geom_type == 'Polygon' else list(union_geom.geoms)
    for poly in polys:
        coords = np.array(poly.exterior.coords)
        verts.extend(coords)
        codes.append(mpath.Path.MOVETO)
        codes.extend([mpath.Path.LINETO] * (len(coords) - 2))
        codes.append(mpath.Path.CLOSEPOLY)
    return mpath.Path(verts, codes)

def _add_gridlines(ax):
    return MappingConfig.apply_gridlines(ax)

def load_spatial_data(division):
    if division == 'Tokyo Bay':
        land_boundary = gpd.read_file(ProjectPaths.BOUNDARIES_DIR / 'SIS_prefecture_boundaries' / 'Tokyobay_boundary.shp')
        water_mask = gpd.read_file(ProjectPaths.BOUNDARIES_DIR / 'SIS water mass polygon' / 'sea_area_mask_Tokyo.shp')
    elif division in ['Ise Bay', 'Ise-Mikawa Bay', 'Ise Mikawa Bay']:
        land_boundary = gpd.read_file(ProjectPaths.BOUNDARIES_DIR / 'SIS_prefecture_boundaries' / 'Isebay_boundary.shp')
        water_mask = gpd.read_file(ProjectPaths.BOUNDARIES_DIR / 'SIS water mass polygon' / 'sea_area_mask_Ise.shp')
    else:
        land_boundary = gpd.read_file(ProjectPaths.BOUNDARIES_DIR / 'SIS_prefecture_boundaries' / 'Setonaikai_boundary_2.shp')
        water_mask = gpd.read_file(ProjectPaths.BOUNDARIES_DIR / 'SIS water mass polygon' / 'sea_area_mask_sis_simplified.shp')
    
    return land_boundary.to_crs("EPSG:4326"), water_mask.to_crs("EPSG:4326")

def main():
    args = parse_args()
    division = 'Ise Bay' if args.division in ['Ise-Mikawa Bay', 'Ise Mikawa Bay'] else args.division
    div_clean = division.replace(' ', '_').lower()
    TARGET_SEASON = 'Summer'
    
    logging.info(f"Loading data for division: {division}")
    merged_gdf = load_and_process_data(force_reload=False)
    
    df = merged_gdf[(merged_gdf['season'] == TARGET_SEASON) & (merged_gdf['saisuipoin'] == 2)].copy()
    df['do_'] = pd.to_numeric(df['do_'], errors='coerce')
    df = df.dropna(subset=['do_'])
    
    if division in WATERMASS_REGIONS:
        df = df[df['watermass_name'] == division]
    else:
        df = df[df['division'] == division]

    if df.empty:
        logging.warning(f"No data available for division: {division}")
        return

    land_boundary, water_mask = load_spatial_data(division)
    
    uniform_extent = MappingConfig.get_dynamic_extent(division, plot_data=df)
    dx = uniform_extent[1] - uniform_extent[0]
    dy = uniform_extent[3] - uniform_extent[2]
    
    bbox_geom = box(uniform_extent[0], uniform_extent[2], uniform_extent[1], uniform_extent[3])
    clean_geom = water_mask.geometry.union_all().buffer(0).intersection(bbox_geom).buffer(0)
    clipped_water_mask = gpd.GeoDataFrame(geometry=[clean_geom], crs="EPSG:4326")
    
    dbounds = [uniform_extent[0], uniform_extent[2], uniform_extent[1], uniform_extent[3]]
    grid_info = setup_diffusion_grid(water_mask, dbounds)
    land_patches_data = build_land_patches(land_boundary, MappingConfig.COLOR_LAND, MappingConfig.COLOR_LAND_EDGE, SUBPLOT_LAND_LW)

    if grid_info is None:
        logging.warning("Could not set up grid info.")
        return

    # Figure 3: DO Trend Spatial Mapping
    logging.info("Generating Figure 3: DO Trend Spatial Mapping")
    ALPHA = 0.05  # Mann-Kendall significance threshold
    slopes, lons, lats, sig_flags = [], [], [], []
    for station, group in df.groupby('zettaicode'):
        group = group.dropna(subset=['year', 'do_'])
        if len(group) < 5:
            continue
        slope, *_ = stats.linregress(group['year'], group['do_'])
        # Mann-Kendall test via Kendall's tau (logic from sandbox 80c); used for markers only
        mk_p = stats.kendalltau(group['year'].values, group['do_'].values).pvalue
        slopes.append(slope)
        lons.append(group['longitude'].iloc[0])
        lats.append(group['latitude'].iloc[0])
        sig_flags.append(bool(mk_p < ALPHA))

    if slopes:
        trend_df = pd.DataFrame({'longitude': lons, 'latitude': lats, 'slope': slopes, 'is_significant': sig_flags})
        csv_out = PROCESSED_DATA_DIR / f"do_trend_stats_{div_clean}_{TARGET_SEASON.lower()}.csv"
        trend_df.to_csv(csv_out, index=False)
        stations_gdf = gpd.GeoDataFrame(trend_df, geometry=[Point(xy) for xy in zip(trend_df.longitude, trend_df.latitude)], crs='EPSG:4326').to_crs(grid_info['utm_crs'])
        Z_trend = run_diffusion_interpolation(stations_gdf['slope'].values, stations_gdf.geometry.x.values, stations_gdf.geometry.y.values, grid_info)
        
        global_vmax = max(abs(np.nanmin(Z_trend)), abs(np.nanmax(Z_trend)))
        if global_vmax == 0: global_vmax = 0.1
        global_vmin = -global_vmax
        
        fig_width, fig_height = MappingConfig.get_dynamic_figsize(uniform_extent, base_width=8)
        fig, ax = plt.subplots(1, 1, figsize=(fig_width, fig_height), subplot_kw={'projection': ccrs.PlateCarree()})
        ax.set_facecolor(MappingConfig.COLOR_OCEAN)
        add_land_to_ax(ax, land_patches_data)
        ax.set_extent(uniform_extent, crs=ccrs.PlateCarree())
        
        c_m = ax.pcolormesh(grid_info['lon_wgs'], grid_info['lat_wgs'], Z_trend,
                            transform=ccrs.PlateCarree(), cmap='RdYlBu', shading='nearest',
                            zorder=MappingConfig.ZORDER_PREDICTED, vmin=global_vmin, vmax=global_vmax)
        c_m.set_clip_path(PathPatch(gdf_to_clip_path(clipped_water_mask), transform=ax.transData))
        zoom_factor = max(4.5 / dx, 1.0)
        sig_arr = np.array(sig_flags, dtype=bool)
        lon_arr, lat_arr = np.array(lons), np.array(lats)
        n_sig, n_tot = int(sig_arr.sum()), len(sig_arr)
        # Plot Non-significant stations ('x')
        if (~sig_arr).any():
            ax.scatter(lon_arr[~sig_arr], lat_arr[~sig_arr], c='black', marker='x',
                       s=SUBPLOT_STATION_SIZE * zoom_factor, linewidths=1.2,
                       label=f'Not significant (p \u2265 {ALPHA})',
                       zorder=MappingConfig.ZORDER_OBSERVATIONS, transform=ccrs.PlateCarree())
        # Plot Significant stations ('o' with white edge from 80c)
        if sig_arr.any():
            ax.scatter(lon_arr[sig_arr], lat_arr[sig_arr], c='black', marker='o',
                       s=SUBPLOT_STATION_SIZE * zoom_factor * 1.3, edgecolors='white', linewidths=0.8,
                       label=f'Significant (p < {ALPHA})',
                       zorder=MappingConfig.ZORDER_OBSERVATIONS + 1, transform=ccrs.PlateCarree())
        ax.legend(loc='lower left', frameon=True, framealpha=0.85, fontsize=10)
        logging.info(f"{division}: {n_sig}/{n_tot} stations significant (Mann-Kendall p < {ALPHA})")
        
        ax.set_title(f"Spatial DO Trend (Slope mg/L/year)\n{division}", fontsize=SUBPLOT_TITLE_SIZE, fontweight='bold')
        _add_gridlines(ax)
        
        cbar = fig.colorbar(c_m, ax=ax, orientation='vertical', fraction=0.046, pad=0.04)
        cbar.set_label('DO Trend Slope (mg/L / yr)', fontsize=SUBPLOT_CBAR_LABEL_SIZE)
        cbar.ax.tick_params(labelsize=SUBPLOT_CBAR_TICK_SIZE)
        
        out_path = OUTPUT_DIR / f"do_trend_{div_clean}_{TARGET_SEASON.lower()}.png"
        plt.savefig(out_path, dpi=OUTPUT_DPI, bbox_inches='tight')
        plt.close()

    logging.info(f"Finished processing {division}.")

if __name__ == '__main__':
    main()
