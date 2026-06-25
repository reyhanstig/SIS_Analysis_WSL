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
"""
54. Hypoxia Frequency & Trend Mapping — All Divisions (Multi-Panel)

Produces three figures, each containing identically scaled subplots for every basin division:
  1. Yearly Mean DO Distribution Map
  2. Hypoxia Frequency Map (Hypoxic 0-2 mg/L)
  3. DO Trend and Severity Spatial Mapping
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, box
from shapely.prepared import prep
from scipy import ndimage, stats
from scipy.spatial import cKDTree
from pyproj import Transformer
import matplotlib.pyplot as plt
import matplotlib.path as mpath
from matplotlib.patches import Polygon as MplPolygon, PathPatch
from matplotlib.collections import PatchCollection
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import sys
from pathlib import Path
import warnings

warnings.filterwarnings('ignore')

# ---------------------------------------------------------------------------
# Project path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.paths import ProjectPaths
from utils.mapping_config import MappingConfig
from utils.data_loader import load_and_process_data

# ---------------------------------------------------------------------------
# Compact subplot style overrides
# ---------------------------------------------------------------------------
SUBPLOT_TITLE_SIZE = 20
SUBPLOT_LABEL_SIZE = 18
SUBPLOT_TICK_SIZE = 16
SUBPLOT_CBAR_LABEL_SIZE = 18
SUBPLOT_CBAR_TICK_SIZE = 16
SUBPLOT_STATION_SIZE = 16          # Enlarged scatter marker size for station dots
SUBPLOT_GRIDLINE_LW = 0.3
SUBPLOT_LAND_LW = 0.3
SUPTITLE_SIZE = 24

# Uniform Extent Spans (Computed from Iyo Nada)
UNIFORM_DX = 1.264
UNIFORM_DY = 0.709

# Apply base styles then override for compact layout
MappingConfig.apply_global_plot_styles()
plt.rcParams.update({
    'font.size': 16,
    'axes.titlesize': SUBPLOT_TITLE_SIZE,
    'axes.labelsize': SUBPLOT_LABEL_SIZE,
    'xtick.labelsize': SUBPLOT_TICK_SIZE,
    'ytick.labelsize': SUBPLOT_TICK_SIZE,
    'legend.fontsize': 12,
    'figure.titlesize': SUPTITLE_SIZE,
    'figure.titleweight': 'bold',
})

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
GRID_RES = 1000
MAX_ITERS = 500
TOL = 1e-3
OMEGA = 1.8
NCOLS = 4            # subplot grid columns
OUTPUT_DPI = 250

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
print("Loading data...")
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

# ---------------------------------------------------------------------------
# Helper functions
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
    """Sets up the grid, KDTree, and masks for diffusion interpolation using cached GeoDataFrame."""
    if water_boundary_gdf.crs != "EPSG:4326":
        water_boundary_gdf = water_boundary_gdf.to_crs("EPSG:4326")

    utm_crs = 'EPSG:32653'
    water_utm = water_boundary_gdf.to_crs(utm_crs)
    bounds_utm = water_utm.total_bounds

    data_bounds_gdf = gpd.GeoDataFrame(
        {'geometry': [Point(data_bounds[0], data_bounds[1]),
                      Point(data_bounds[2], data_bounds[3])]},
        crs="EPSG:4326"
    )
    data_bounds_utm = data_bounds_gdf.to_crs(utm_crs).total_bounds

    # Ensure the grid fully encompasses the uniform extent window
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
    """Convert a GeoDataFrame's geometry to a matplotlib Path for clipping."""
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
    """Add compact gridlines to a GeoAxes subplot."""
    gl = ax.gridlines(draw_labels=False,
                      linestyle=MappingConfig.GRID_LINESTYLE,
                      color=MappingConfig.GRID_COLOR,
                      alpha=MappingConfig.GRID_ALPHA,
                      linewidth=SUBPLOT_GRIDLINE_LW,
                      zorder=MappingConfig.ZORDER_GRIDLINES)
    return gl

def add_global_scalebar(ax_scale):
    """Draw a 20km scalebar on a dedicated transparent geographic axes."""
    ax_scale.set_visible(True)
    ax_scale.axis('off')
    ax_scale.set_extent([0, UNIFORM_DX, 0, UNIFORM_DY], crs=ccrs.PlateCarree())
    
    # Calculate degree length of 20km at roughly 34 deg N
    km_per_deg_lon = 111.32 * np.cos(np.radians(34.0))
    deg_20km = 20.0 / km_per_deg_lon
    
    lon_start = UNIFORM_DX * 0.4
    lon_end = lon_start + deg_20km
    lat_pos = UNIFORM_DY * 0.35
    
    # Draw line and text
    ax_scale.plot([lon_start, lon_end], [lat_pos, lat_pos], color='black', lw=3, transform=ccrs.PlateCarree())
    ax_scale.text((lon_start + lon_end)/2, lat_pos + 0.05, '20 km', ha='center', va='bottom', 
                  fontsize=SUBPLOT_LABEL_SIZE+2, fontweight='bold', transform=ccrs.PlateCarree())

# ---------------------------------------------------------------------------
# Pre-caching regions and geometric processing
# ---------------------------------------------------------------------------
print("Pre-caching shapefiles and computing uniform grids...")
sis_land_boundary = gpd.read_file(ProjectPaths.BOUNDARIES_DIR / 'SIS_prefecture_boundaries' / 'Setonaikai_boundary_2.shp').to_crs("EPSG:4326")
sis_water_mask = gpd.read_file(ProjectPaths.BOUNDARIES_DIR / 'SIS water mass polygon' / 'sea_area_mask_sis_simplified.shp').to_crs("EPSG:4326")

tokyo_land = gpd.read_file(ProjectPaths.BOUNDARIES_DIR / 'SIS_prefecture_boundaries' / 'Tokyobay_boundary.shp').to_crs("EPSG:4326")
tokyo_water = gpd.read_file(ProjectPaths.BOUNDARIES_DIR / 'SIS water mass polygon' / 'sea_area_mask_Tokyo.shp').to_crs("EPSG:4326")

ise_land = gpd.read_file(ProjectPaths.BOUNDARIES_DIR / 'SIS_prefecture_boundaries' / 'Isebay_boundary.shp').to_crs("EPSG:4326")
ise_water = gpd.read_file(ProjectPaths.BOUNDARIES_DIR / 'SIS water mass polygon' / 'sea_area_mask_Ise.shp').to_crs("EPSG:4326")

regions_info = [
    {
        'name': 'Tokyo Bay',
        'land_boundary': tokyo_land,
        'water_mask': tokyo_water,
        'data': summer_bottom_df[summer_bottom_df['watermass_name'] == 'Tokyo Bay'].copy()
    },
    {
        'name': 'Ise Bay',
        'land_boundary': ise_land,
        'water_mask': ise_water,
        'data': summer_bottom_df[summer_bottom_df['watermass_name'] == 'Ise Bay'].copy()
    }
]

sis_df = summer_bottom_df[summer_bottom_df['watermass_name'] == 'Seto Inland Sea']
sis_divisions = sis_df['division'].dropna().unique().tolist()
for div in sis_divisions:
    regions_info.append({
        'name': div,
        'land_boundary': sis_land_boundary,
        'water_mask': sis_water_mask,
        'data': sis_df[sis_df['division'] == div].copy()
    })

n_regions = len(regions_info)
NROWS = int(np.ceil(n_regions / NCOLS))
print(f"Total regions: {n_regions}  →  grid {NROWS}×{NCOLS}")

# Generate spatial data and grids
for r in regions_info:
    df = r['data']
    if df.empty:
        r['extent'] = None
        r['grid_info'] = None
        continue
    
    # Calculate geographic center
    minx, maxx = df['longitude'].min(), df['longitude'].max()
    miny, maxy = df['latitude'].min(), df['latitude'].max()
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    
    # Uniform extent based on reference basin
    uniform_extent = [cx - UNIFORM_DX/2, cx + UNIFORM_DX/2, cy - UNIFORM_DY/2, cy + UNIFORM_DY/2]
    r['extent'] = uniform_extent
    
    # Compute the intersection of the water mask with the bounding box so pcolormesh won't bleed
    bbox_geom = box(uniform_extent[0], uniform_extent[2], uniform_extent[1], uniform_extent[3])
    clean_geom = r['water_mask'].geometry.union_all().buffer(0).intersection(bbox_geom).buffer(0)
    r['clipped_water_mask'] = gpd.GeoDataFrame(geometry=[clean_geom], crs="EPSG:4326")
    
    # data_bounds for diffusion grid must be [minlon, minlat, maxlon, maxlat]
    dbounds = [uniform_extent[0], uniform_extent[2], uniform_extent[1], uniform_extent[3]]
    r['grid_info'] = setup_diffusion_grid(r['water_mask'], dbounds)
    r['land_patches_data'] = build_land_patches(r['land_boundary'], MappingConfig.COLOR_LAND, MappingConfig.COLOR_LAND_EDGE, SUBPLOT_LAND_LW)


# =========================================================================
# FIGURE 1 — Yearly Mean DO Distribution Map
# =========================================================================
def figure_yearly_mean_do():
    print("\n" + "=" * 60)
    print("Figure 1: Yearly Mean DO Distribution Map")
    print("=" * 60)

    var_cfg = MappingConfig.get_var_settings('do_')
    vmin, vmax = var_cfg['vmin'], var_cfg['vmax']
    cmap = var_cfg['cmap']
    label = var_cfg['label']

    fig, axes = plt.subplots(NROWS, NCOLS,
                             figsize=(NCOLS * 4.0, NROWS * 3.2),
                             subplot_kw={'projection': ccrs.PlateCarree()})
    axes_flat = axes.flatten()
    last_cm = None

    for idx, region in enumerate(regions_info):
        ax = axes_flat[idx]
        name = region['name']
        df = region['data']
        grid_info = region['grid_info']
        print(f"  Processing {name}...")

        if grid_info is None:
            ax.set_visible(False)
            continue

        station_mean = df.groupby('zettaicode')[['do_', 'longitude', 'latitude']].mean()
        stations_gdf = gpd.GeoDataFrame(
            station_mean,
            geometry=[Point(xy) for xy in zip(station_mean.longitude, station_mean.latitude)],
            crs='EPSG:4326'
        ).to_crs(grid_info['utm_crs'])

        pts_x = stations_gdf.geometry.x.values
        pts_y = stations_gdf.geometry.y.values
        do_vals = stations_gdf['do_'].values

        Z = run_diffusion_interpolation(do_vals, pts_x, pts_y, grid_info)

        ax.set_facecolor(MappingConfig.COLOR_OCEAN)
        add_land_to_ax(ax, region['land_patches_data'])
        ax.set_extent(region['extent'], crs=ccrs.PlateCarree())

        c_m = ax.pcolormesh(grid_info['lon_wgs'], grid_info['lat_wgs'], Z,
                            transform=ccrs.PlateCarree(),
                            cmap=cmap, shading='nearest',
                            zorder=MappingConfig.ZORDER_PREDICTED,
                            vmin=vmin, vmax=vmax)

        # Apply strictly clipped boundary to prevent bleeding
        clip_path = gdf_to_clip_path(region['clipped_water_mask'])
        clip_patch = PathPatch(clip_path, transform=ax.transData)
        c_m.set_clip_path(clip_patch)

        ax.scatter(station_mean['longitude'], station_mean['latitude'],
                   c='black', s=SUBPLOT_STATION_SIZE,
                   zorder=MappingConfig.ZORDER_OBSERVATIONS,
                   transform=ccrs.PlateCarree())

        ax.set_title(name, fontsize=SUBPLOT_TITLE_SIZE, fontweight='bold')
        _add_gridlines(ax)
        last_cm = c_m

    for idx in range(n_regions, len(axes_flat)):
        axes_flat[idx].set_visible(False)

    fig.suptitle('Mean Climatological Bottom DO by Division',
                 fontsize=SUPTITLE_SIZE, fontweight='bold', y=1.0)
    
    plt.subplots_adjust(left=0.05, right=0.98, bottom=0.18, top=0.92, wspace=0.1, hspace=0.5)

    if last_cm is not None:
        cbar_ax = fig.add_axes([0.3, 0.10, 0.4, 0.02])
        cbar = fig.colorbar(last_cm, cax=cbar_ax, orientation='horizontal')
        cbar.set_label(label, fontsize=SUBPLOT_CBAR_LABEL_SIZE)
        cbar.ax.tick_params(labelsize=SUBPLOT_CBAR_TICK_SIZE)
        MappingConfig.format_colorbar_ticks(cbar, 'do_')

    add_global_scalebar(axes_flat[-1])

    out_path = ProjectPaths.FIGURES_DIR / '54_yearly_mean_do_all_divisions.png'
    fig.savefig(out_path, dpi=OUTPUT_DPI, bbox_inches='tight')
    print(f"  Saved → {out_path}")
    plt.close(fig)


# =========================================================================
# FIGURE 2 — Hypoxia Frequency Map (Hypoxic Only)
# =========================================================================
def figure_frequency_map():
    print("\n" + "=" * 60)
    print("Figure 2: Hypoxia Frequency Map (Hypoxic 0-2 mg/L)")
    print("=" * 60)

    fig, axes = plt.subplots(NROWS, NCOLS,
                             figsize=(NCOLS * 4.0, NROWS * 3.2),
                             subplot_kw={'projection': ccrs.PlateCarree()})
    axes_flat = axes.flatten()
    last_sc = None

    for idx, region in enumerate(regions_info):
        ax = axes_flat[idx]
        name = region['name']
        df = region['data']
        extent = region['extent']

        if extent is None:
            ax.set_visible(False)
            continue

        def calc_freq(group):
            total_years = group['year'].nunique()
            cond_years = group[(group['do_'] >= 0.0) & (group['do_'] <= 2.0)]['year'].nunique()
            return (cond_years / total_years) * 100

        freq_df = df.groupby(['zettaicode', 'longitude', 'latitude']).apply(calc_freq).reset_index(name='frequency')

        ax.set_facecolor(MappingConfig.COLOR_OCEAN)
        add_land_to_ax(ax, region['land_patches_data'])
        ax.set_extent(extent, crs=ccrs.PlateCarree())

        # Enlarged dynamic marker sizing
        marker_sizes = freq_df['frequency'] * 2.4 + 24

        sc = ax.scatter(freq_df['longitude'], freq_df['latitude'],
                        c=freq_df['frequency'], cmap='Reds', vmin=0, vmax=100,
                        s=marker_sizes, edgecolor='k', linewidth=0.3,
                        transform=ccrs.PlateCarree(),
                        zorder=MappingConfig.ZORDER_OBSERVATIONS)

        ax.set_title(name, fontsize=SUBPLOT_TITLE_SIZE, fontweight='bold')
        _add_gridlines(ax)
        last_sc = sc
        print(f"  Processed {name}")

    for idx in range(n_regions, len(axes_flat)):
        axes_flat[idx].set_visible(False)

    fig.suptitle('Hypoxia Frequency (0-2 mg/L) by Division',
                 fontsize=SUPTITLE_SIZE, fontweight='bold', y=1.0)
    
    plt.subplots_adjust(left=0.05, right=0.98, bottom=0.18, top=0.92, wspace=0.1, hspace=0.5)

    if last_sc is not None:
        cbar_ax = fig.add_axes([0.3, 0.10, 0.4, 0.02])
        cbar = fig.colorbar(last_sc, cax=cbar_ax, orientation='horizontal')
        cbar.set_label('Frequency (%)', fontsize=SUBPLOT_CBAR_LABEL_SIZE)
        cbar.ax.tick_params(labelsize=SUBPLOT_CBAR_TICK_SIZE)

    add_global_scalebar(axes_flat[-1])

    out_path = ProjectPaths.FIGURES_DIR / '54_hypoxia_frequency_all_divisions.png'
    fig.savefig(out_path, dpi=OUTPUT_DPI, bbox_inches='tight')
    print(f"  Saved → {out_path}")
    plt.close(fig)


# =========================================================================
# FIGURE 3 — DO Trend & Severity Spatial Mapping
# =========================================================================
def figure_do_trend():
    print("\n" + "=" * 60)
    print("Figure 3: DO Trend Spatial Mapping")
    print("=" * 60)

    fig, axes = plt.subplots(NROWS, NCOLS,
                             figsize=(NCOLS * 4.0, NROWS * 3.2),
                             subplot_kw={'projection': ccrs.PlateCarree()})
    axes_flat = axes.flatten()

    all_Z_min, all_Z_max = [], []
    plot_data = {}

    for idx, region in enumerate(regions_info):
        name = region['name']
        df = region['data']
        grid_info = region['grid_info']

        if grid_info is None:
            continue

        slopes, lons, lats = [], [], []
        for station, group in df.groupby('zettaicode'):
            group = group.dropna(subset=['year', 'do_'])
            if len(group) < 5:
                continue
            slope, *_ = stats.linregress(group['year'], group['do_'])
            slopes.append(slope)
            lons.append(group['longitude'].iloc[0])
            lats.append(group['latitude'].iloc[0])

        if not slopes:
            continue

        trend_df = pd.DataFrame({'longitude': lons, 'latitude': lats, 'slope': slopes})
        stations_gdf = gpd.GeoDataFrame(
            trend_df,
            geometry=[Point(xy) for xy in zip(trend_df.longitude, trend_df.latitude)],
            crs='EPSG:4326'
        ).to_crs(grid_info['utm_crs'])

        pts_x = stations_gdf.geometry.x.values
        pts_y = stations_gdf.geometry.y.values
        do_vals = stations_gdf['slope'].values

        Z = run_diffusion_interpolation(do_vals, pts_x, pts_y, grid_info)

        all_Z_min.append(np.nanmin(Z))
        all_Z_max.append(np.nanmax(Z))

        plot_data[idx] = {
            'Z': Z, 'lons': lons, 'lats': lats
        }
        print(f"  Computed trend for {name}")

    if all_Z_min and all_Z_max:
        global_vmax = max(abs(min(all_Z_min)), abs(max(all_Z_max)))
    else:
        global_vmax = 0.1
    global_vmin = -global_vmax

    last_cm = None
    for idx, region in enumerate(regions_info):
        ax = axes_flat[idx]
        if idx not in plot_data:
            ax.set_visible(False)
            continue

        pd_entry = plot_data[idx]
        grid_info = region['grid_info']
        Z = pd_entry['Z']
        name = region['name']
        lons = pd_entry['lons']
        lats = pd_entry['lats']

        ax.set_facecolor(MappingConfig.COLOR_OCEAN)
        add_land_to_ax(ax, region['land_patches_data'])
        ax.set_extent(region['extent'], crs=ccrs.PlateCarree())

        c_m = ax.pcolormesh(grid_info['lon_wgs'], grid_info['lat_wgs'], Z,
                            transform=ccrs.PlateCarree(),
                            cmap='RdYlBu', shading='nearest',
                            zorder=MappingConfig.ZORDER_PREDICTED,
                            vmin=global_vmin, vmax=global_vmax)

        clip_path = gdf_to_clip_path(region['clipped_water_mask'])
        clip_patch = PathPatch(clip_path, transform=ax.transData)
        c_m.set_clip_path(clip_patch)

        ax.scatter(lons, lats, c='black', s=SUBPLOT_STATION_SIZE,
                   zorder=MappingConfig.ZORDER_OBSERVATIONS,
                   transform=ccrs.PlateCarree())

        ax.set_title(name, fontsize=SUBPLOT_TITLE_SIZE, fontweight='bold')
        _add_gridlines(ax)
        last_cm = c_m

    for idx in range(n_regions, len(axes_flat)):
        axes_flat[idx].set_visible(False)

    fig.suptitle('Spatial DO Trend (Slope mg/L/year) by Division',
                 fontsize=SUPTITLE_SIZE, fontweight='bold', y=1.0)
    
    plt.subplots_adjust(left=0.05, right=0.98, bottom=0.18, top=0.92, wspace=0.1, hspace=0.5)

    if last_cm is not None:
        cbar_ax = fig.add_axes([0.3, 0.10, 0.4, 0.02])
        cbar = fig.colorbar(last_cm, cax=cbar_ax, orientation='horizontal')
        cbar.set_label('DO Trend Slope (mg/L / yr)', fontsize=SUBPLOT_CBAR_LABEL_SIZE)
        cbar.ax.tick_params(labelsize=SUBPLOT_CBAR_TICK_SIZE)

    add_global_scalebar(axes_flat[-1])

    out_path = ProjectPaths.FIGURES_DIR / '54_do_trend_all_divisions.png'
    fig.savefig(out_path, dpi=OUTPUT_DPI, bbox_inches='tight')
    print(f"  Saved → {out_path}")
    plt.close(fig)

# =========================================================================
# Main
# =========================================================================
if __name__ == '__main__':
    figure_yearly_mean_do()
    figure_frequency_map()
    figure_do_trend()
    print("\n✓ All three figures generated successfully.")
