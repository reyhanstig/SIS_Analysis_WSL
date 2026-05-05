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
import time

warnings.filterwarnings('ignore')

# 1. Project Path Setup
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from scripts.paths import ProjectPaths
from scripts.mapping_config import MappingConfig

# 2. Setup constants
GRID_RES = 4000
MAX_ITERS = 500
TOL = 1e-3
OMEGA = 1.8

# 3. Loading geometry
water_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS water mass polygon" / "sea_area_mask_simplified.shp"
sis_water_boundary = gpd.read_file(water_boundary_path)
land_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS_prefecture_boundaries" / "Setonaikai_boundary.shp"
sis_land_boundary = gpd.read_file(land_boundary_path)

if sis_water_boundary.crs != "EPSG:4326":
    sis_water_boundary = sis_water_boundary.to_crs("EPSG:4326")
if sis_land_boundary.crs != "EPSG:4326":
    sis_land_boundary = sis_land_boundary.to_crs("EPSG:4326")

bounds = sis_water_boundary.total_bounds
utm_crs = 'EPSG:32653'
sis_water_utm = sis_water_boundary.to_crs(utm_crs)
bounds_utm = sis_water_utm.total_bounds

grid_x_1d = np.arange(bounds_utm[0], bounds_utm[2], GRID_RES)
grid_y_1d = np.arange(bounds_utm[1], bounds_utm[3], GRID_RES)
grid_x, grid_y = np.meshgrid(grid_x_1d, grid_y_1d)

water_polygon = sis_water_utm.geometry.union_all()
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

merged_gdf = gpd.read_feather(ProjectPaths.MERGED_DATA_FILE)
stations_gdf = merged_gdf[['zettaicode', 'longitude', 'latitude']].drop_duplicates().set_index('zettaicode')
stations_utm = gpd.GeoDataFrame(
    stations_gdf,
    geometry=[Point(xy) for xy in zip(stations_gdf.longitude, stations_gdf.latitude)],
    crs='EPSG:4326'
).to_crs(utm_crs)

kernel = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]])
water_float = water_mask.astype(np.float64)
W = ndimage.convolve(water_float, kernel, mode='constant', cval=0.0)
valid_W_mask = W > 0

i_indices, j_indices = np.indices(grid_x.shape)
red_mask = (i_indices + j_indices) % 2 == 0
black_mask = ~red_mask

water_iy, water_ix = np.where(water_mask)
water_coords = np.column_stack([grid_x[water_iy, water_ix], grid_y[water_iy, water_ix]])
water_tree = cKDTree(water_coords)

def run_diffusion_interpolation(year_data, stations_utm_local,
                                grid_x_1d, grid_y_1d,
                                water_mask, grid_x, grid_y,
                                max_iters=MAX_ITERS, tol=TOL, omega=OMEGA):
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


def calculate_mean_diffusion(season, layer):
    print(f"Calculating mean diffusion for {season} {layer}...")
    subset_dir = ProjectPaths.get_subset_dir(season, layer)
    yearly_do_file = subset_dir / "yearly_do_df.csv"
    if not yearly_do_file.exists():
        print(f"Data file not found for {season}. Returning None.")
        return None
    
    yearly_do_df = pd.read_csv(yearly_do_file, dtype={'zettaicode': str}).set_index('zettaicode')
    available_years = sorted([col for col in yearly_do_df.columns if str(col).isdigit()])
    
    if len(available_years) == 0:
        return None
        
    print(f'Interpolating {len(available_years)} years...')
    all_Z = []
    for y in available_years:
        do_values = yearly_do_df[[y]].dropna().rename(columns={y: 'do_'})
        if len(do_values) > 0:
            Z = run_diffusion_interpolation(
                do_values, stations_utm,
                grid_x_1d, grid_y_1d,
                water_mask, grid_x, grid_y)
            all_Z.append(Z)
    
    if not all_Z:
        return None
        
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        # Calculate mean across all interpolated years, ignoring NaNs
        mean_Z = np.nanmean(all_Z, axis=0)
    
    return mean_Z


def plot_single_seasonal_means():
    seasons = ['Spring', 'Summer', 'Autumn', 'Winter']
    layer = 'bottom'
    
    for season in seasons:
        mean_Z = calculate_mean_diffusion(season, layer)
        
        if mean_Z is None:
            print(f"Failed to calculate mean for {season} {layer}.")
            continue
            
        var_cfg = MappingConfig.get_var_settings('do_')
        vmin, vmax = var_cfg['vmin'], var_cfg['vmax']
        cmap = var_cfg['cmap']
        label = var_cfg['label']

        fig, ax = plt.subplots(1, 1, figsize=(14, 10), subplot_kw={'projection': ccrs.PlateCarree()})
        ax.set_facecolor(MappingConfig.COLOR_OCEAN)
        add_land_to_ax(ax, land_patches_data)
        ax.set_extent([bounds[0]+0.1, bounds[2]+0.1, bounds[1]-0, bounds[3]+0.2], crs=ccrs.PlateCarree())

        c_m = ax.pcolormesh(lon_wgs, lat_wgs, mean_Z,
                            transform=ccrs.PlateCarree(),
                            cmap=cmap, shading='nearest',
                            zorder=MappingConfig.ZORDER_PREDICTED,
                            vmin=vmin, vmax=vmax)

        ax.set_title(f'Mean Climatological DO: {season} ({layer.capitalize()}) (1981-2023)', fontsize=16)
        
        # Gridlines and Tickers for single map
        gl = ax.gridlines(draw_labels=True, linestyle=MappingConfig.GRID_LINESTYLE,
                          color=MappingConfig.GRID_COLOR, alpha=MappingConfig.GRID_ALPHA,
                          linewidth=MappingConfig.GRID_LINEWIDTH, zorder=MappingConfig.ZORDER_GRIDLINES)
        gl.top_labels = False
        gl.right_labels = False
        
        cbar = fig.colorbar(c_m, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label(label, fontsize=14)

        out_file = ProjectPaths.FIGURES_DIR / f"mean_climatology_{season.lower()}_{layer}_do.png"
        plt.savefig(out_file, dpi=300, bbox_inches='tight')
        print(f"Saved single figure to {out_file}")
        plt.close()


def plot_mean_four_seasons_bottom():
    seasons = ['Spring', 'Summer', 'Autumn', 'Winter']
    layer = 'bottom'
    
    mean_Zs = {}
    for s in seasons:
        # Avoid recalculating summer if already done, but for simplicity here we just run it again
        # since it's just a few seconds.
        mean_Z = calculate_mean_diffusion(s, layer)
        if mean_Z is not None:
            mean_Zs[s] = mean_Z

    if not mean_Zs:
        print("Failed to calculate means for four seasons.")
        return

    var_cfg = MappingConfig.get_var_settings('do_')
    vmin, vmax = var_cfg['vmin'], var_cfg['vmax']
    cmap = var_cfg['cmap']
    label = var_cfg['label']

    extent = [bounds[0]+0.1, bounds[2]+0.1, bounds[1]-0, bounds[3]+0.2]
    aspect_ratio = (extent[3] - extent[2]) / (extent[1] - extent[0])

    fig_width = 18
    width_per_subplot = fig_width / 2
    height_per_subplot = (width_per_subplot * aspect_ratio) + 0.3
    fig_height = height_per_subplot * 2

    fig, axes = plt.subplots(2, 2, figsize=(fig_width, fig_height),
                             subplot_kw={'projection': ccrs.PlateCarree()})
    axes = axes.flatten()

    c_m = None
    for i, s in enumerate(seasons):
        ax = axes[i]
        ax.set_facecolor(MappingConfig.COLOR_OCEAN)
        add_land_to_ax(ax, land_patches_data)
        ax.set_extent(extent, crs=ccrs.PlateCarree())

        if s in mean_Zs:
            c_m = ax.pcolormesh(lon_wgs, lat_wgs, mean_Zs[s],
                                transform=ccrs.PlateCarree(),
                                cmap=cmap, shading='nearest',
                                zorder=MappingConfig.ZORDER_PREDICTED,
                                vmin=vmin, vmax=vmax)

        ax.set_title(f'Mean Climatological DO: {s} (Bottom)', fontsize=14)
        # Gridlines and Tickers following SIS Mapping Standard
        # "only keep the bottom most and leftmost ticker labels"
        gl = ax.gridlines(draw_labels=True, linestyle=MappingConfig.GRID_LINESTYLE,
                          color=MappingConfig.GRID_COLOR, alpha=MappingConfig.GRID_ALPHA,
                          linewidth=MappingConfig.GRID_LINEWIDTH, zorder=MappingConfig.ZORDER_GRIDLINES)
        gl.top_labels = False
        gl.right_labels = False
        gl.bottom_labels = True if i >= 2 else False
        gl.left_labels = True if i % 2 == 0 else False

    if c_m is not None:
        cbar_ax = fig.add_axes([0.92, 0.15, 0.015, 0.7])
        cbar = fig.colorbar(c_m, cax=cbar_ax)
        cbar.set_label(label, fontsize=14)

    plt.suptitle(f'Mean Climatological DO Distribution (1981-2023)',
                 fontsize=18, fontweight='bold', y=0.95)
    plt.subplots_adjust(right=0.9, wspace=0.05, hspace=0.1)

    out_file = ProjectPaths.FIGURES_DIR / "mean_climatology_four_seasons_bottom_do.png"
    plt.savefig(out_file, dpi=300, bbox_inches='tight')
    print(f"Saved Figure 2 to {out_file}")
    plt.close()


if __name__ == "__main__":
    ProjectPaths.ensure_directories()
    
    t0 = time.time()
    plot_single_seasonal_means()
    t1 = time.time()
    print(f"\nTime for Single Seasonal Figures: {t1-t0:.2f}s\n")
    
    plot_mean_four_seasons_bottom()
    t2 = time.time()
    print(f"\nTime for 2x2 Grid Figure: {t2-t1:.2f}s\n")
    print("Done!")
