import geopandas as gpd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import pandas as pd
import numpy as np
import matplotlib.colors as mcolors
import sys
from pathlib import Path
from tqdm import tqdm
import argparse

# --- BOILERPLATE INJECTED BY AGENT ---
import os
import logging

CURRENT_SCRIPT = Path(__file__).resolve()
sys.path.insert(0, str(CURRENT_SCRIPT.parent.parent))
STEP_DIR = CURRENT_SCRIPT.parent.name
SCRIPT_NAME = CURRENT_SCRIPT.stem
OUTPUT_DIR = Path('/home/reyha/SIS_Analysis_WSL/figures') / STEP_DIR / SCRIPT_NAME
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR = Path('/home/reyha/SIS_Analysis_WSL/data/processed') / STEP_DIR / SCRIPT_NAME
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

step_num = STEP_DIR.split('_')[0].replace('step', '')
log_file = CURRENT_SCRIPT.parent / f"log_process{step_num}.txt"
logging.basicConfig(level=logging.INFO, filename=log_file, format='%(levelname)s: %(message)s')
# -------------------------------------

project_root = CURRENT_SCRIPT.parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.paths import ProjectPaths
from utils.mapping_config import MappingConfig

# Apply the global project style
plt.style.use(str(ProjectPaths.PROJECT_ROOT / 'project_style.mplstyle'))


def create_correlation_map(corr_df, parameter, output_path, pc_name, target_region="Seto Inland Sea"):
    # Filter data first to get data bounds
    merged_df = pd.read_feather(ProjectPaths.MERGED_DATA_FILE)
    if target_region in ['Tokyo Bay', 'Ise Bay', 'Seto Inland Sea']:
        merged_df = merged_df[merged_df['watermass_name'] == target_region]
    else:
        merged_df = merged_df[merged_df['division'] == target_region]

    stations = merged_df[['zettaicode', 'latitude', 'longitude']].drop_duplicates('zettaicode').set_index('zettaicode')
    stations.index = stations.index.astype(str).str.zfill(8)
    corr_df.index = corr_df.index.astype(str).str.zfill(8)
    
    p_col = parameter + '_pval'
    plot_data = stations.join(corr_df[[parameter, p_col]], how='inner').dropna(subset=[parameter, p_col])

    if plot_data.empty:
        logging.warning(f"No correlation data available for {target_region}")
        return

    # 1. Calculation for Figure Dimensions (Maintaining Aspect Ratio)
    extent = MappingConfig.get_dynamic_extent(target_region, plot_data=plot_data)
    extent_width = extent[1] - extent[0]
    zoom_factor = max(4.5 / extent_width, 1.0)
    fig_width, fig_height = MappingConfig.get_dynamic_figsize(extent, base_width=10)
    single_fig_height = fig_height + 1.4
    
    # 2. Base Figure Setup
    fig = plt.figure(figsize=(fig_width, single_fig_height))
    ax = plt.axes(projection=ccrs.PlateCarree())
    
    ax.set_facecolor(MappingConfig.COLOR_OCEAN if hasattr(MappingConfig, 'COLOR_OCEAN') else 'lightblue')
    ax.set_extent(extent, crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.LAND, facecolor=MappingConfig.COLOR_LAND, edgecolor='gray', zorder=MappingConfig.ZORDER_CARTOPY_LAND)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5, edgecolor='black', zorder=MappingConfig.ZORDER_CARTOPY_COASTLINE)
    
    # 3. Add High-Res Coastlines (Land Boundary)
    land_boundary_file = "polbnda_jpn.shp" 
    if hasattr(MappingConfig, 'get_boundary_file'):
        land_boundary_file = MappingConfig.get_boundary_file(target_region)
    land_boundary_path = ProjectPaths.BOUNDARIES_DIR / "SIS_prefecture_boundaries" / land_boundary_file
    
    if land_boundary_path.exists():
        sis_land_boundary = gpd.read_file(land_boundary_path)
        if sis_land_boundary.crs != "EPSG:4326":
            sis_land_boundary = sis_land_boundary.to_crs("EPSG:4326")

        sis_land_boundary.plot(
            ax=ax,
            facecolor=MappingConfig.COLOR_LAND,
            edgecolor=getattr(MappingConfig, 'COLOR_LAND_EDGE', 'gray'),
            linewidth=MappingConfig.LINEWIDTH_LAND,
            transform=ccrs.PlateCarree(),
            zorder=MappingConfig.ZORDER_LAND
        )
    
    # 4. Add Gridlines
    gl = MappingConfig.apply_gridlines(ax)
    
    # 5. Determine Colors and Sizes
    colors = []
    sizes = []
    
    cmap = plt.get_cmap('coolwarm')
    norm = mcolors.Normalize(vmin=-1, vmax=1)
    
    for val, p_val in zip(plot_data[parameter], plot_data[p_col]):
        if p_val <= 0.001: size = 500
        elif p_val <= 0.01: size = 300
        elif p_val <= 0.05: size = 150
        else: size = 20
        sizes.append(size * zoom_factor)
        
        if val < -0.75: color = cmap(0.0)
        elif val < -0.5: color = cmap(0.15)
        elif val < -0.25: color = cmap(0.3)
        elif val < 0: color = cmap(0.45)
        elif val < 0.25: color = cmap(0.55)
        elif val < 0.5: color = cmap(0.7)
        elif val < 0.75: color = cmap(0.85)
        else: color = cmap(1.0)
        colors.append(color)

    # 6. Scatter Plot
    sc = ax.scatter(
        plot_data['longitude'],
        plot_data['latitude'],
        c=colors,
        s=sizes,
        edgecolors='k',
        linewidths=0.5,
        transform=ccrs.PlateCarree(),
        zorder=MappingConfig.ZORDER_PREDICTED,
        alpha=1
    )
    
    # 7. Add Title and Colorbar
    plt.title(f"{pc_name} vs {parameter.replace('_', ' ')} Correlation\n{target_region}", pad=20, fontsize=20, fontweight='bold')
    
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    ticks = [-1.0, -0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75, 1.0]
    
    cbar_ax = fig.add_axes([0.92, 0.15, 0.03, 0.7]) 
    cbar = fig.colorbar(sm, cax=cbar_ax, orientation='vertical', ticks=ticks)
    cbar.set_label('Pearson Correlation (Red=Positive, Blue=Negative)', fontsize=14) 
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pc_name', required=True)
    parser.add_argument('--param', required=True)
    parser.add_argument('--target_region', required=True)
    parser.add_argument('--season', default='Summer')
    parser.add_argument('--layer', default='bottom')
    parser.add_argument('--data_type', required=True, choices=['env', 'nutr'])
    args = parser.parse_args()
    
    season = args.season
    layer = args.layer
    data_type = args.data_type
    
    subset_dir = ProjectPaths.get_subset_dir(season, layer)
    pc_corr_path = subset_dir / f'pca_{data_type}_corr_{args.pc_name.lower()}.csv'
    
    if not pc_corr_path.exists():
        logging.error(f"Error: correlation file not found: {pc_corr_path}")
        return
        
    df_pc = pd.read_csv(pc_corr_path, index_col=0)
    
    if args.param not in df_pc.columns:
        logging.error(f"Parameter {args.param} not found in {pc_corr_path}")
        return
    
    ProjectPaths.ensure_directories()
    
    region_str = args.target_region.replace(" ", "_")
    safe_param = args.param.replace(' ', '_').replace('/', '_')
    for old, new in [('NH4N2', 'NH4-N'), ('NH4N', 'NH4-N'), ('NO3N2', 'NO3-N'), ('NO3N', 'NO3-N'), ('NO2N2', 'NO2-N'), ('NO2N', 'NO2-N'), ('PO4P2', 'PO4-P'), ('PO4P', 'PO4-P')]:
        safe_param = safe_param.replace(old, new)
    
    # Separate outputs based on selected basins
    region_output_dir = OUTPUT_DIR / region_str
    region_output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = region_output_dir / f"spatial_corr_map_{data_type}_{args.pc_name}_{safe_param}_{region_str}_{season}_{layer}.png"
    
    create_correlation_map(df_pc, args.param, output_path, args.pc_name, args.target_region)
    logging.info(f"Correlation map generated: {output_path.name}")

if __name__ == '__main__':
    main()
